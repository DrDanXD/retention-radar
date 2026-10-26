"""Typed data model.

A member's raw activity is normalised into a ``MemberTimeline``. Every signal reads
from that one structure, so adding a new data source only means writing an adapter
in ``retention_radar.ingest``.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Band(StrEnum):
    NEEDS_CARE = "needs_care"
    DRIFTING = "drifting"
    STEADY = "steady"


class Member(BaseModel):
    id: str
    name: str
    coach: str
    annual_value_usd: int = Field(gt=0, description="Membership revenue per year")
    renewal_date: date

    @property
    def first_name(self) -> str:
        return self.name.split()[0]


class WearableSync(BaseModel):
    """One day on which the member's wearable uploaded data."""

    day: date
    source: str = "wearable"


class Message(BaseModel):
    sent_at: datetime
    from_coach: bool
    replied_at: datetime | None = None


class HabitLog(BaseModel):
    """Share of planned habits completed on a day, 0 to 100."""

    day: date
    adherence: float = Field(ge=0, le=100)


class LabDraw(BaseModel):
    scheduled: date
    completed: date | None = None


class CoachCall(BaseModel):
    day: date


class MemberTimeline(BaseModel):
    member: Member
    syncs: list[WearableSync] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    habits: list[HabitLog] = Field(default_factory=list)
    labs: list[LabDraw] = Field(default_factory=list)
    calls: list[CoachCall] = Field(default_factory=list)
    joined: date | None = None

    @field_validator("syncs", "habits", "calls")
    @classmethod
    def _sorted_by_day(cls, v: list) -> list:
        return sorted(v, key=lambda x: x.day)

    @field_validator("messages")
    @classmethod
    def _sorted_by_time(cls, v: list[Message]) -> list[Message]:
        return sorted(v, key=lambda m: m.sent_at)


class SignalHit(BaseModel):
    signal: str
    points: int
    detail: str
    short: str


class RiskAssessment(BaseModel):
    member_id: str
    name: str
    coach: str
    as_of: date
    score: int
    band: Band
    hits: list[SignalHit]
    annual_value_usd: int
    days_to_renewal: int

    @property
    def flagged(self) -> bool:
        return self.band is not Band.STEADY
