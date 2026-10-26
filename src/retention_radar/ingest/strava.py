"""Strava adapter.

Takes the JSON list returned by Strava's ``GET /athlete/activities`` endpoint (or a
saved copy of it). Each activity's ``start_date_local`` (falling back to
``start_date``) becomes a sync day. Many members wear Garmin, Coros or Apple Watch
devices that auto-upload to Strava, so this gives a device-agnostic activity feed.

Strava only carries workouts, so a member who sleeps in a ring but skips workouts
will look quieter here than in a sleep feed. Pair it with a daily-summary source
when one is available.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from retention_radar.models import WearableSync


def syncs_from_strava_activities(activities: Iterable[dict[str, Any]]) -> list[WearableSync]:
    days = set()
    for a in activities:
        stamp = a.get("start_date_local") or a.get("start_date")
        if not stamp:
            continue
        days.add(datetime.fromisoformat(stamp.replace("Z", "+00:00")).date())
    return [WearableSync(day=d, source="strava") for d in sorted(days)]


def load_strava_file(path: str | Path) -> list[WearableSync]:
    with Path(path).open(encoding="utf-8") as f:
        return syncs_from_strava_activities(json.load(f))
