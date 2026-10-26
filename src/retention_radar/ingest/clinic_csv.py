"""Load a clinic from a folder of plain CSV exports.

Expected files (all keyed by ``member_id`` except ``members.csv``)::

    members.csv   id,name,coach,annual_value_usd,renewal_date,joined
    syncs.csv     member_id,date
    messages.csv  member_id,sent_at,sender           (sender is "coach" or "member")
    habits.csv    member_id,date,adherence           (0 to 100)
    labs.csv      member_id,scheduled,completed      (completed may be blank)
    calls.csv     member_id,date

Only ``members.csv`` is required. Missing files mean that signal has no data.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from retention_radar.models import (
    CoachCall,
    HabitLog,
    LabDraw,
    Member,
    MemberTimeline,
    Message,
    WearableSync,
)


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _d(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def pair_replies(raw: Iterable[tuple[datetime, str]]) -> list[Message]:
    """Turn a flat message log into coach messages with ``replied_at`` filled in.

    A coach message counts as answered by the first member message sent after it.
    Member messages are kept too, so the timeline stays complete.
    """
    ordered = sorted(raw, key=lambda x: x[0])
    out: list[Message] = []
    for i, (sent, sender) in enumerate(ordered):
        is_coach = sender.lower() == "coach"
        reply = None
        if is_coach:
            reply = next((s for s, who in ordered[i + 1 :] if who.lower() == "member"), None)
        out.append(Message(sent_at=sent, from_coach=is_coach, replied_at=reply))
    return out


def load_clinic(folder: str | Path) -> list[MemberTimeline]:
    root = Path(folder)
    members = _rows(root / "members.csv")
    if not members:
        raise FileNotFoundError(f"No members.csv with rows in {root}")

    by: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in _rows(root / "syncs.csv"):
        by[r["member_id"]]["syncs"].append(WearableSync(day=_d(r["date"])))
    for r in _rows(root / "messages.csv"):
        by[r["member_id"]]["raw_messages"].append(
            (datetime.fromisoformat(r["sent_at"]), r["sender"])
        )
    for r in _rows(root / "habits.csv"):
        by[r["member_id"]]["habits"].append(
            HabitLog(day=_d(r["date"]), adherence=float(r["adherence"]))
        )
    for r in _rows(root / "labs.csv"):
        by[r["member_id"]]["labs"].append(
            LabDraw(scheduled=_d(r["scheduled"]), completed=_d(r.get("completed", "")))
        )
    for r in _rows(root / "calls.csv"):
        by[r["member_id"]]["calls"].append(CoachCall(day=_d(r["date"])))

    timelines = []
    for r in members:
        data = by.get(r["id"], {})
        timelines.append(
            MemberTimeline(
                member=Member(
                    id=r["id"],
                    name=r["name"],
                    coach=r["coach"],
                    annual_value_usd=int(r["annual_value_usd"]),
                    renewal_date=_d(r["renewal_date"]),
                ),
                joined=_d(r.get("joined", "")),
                syncs=data.get("syncs", []),
                messages=pair_replies(data.get("raw_messages", [])),
                habits=data.get("habits", []),
                labs=data.get("labs", []),
                calls=data.get("calls", []),
            )
        )
    return timelines
