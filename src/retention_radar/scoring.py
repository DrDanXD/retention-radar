"""Combine signals into one explainable risk score per member."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from retention_radar.config import DEFAULT, Thresholds
from retention_radar.models import Band, MemberTimeline, RiskAssessment
from retention_radar.signals import DEFAULT_SIGNALS, Signal


def band_for(score: int, cfg: Thresholds = DEFAULT) -> Band:
    if score >= cfg.needs_care_at:
        return Band.NEEDS_CARE
    if score >= cfg.drifting_at:
        return Band.DRIFTING
    return Band.STEADY


def assess(
    timeline: MemberTimeline,
    as_of: date,
    cfg: Thresholds = DEFAULT,
    signals: Sequence[Signal] = DEFAULT_SIGNALS,
) -> RiskAssessment:
    hits = [h for s in signals if (h := s(timeline, as_of, cfg)) is not None]
    hits.sort(key=lambda h: h.points, reverse=True)
    score = sum(h.points for h in hits)
    m = timeline.member
    return RiskAssessment(
        member_id=m.id,
        name=m.name,
        coach=m.coach,
        as_of=as_of,
        score=score,
        band=band_for(score, cfg),
        hits=hits,
        annual_value_usd=m.annual_value_usd,
        days_to_renewal=(m.renewal_date - as_of).days,
    )


def assess_all(
    timelines: Iterable[MemberTimeline],
    as_of: date,
    cfg: Thresholds = DEFAULT,
) -> list[RiskAssessment]:
    """Assess every member, highest risk first."""
    out = [assess(t, as_of, cfg) for t in timelines]
    out.sort(key=lambda a: (-a.score, a.days_to_renewal))
    return out


def at_risk_value(assessments: Iterable[RiskAssessment], cfg: Thresholds = DEFAULT) -> int:
    """Annual revenue from flagged members whose renewal falls inside the horizon."""
    return sum(
        a.annual_value_usd
        for a in assessments
        if a.flagged and 0 <= a.days_to_renewal <= cfg.renewal_horizon_days
    )
