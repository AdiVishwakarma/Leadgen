from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DiscoverRequest(BaseModel):
    category: str = Field(examples=["dentist"])
    city: str = Field(examples=["Vasai"])
    limit: int = Field(default=20, ge=1, le=60)


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    score: int
    reasons: list[str]
    signals: dict
    created_at: datetime


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    place_id: str
    name: str
    category: str | None
    address: str | None
    phone: str | None
    website: str | None
    rating: float | None
    review_count: int | None
    city: str | None
    status: str
    score: int | None


class DiscoverResponse(BaseModel):
    found: int
    inserted: int
    skipped_duplicates: int
