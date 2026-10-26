"""Every threshold and point value lives here so a clinic can tune it in one place."""

from __future__ import annotations

from pydantic import BaseModel


class Tier(BaseModel):
    at_least: float
    points: int


class Thresholds(BaseModel):
    # Wearable: days since the last successful sync
    wearable_gap: list[Tier] = [Tier(at_least=14, points=30), Tier(at_least=7, points=15)]

    # Messages: coach messages with no member reply
    unanswered_window_days: int = 30
    unanswered_grace_hours: int = 48
    unanswered: list[Tier] = [Tier(at_least=2, points=20), Tier(at_least=1, points=8)]

    # Habits: drop in mean adherence, recent window vs baseline window, in points
    habit_recent_days: int = 14
    habit_baseline_days: int = 28
    habit_drop: list[Tier] = [Tier(at_least=25, points=20), Tier(at_least=10, points=10)]
    habit_min_logged_days: int = 5

    # Labs: a scheduled draw that never happened
    missed_lab_window_days: int = 30
    missed_lab_points: int = 15

    # Coach: days since the last live conversation
    coach_gap: list[Tier] = [Tier(at_least=90, points=15), Tier(at_least=60, points=8)]

    # Bands
    needs_care_at: int = 55
    drifting_at: int = 30

    # Revenue at risk only counts renewals inside this horizon
    renewal_horizon_days: int = 60


def first_tier(value: float, tiers: list[Tier]) -> int:
    """Points for the highest tier ``value`` reaches. Tiers are checked in order."""
    for tier in tiers:
        if value >= tier.at_least:
            return tier.points
    return 0


DEFAULT = Thresholds()
