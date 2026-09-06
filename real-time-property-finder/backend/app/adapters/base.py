"""Shared plumbing for portal adapters.

Pipeline per adapter: discover URLs (done upstream by the search
provider + query builder) -> fetch page -> extract structured fields ->
normalize -> return a PropertyRecord. Fetching is shared here so every
adapter gets the same timeout/retry/blocked-page handling; extraction is
mostly shared too (see ``GenericExtractionMixin``) since real portal
markup is too unstable to hard-code selectors against — adapters mainly
differ in which domains they claim and how they pull a source listing id
out of the URL.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

from .. import config, extraction_utils as ex
from ..logging_config import logger
from ..models import AvailabilityStatus, PropertyRecord


class FetchOutcome:
    def __init__(self, status_code: Optional[int], html: Optional[str], error: Optional[str] = None):
        self.status_code = status_code
        self.html = html
        self.error = error

    @property
    def ok(self) -> bool:
        return self.status_code == 200 and self.html is not None


class PortalAdapter(ABC):
    source_name: str = "unknown"
    domains: List[str] = []

    @classmethod
    def matches(cls, url: str) -> bool:
        return any(domain in url for domain in cls.domains)

    async def fetch(self, url: str, client: httpx.AsyncClient) -> FetchOutcome:
        headers = {"User-Agent": config.USER_AGENT}
        attempts = 2
        for attempt in range(1, attempts + 1):
            try:
                response = await client.get(url, headers=headers, follow_redirects=True)
                if response.status_code == 200:
                    return FetchOutcome(response.status_code, response.text)
                if response.status_code in (403, 429, 503) and attempt < attempts:
                    await asyncio.sleep(0.8 * attempt)
                    continue
                return FetchOutcome(response.status_code, response.text if response.status_code < 500 else None)
            except httpx.HTTPError as exc:
                if attempt >= attempts:
                    return FetchOutcome(None, None, error=str(exc))
                await asyncio.sleep(0.5 * attempt)
        return FetchOutcome(None, None, error="exhausted retries")

    @abstractmethod
    def extract(self, url: str, html: str) -> Optional[PropertyRecord]:
        raise NotImplementedError

    def source_listing_id(self, url: str) -> Optional[str]:
        match = re.search(r"([a-zA-Z0-9]{6,})(?:\.html|/?$)", url.split("?")[0])
        return match.group(1) if match else None


class GenericExtractionMixin:
    """Domain-agnostic field extraction shared by every adapter."""

    def _build_record(self, url: str, html: str, source_name: str, listing_id: Optional[str]) -> Optional[PropertyRecord]:
        soup = BeautifulSoup(html, "lxml")

        if ex.looks_blocked(200, html):
            logger.info("Page appears blocked/CAPTCHA-gated, skipping: %s", url)
            return None

        text = ex.visible_text(soup)

        if ex.is_pg_or_shared(text):
            logger.info("Excluded (looks like PG/shared/hostel, not independent rental): %s", url)
            return None
        if ex.is_commercial(text):
            logger.info("Excluded (looks like a commercial listing): %s", url)
            return None

        json_ld = ex.extract_json_ld(soup)

        title = (
            ex.extract_meta(soup, "og:title")
            or (soup.title.get_text(strip=True) if soup.title else None)
            or json_ld.get("name")
        )
        description = ex.extract_meta(soup, "og:description", "description") or json_ld.get("description")
        photo_url = ex.extract_meta(soup, "og:image") or json_ld.get("image")
        locality = ex.extract_locality(title, description)
        address = ex.extract_address_from_json_ld(json_ld) or locality

        rent = ex.extract_rent(text)
        bhk = ex.extract_bhk(text)
        size_sqft = ex.extract_size_sqft(text)
        deposit = ex.extract_deposit(text)
        maintenance = ex.extract_maintenance(text)
        phone = ex.extract_phone(text)
        furnishing = ex.detect_furnishing(text)
        parking = ex.detect_parking(text)
        lift = ex.detect_lift(text)
        water = ex.detect_water_supply(text)
        owner_or_agent = ex.detect_owner_or_agent(text)
        brokerage = ex.detect_brokerage(text)
        food_preference = ex.detect_food_preference(text)
        property_type = ex.detect_property_type(text)

        known_fields = [
            rent, bhk, size_sqft, deposit, furnishing, parking, lift, water,
            owner_or_agent, property_type, photo_url, description,
        ]
        confidence = round(sum(1 for f in known_fields if f is not None) / len(known_fields), 2)

        now_iso = datetime.now(timezone.utc).isoformat()

        return PropertyRecord(
            id=str(uuid.uuid4()),
            source=source_name,
            source_listing_id=listing_id,
            listing_url=url,
            photo_url=photo_url,
            property_name=title,
            property_type=property_type,
            bhk=bhk,
            locality=locality,
            address=address,
            monthly_rent=rent,
            maintenance=maintenance,
            security_deposit=deposit,
            brokerage=brokerage,
            size_sqft=size_sqft,
            furnishing=furnishing,
            parking=parking,
            lift=lift,
            water_supply=water,
            food_preference=food_preference,
            owner_or_agent=owner_or_agent,
            contact_number=phone,
            listed_date=None,
            updated_date=None,
            last_checked=now_iso,
            availability_status=AvailabilityStatus.POSSIBLY_ACTIVE if confidence > 0 else AvailabilityStatus.UNABLE_TO_VERIFY,
            description=description,
            source_confidence=confidence,
        )
