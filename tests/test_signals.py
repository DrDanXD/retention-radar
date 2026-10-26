from datetime import timedelta

import pytest

from retention_radar.config import DEFAULT, Tier, first_tier
from retention_radar.models import CoachCall, HabitLog, LabDraw, Message, WearableSync
from retention_radar.signals import (
    coach_gap,
    habit_slip,
    missed_lab,
    unanswered_messages,
    wearable_gap,
)

from .conftest import AS_OF, at, days_ago


def test_healthy_member_trips_nothing(healthy):
    for signal in (wearable_gap, unanswered_messages, habit_slip, missed_lab, coach_gap):
        assert signal(healthy, AS_OF, DEFAULT) is None


@pytest.mark.parametrize(
    ("tiers", "value", "expected"),
    [
        ([Tier(at_least=14, points=30), Tier(at_least=7, points=15)], 6, 0),
        ([Tier(at_least=14, points=30), Tier(at_least=7, points=15)], 7, 15),
        ([Tier(at_least=14, points=30), Tier(at_least=7, points=15)], 13, 15),
        ([Tier(at_least=14, points=30), Tier(at_least=7, points=15)], 14, 30),
    ],
)
def test_first_tier_boundaries(tiers, value, expected):
    assert first_tier(value, tiers) == expected


@pytest.mark.parametrize(
    ("last_sync", "points"), [(6, None), (7, 15), (13, 15), (14, 30), (40, 30)]
)
def test_wearable_gap_tiers(healthy, last_sync, points):
    t = healthy.model_copy(update={"syncs": [WearableSync(day=days_ago(last_sync))]})
    hit = wearable_gap(t, AS_OF, DEFAULT)
    assert (hit.points if hit else None) == points


def test_wearable_gap_ignores_future_syncs(healthy):
    """Backtests replay the past. A sync after as_of must not hide a gap."""
    t = healthy.model_copy(
        update={
            "syncs": [WearableSync(day=days_ago(20)), WearableSync(day=AS_OF + timedelta(days=2))]
        }
    )
    assert wearable_gap(t, AS_OF, DEFAULT).points == 30


def test_wearable_gap_falls_back_to_join_date(healthy):
    t = healthy.model_copy(update={"syncs": [], "joined": days_ago(9)})
    assert wearable_gap(t, AS_OF, DEFAULT).points == 15


def test_unanswered_counts_only_coach_messages_past_grace(healthy):
    t = healthy.model_copy(
        update={
            "messages": [
                Message(sent_at=at(12), from_coach=True),  # unanswered
                Message(sent_at=at(5), from_coach=True),  # unanswered
                Message(sent_at=at(1), from_coach=True),  # inside 48h grace, not counted
                Message(sent_at=at(3), from_coach=False),  # member message, ignored
                Message(sent_at=at(45), from_coach=True),  # outside 30 day window
            ]
        }
    )
    hit = unanswered_messages(t, AS_OF, DEFAULT)
    assert hit.points == 20
    assert hit.short == "2 unanswered"


def test_reply_after_as_of_still_counts_as_unanswered(healthy):
    t = healthy.model_copy(
        update={"messages": [Message(sent_at=at(6), from_coach=True, replied_at=at(-2))]}
    )
    assert unanswered_messages(t, AS_OF, DEFAULT).points == 8


def test_habit_slip_measures_drop_against_baseline(healthy):
    habits = [HabitLog(day=days_ago(i), adherence=80) for i in range(15, 43)]
    habits += [HabitLog(day=days_ago(i), adherence=50) for i in range(14)]
    t = healthy.model_copy(update={"habits": habits})
    hit = habit_slip(t, AS_OF, DEFAULT)
    assert hit.points == 20
    assert "80%" in hit.detail and "50%" in hit.detail


def test_habit_slip_treats_missing_recent_logs_as_zero(healthy):
    habits = [HabitLog(day=days_ago(i), adherence=40) for i in range(15, 43)]
    habits += [HabitLog(day=days_ago(i), adherence=40) for i in range(7)]  # stopped logging
    t = healthy.model_copy(update={"habits": habits})
    assert habit_slip(t, AS_OF, DEFAULT).points == 10  # 40 -> 20


def test_habit_slip_needs_a_baseline(healthy):
    t = healthy.model_copy(
        update={"habits": [HabitLog(day=days_ago(i), adherence=10) for i in range(10)]}
    )
    assert habit_slip(t, AS_OF, DEFAULT) is None


def test_missed_lab_only_when_not_completed_by_as_of(healthy):
    late = healthy.model_copy(
        update={"labs": [LabDraw(scheduled=days_ago(10), completed=AS_OF + timedelta(days=1))]}
    )
    assert missed_lab(late, AS_OF, DEFAULT).points == 15
    old = healthy.model_copy(update={"labs": [LabDraw(scheduled=days_ago(45))]})
    assert missed_lab(old, AS_OF, DEFAULT) is None


@pytest.mark.parametrize(("last_call", "points"), [(59, None), (60, 8), (89, 8), (90, 15)])
def test_coach_gap_tiers(healthy, last_call, points):
    t = healthy.model_copy(update={"calls": [CoachCall(day=days_ago(last_call))]})
    hit = coach_gap(t, AS_OF, DEFAULT)
    assert (hit.points if hit else None) == points
