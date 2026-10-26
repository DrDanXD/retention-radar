"""Churn signals.

Each signal is a small pure function: ``(timeline, as_of, thresholds) -> SignalHit | None``.
Signals only look at data on or before ``as_of`` so the same code runs live and in the
backtest without leaking the future.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from retention_radar.config import Thresholds, first_tier
from retention_radar.models import MemberTimeline, SignalHit

Signal = Callable[[MemberTimeline, date, Thresholds], SignalHit | None]


def _end_of(day: date) -> datetime:
    return datetime.combine(day, time.max)


def wearable_gap(t: MemberTimeline, as_of: date, cfg: Thresholds) -> SignalHit | None:
    """Days since the wearable last synced."""
    seen = [s.day for s in t.syncs if s.day <= as_of]
    if seen:
        gap = (as_of - seen[-1]).days
    elif t.joined and t.joined <= as_of:
        gap = (as_of - t.joined).days
    else:
        return None
    pts = first_tier(gap, cfg.wearable_gap)
    if not pts:
        return None
    return SignalHit(
        signal="wearable_gap",
        points=pts,
        detail=f"Wearable has not synced in {gap} days",
        short=f"No sync {gap}d",
    )


def unanswered_messages(t: MemberTimeline, as_of: date, cfg: Thresholds) -> SignalHit | None:
    """Coach messages in the window that the member has not replied to."""
    end = _end_of(as_of)
    window_start = end - timedelta(days=cfg.unanswered_window_days)
    grace = timedelta(hours=cfg.unanswered_grace_hours)
    count = sum(
        1
        for m in t.messages
        if m.from_coach
        and window_start < m.sent_at <= end - grace
        and (m.replied_at is None or m.replied_at > end)
    )
    pts = first_tier(count, cfg.unanswered)
    if not pts:
        return None
    noun = "message" if count == 1 else "messages"
    return SignalHit(
        signal="unanswered_messages",
        points=pts,
        detail=f"{count} coach {noun} unanswered",
        short=f"{count} unanswered",
    )


def habit_slip(t: MemberTimeline, as_of: date, cfg: Thresholds) -> SignalHit | None:
    """Drop in habit adherence: recent window vs the window before it.

    Days with no log in the recent window count as zero. A member who stops logging
    has slipped, and silence should not look like stability.
    """
    recent_start = as_of - timedelta(days=cfg.habit_recent_days)
    base_start = recent_start - timedelta(days=cfg.habit_baseline_days)
    base = [h.adherence for h in t.habits if base_start < h.day <= recent_start]
    recent = {h.day: h.adherence for h in t.habits if recent_start < h.day <= as_of}
    if len(base) < cfg.habit_min_logged_days:
        return None
    base_mean = sum(base) / len(base)
    recent_mean = sum(recent.values()) / cfg.habit_recent_days
    drop = base_mean - recent_mean
    pts = first_tier(drop, cfg.habit_drop)
    if not pts:
        return None
    return SignalHit(
        signal="habit_slip",
        points=pts,
        detail=f"Habit adherence fell from {base_mean:.0f}% to {recent_mean:.0f}%",
        short=f"Habits {base_mean:.0f}→{recent_mean:.0f}%",
    )


def missed_lab(t: MemberTimeline, as_of: date, cfg: Thresholds) -> SignalHit | None:
    """A lab draw scheduled in the window that never happened."""
    window_start = as_of - timedelta(days=cfg.missed_lab_window_days)
    missed = [
        lab
        for lab in t.labs
        if window_start < lab.scheduled < as_of and (lab.completed is None or lab.completed > as_of)
    ]
    if not missed:
        return None
    when = (as_of - missed[-1].scheduled).days
    return SignalHit(
        signal="missed_lab",
        points=cfg.missed_lab_points,
        detail=f"Missed a scheduled lab draw {when} days ago",
        short="Missed lab",
    )


def coach_gap(t: MemberTimeline, as_of: date, cfg: Thresholds) -> SignalHit | None:
    """Days since the last live conversation with the coach."""
    seen = [c.day for c in t.calls if c.day <= as_of]
    if seen:
        gap = (as_of - seen[-1]).days
    elif t.joined and t.joined <= as_of:
        gap = (as_of - t.joined).days
    else:
        return None
    pts = first_tier(gap, cfg.coach_gap)
    if not pts:
        return None
    return SignalHit(
        signal="coach_gap",
        points=pts,
        detail=f"No coach conversation in {gap} days",
        short=f"No call {gap}d",
    )


DEFAULT_SIGNALS: tuple[Signal, ...] = (
    wearable_gap,
    unanswered_messages,
    habit_slip,
    missed_lab,
    coach_gap,
)
