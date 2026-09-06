"""Pydantic data models shared across the search pipeline."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class PropertyType(str, Enum):
    ANY = "any"
    APARTMENT = "apartment"
    INDEPENDENT_HOUSE = "independent_house"
    VILLA = "villa"


class BHK(str, Enum):
    ANY = "any"
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR_PLUS = "4+"


class Furnishing(str, Enum):
    ANY = "any"
    UNFURNISHED = "unfurnished"
    SEMI_FURNISHED = "semi_furnished"
    FULLY_FURNISHED = "fully_furnished"


class ParkingPreference(str, Enum):
    ANY = "any"
    COVERED = "covered"
    OPEN = "open"
    NONE = "none"


class LiftPreference(str, Enum):
    ANY = "any"
    REQUIRED = "required"
    NOT_REQUIRED = "not_required"


class WaterPreference(str, Enum):
    ANY = "any"
    PREFERRED = "preferred"
    REQUIRED = "required"


class BrokeragePreference(str, Enum):
    ANY = "any"
    PREFERRED = "preferred"
    ONLY = "only"


class FoodPreference(str, Enum):
    ANY = "any"
    VEGETARIAN = "vegetarian"
    NON_VEGETARIAN = "non_vegetarian"


class AvailabilityStatus(str, Enum):
    ACTIVE = "active"
    POSSIBLY_ACTIVE = "possibly_active"
    STALE = "stale"
    INACTIVE = "inactive"
    UNAVAILABLE = "unavailable"
    UNABLE_TO_VERIFY = "unable_to_verify"


class SourceState(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class Priority(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class SearchRequest(BaseModel):
    """A single, free-form area/locality is the only geography input.

    No city field, no radius, no predefined locality list: whatever the
    user types is used verbatim as the primary geographic search term.
    """

    area: str = Field(..., min_length=1, description="Free-form area / locality text")
    property_type: PropertyType = PropertyType.ANY
    bhk: BHK = BHK.ANY
    min_rent: Optional[int] = Field(default=None, ge=0)
    max_rent: Optional[int] = Field(default=None, ge=0)
    furnishing: Furnishing = Furnishing.ANY
    parking: ParkingPreference = ParkingPreference.ANY
    lift: LiftPreference = LiftPreference.ANY
    water: WaterPreference = WaterPreference.ANY
    brokerage: BrokeragePreference = BrokeragePreference.ANY
    food_preference: FoodPreference = FoodPreference.ANY

    @field_validator("area")
    @classmethod
    def area_must_be_meaningful(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("area must not be blank")
        return cleaned

    @model_validator(mode="after")
    def rent_range_is_sane(self) -> "SearchRequest":
        if self.min_rent is not None and self.max_rent is not None:
            if self.min_rent > self.max_rent:
                raise ValueError("min_rent must not exceed max_rent")
        return self


class PropertyRecord(BaseModel):
    """Normalized representation of a single discovered listing.

    Any field that could not be found or confirmed on the source page is
    left as ``None``. The frontend is responsible for rendering that as
    "Not verified" / "Not publicly available" — the backend never invents
    a value to fill a gap.
    """

    id: str
    source: str
    source_listing_id: Optional[str] = None
    listing_url: str
    photo_url: Optional[str] = None
    property_name: Optional[str] = None
    property_type: Optional[str] = None
    bhk: Optional[str] = None
    locality: Optional[str] = None
    address: Optional[str] = None
    monthly_rent: Optional[int] = None
    maintenance: Optional[int] = None
    security_deposit: Optional[int] = None
    brokerage: Optional[str] = None
    size_sqft: Optional[int] = None
    furnishing: Optional[str] = None
    parking: Optional[str] = None
    lift: Optional[str] = None
    water_supply: Optional[str] = None
    food_preference: Optional[str] = None
    owner_or_agent: Optional[str] = None
    contact_number: Optional[str] = None
    listed_date: Optional[str] = None
    updated_date: Optional[str] = None
    last_checked: str
    availability_status: AvailabilityStatus = AvailabilityStatus.UNABLE_TO_VERIFY
    description: Optional[str] = None
    source_confidence: float = 0.0
    match_score: Optional[float] = None
    priority: Optional[Priority] = None
    notes: List[str] = Field(default_factory=list)
    merged_sources: List[str] = Field(default_factory=list)


class SourceStatus(BaseModel):
    name: str
    state: SourceState
    queries_attempted: int = 0
    candidates_found: int = 0
    listings_extracted: int = 0
    message: Optional[str] = None


class SearchStatistics(BaseModel):
    sources_searched: int
    listings_discovered: int
    after_filtering: int
    after_deduplication: int


class SearchResponse(BaseModel):
    search_id: str
    searched_at: str
    request: SearchRequest
    sources: List[SourceStatus]
    statistics: SearchStatistics
    results: List[PropertyRecord]
    queries_used: List[str] = Field(default_factory=list)
    no_results_suggestions: List[str] = Field(default_factory=list)
