"""HTTP API.

Run with::

    radar serve data/sample_clinic

or ``uvicorn retention_radar.api:app`` with ``RADAR_DATA`` pointing at a clinic folder.
"""

from __future__ import annotations

import os
from datetime import date

from fastapi import FastAPI, HTTPException, Query

from retention_radar.drafts import draft_checkin
from retention_radar.ingest import load_clinic
from retention_radar.models import MemberTimeline, RiskAssessment
from retention_radar.scoring import assess, assess_all, at_risk_value


def create_app(timelines: list[MemberTimeline]) -> FastAPI:
    app = FastAPI(title="Retention Radar", version="0.1.0")
    by_id = {t.member.id: t for t in timelines}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/members/at-risk")
    def at_risk(
        as_of: date | None = None,
        horizon: int = Query(60, ge=1, le=365),
    ) -> dict:
        day = as_of or date.today()
        flagged = [
            a for a in assess_all(timelines, day) if a.flagged and 0 <= a.days_to_renewal <= horizon
        ]
        return {
            "as_of": day.isoformat(),
            "horizon_days": horizon,
            "at_risk_usd": at_risk_value(flagged),
            "members": [a.model_dump(mode="json") for a in flagged],
        }

    @app.get("/members/{member_id}", response_model=RiskAssessment)
    def member(member_id: str, as_of: date | None = None) -> RiskAssessment:
        t = by_id.get(member_id)
        if t is None:
            raise HTTPException(404, f"No member {member_id}")
        return assess(t, as_of or date.today())

    @app.get("/members/{member_id}/draft")
    def draft(member_id: str, as_of: date | None = None) -> dict[str, str]:
        t = by_id.get(member_id)
        if t is None:
            raise HTTPException(404, f"No member {member_id}")
        return {"member_id": member_id, "draft": draft_checkin(assess(t, as_of or date.today()))}

    return app


def _from_env() -> FastAPI:
    folder = os.getenv("RADAR_DATA")
    return create_app(load_clinic(folder) if folder else [])


app = _from_env()
