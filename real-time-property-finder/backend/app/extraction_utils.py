"""Portal-agnostic heuristics for pulling structured fields out of an
arbitrary property-listing HTML page.

Real portal markup changes constantly and differs page to page, so
instead of brittle CSS selectors we lean on the things that tend to be
stable across sites: JSON-LD structured data, Open Graph meta tags, and
plain-text pattern matching over the visible page text. When a value
cannot be found with reasonable confidence, the corresponding extractor
returns ``None`` rather than guessing.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup

_RENT_RANGE_RE = re.compile(
    r"(?:rent|rs\.?|inr|₹)\s*[:\-]?\s*₹?\s*([\d,]{3,8})(?:\s*(?:-|to)\s*₹?\s*([\d,]{3,8}))?",
    re.IGNORECASE,
)
_PLAIN_RUPEE_RE = re.compile(r"₹\s*([\d,]{3,8})")
_BHK_RE = re.compile(r"(\d)\s*[- ]?\s*bhk", re.IGNORECASE)
_SQFT_RE = re.compile(r"([\d,]{2,6})\s*(?:sq\.?\s*ft|sqft|sq\.?\s*feet)", re.IGNORECASE)
_DEPOSIT_RE = re.compile(r"deposit[^\d₹]{0,15}₹?\s*([\d,]{3,9})", re.IGNORECASE)
_MAINTENANCE_RE = re.compile(r"maintenance[^\d₹]{0,15}₹?\s*([\d,]{2,8})", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b")
_LOCALITY_RE = re.compile(r"\bin\s+([A-Z][A-Za-z\s]{2,45}?)(?:,|\s+for\b|\s+rent\b|$)")


def _to_int(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def extract_json_ld(soup: BeautifulSoup) -> Dict[str, Any]:
    """Merge every JSON-LD ``<script>`` block into a single dict, best effort."""
    merged: Dict[str, Any] = {}
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict):
                merged.update(item)
    return merged


def extract_meta(soup: BeautifulSoup, *names: str) -> Optional[str]:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def extract_rent(text: str) -> Optional[int]:
    """Returns the rent only when the text points at exactly one figure.

    A portal locality/category page (listing many properties, or showing
    price-tier facet links like "under 20000", "under 30000") often
    contains several different rent-like numbers with nothing tying any
    one of them to a specific property. Picking the first one would be a
    guess, and per spec an ambiguous rent must not be treated as a
    confident value (and must never cause a hard-filter exclusion) - so
    multiple distinct figures resolve to "not verified" (None) rather
    than an arbitrary pick.
    """
    candidates = [_to_int(m.group(1)) for m in _RENT_RANGE_RE.finditer(text)]
    candidates += [_to_int(m.group(1)) for m in _PLAIN_RUPEE_RE.finditer(text)]
    candidates = [c for c in candidates if c]
    distinct = set(candidates)
    if len(distinct) == 1:
        return candidates[0]
    return None


def extract_bhk(text: str) -> Optional[str]:
    match = _BHK_RE.search(text)
    if match:
        return match.group(1)
    return None


def extract_size_sqft(text: str) -> Optional[int]:
    match = _SQFT_RE.search(text)
    if match:
        return _to_int(match.group(1))
    return None


def extract_deposit(text: str) -> Optional[int]:
    match = _DEPOSIT_RE.search(text)
    if match:
        return _to_int(match.group(1))
    return None


def extract_maintenance(text: str) -> Optional[int]:
    match = _MAINTENANCE_RE.search(text)
    if match:
        return _to_int(match.group(1))
    return None


def extract_phone(text: str) -> Optional[str]:
    match = _PHONE_RE.search(text)
    if match:
        return match.group(0)
    return None


def detect_furnishing(text: str) -> Optional[str]:
    lowered = text.lower()
    if "fully furnished" in lowered or "fully-furnished" in lowered:
        return "fully_furnished"
    if "semi furnished" in lowered or "semi-furnished" in lowered:
        return "semi_furnished"
    if "unfurnished" in lowered:
        return "unfurnished"
    return None


def detect_parking(text: str) -> Optional[str]:
    lowered = text.lower()
    if "covered parking" in lowered or "covered car parking" in lowered:
        return "covered"
    if "open parking" in lowered:
        return "open"
    if "no parking" in lowered:
        return "none"
    return None


def detect_lift(text: str) -> Optional[str]:
    lowered = text.lower()
    if "lift available" in lowered or ("lift" in lowered and "no lift" not in lowered):
        return "available"
    if "no lift" in lowered:
        return "not_available"
    return None


def detect_water_supply(text: str) -> Optional[str]:
    lowered = text.lower()
    if "24x7 water" in lowered or "24/7 water" in lowered or "reliable water" in lowered:
        return "reliable"
    if "water shortage" in lowered or "water problem" in lowered:
        return "unreliable"
    return None


def detect_owner_or_agent(text: str) -> Optional[str]:
    lowered = text.lower()
    owner_signals = ["no brokerage", "owner listed", "posted by owner", "by owner"]
    if any(signal in lowered for signal in owner_signals):
        return "owner"
    if re.search(r"\bowner\b", lowered) and "broker" not in lowered and "agent" not in lowered:
        return "owner"
    if "broker" in lowered or "agent" in lowered:
        return "agent"
    return None


def detect_brokerage(text: str) -> Optional[str]:
    lowered = text.lower()
    if "no brokerage" in lowered or "zero brokerage" in lowered:
        return "none"
    match = re.search(r"brokerage[^\d₹]{0,15}₹?\s*([\d,]{3,8})", lowered)
    if match:
        return f"₹{match.group(1)}"
    return None


def detect_food_preference(text: str) -> Optional[str]:
    """Only ever reads an explicit statement on the page — never inferred
    from locality, community, or any other indirect signal."""
    lowered = text.lower()
    if "vegetarian only" in lowered or "veg only" in lowered or "strictly vegetarian" in lowered:
        return "vegetarian"
    if "non-veg allowed" in lowered or "non veg allowed" in lowered:
        return "non_vegetarian"
    return None


def detect_property_type(text: str) -> Optional[str]:
    lowered = text.lower()
    if "villa" in lowered:
        return "villa"
    if "independent house" in lowered or "individual house" in lowered:
        return "independent_house"
    if "apartment" in lowered or "flat" in lowered:
        return "apartment"
    return None


def is_pg_or_shared(text: str) -> bool:
    lowered = text.lower()
    # Deliberately no bare "pg" token: a two-letter abbreviation is too
    # likely to appear in unrelated portal cross-sell text ("Flats, PG,
    # Commercial for rent in ...") even within a title/description, so
    # only unambiguous multi-word phrases are treated as PG signals.
    keywords = ["paying guest", "pg for boys", "pg for girls", "pg accommodation", "hostel", "shared room", "shared accommodation"]
    if any(k in f" {lowered} " for k in keywords):
        if "co-living" in lowered and "private" in lowered and "shared" not in lowered:
            return False
        return True
    if "co-living" in lowered and ("shared" in lowered or "bed space" in lowered):
        return True
    return False


def is_commercial(text: str) -> bool:
    lowered = text.lower()
    keywords = ["commercial property", "office space", "shop for rent", "warehouse", "showroom for rent", "commercial space"]
    return any(k in lowered for k in keywords)


def extract_locality(*texts: Optional[str]) -> Optional[str]:
    for text in texts:
        if not text:
            continue
        match = _LOCALITY_RE.search(text)
        if match:
            return match.group(1).strip()
    return None


def extract_address_from_json_ld(json_ld: Dict[str, Any]) -> Optional[str]:
    address = json_ld.get("address")
    if isinstance(address, str):
        return address
    if isinstance(address, dict):
        parts = [
            address.get("streetAddress"),
            address.get("addressLocality"),
            address.get("addressRegion"),
        ]
        joined = ", ".join(p for p in parts if p)
        return joined or None
    return None


def looks_blocked(status_code: int, html: str) -> bool:
    if status_code in (403, 429, 503, 999):
        return True
    lowered = html.lower()
    return any(k in lowered for k in ["captcha", "access denied", "are you a robot", "unusual traffic"])
