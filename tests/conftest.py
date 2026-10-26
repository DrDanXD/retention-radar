from datetime import date, datetime, timedelta

import pytest

from retention_radar.models import (
    CoachCall,
    HabitLog,
    LabDraw,
    Member,
    MemberTimeline,
    Message,
    WearableSync,
)

AS_OF = date(2026, 10, 26)


def days_ago(n: int) -> date:
    return AS_OF - timedelta(days=n)


def at(n_days_ago: int, hour: int = 10) -> datetime:
    return datetime.combine(days_ago(n_days_ago), datetime.min.time()).replace(hour=hour)


@pytest.fixture
def member() -> Member:
    return Member(
        id="m-1",
        name="Elena Marsh",
        coach="Dana",
        annual_value_usd=32_000,
        renewal_date=AS_OF + timedelta(days=18),
    )


@pytest.fixture
def healthy(member: Member) -> MemberTimeline:
    """Engaged member: syncs daily, replies, steady habits, labs done, recent call."""
    return MemberTimeline(
        member=member,
        joined=days_ago(300),
        syncs=[WearableSync(day=days_ago(i)) for i in range(60)],
        messages=[
            Message(sent_at=at(10), from_coach=True, replied_at=at(9)),
            Message(sent_at=at(9), from_coach=False),
        ],
        habits=[HabitLog(day=days_ago(i), adherence=80) for i in range(60)],
        labs=[LabDraw(scheduled=days_ago(20), completed=days_ago(19))],
        calls=[CoachCall(day=days_ago(25))],
    )
