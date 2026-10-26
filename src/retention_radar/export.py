"""Write synthetic clinics to disk: CSV folders for the ingest path, JSON for the dashboard."""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

from retention_radar.drafts import draft_checkin
from retention_radar.models import MemberTimeline
from retention_radar.scoring import assess, at_risk_value
from retention_radar.synth import FIRST, LAST, SimParams, SynthMember, simulate_member

WINDOW = 90


def write_clinic_csv(members: list[SynthMember], folder: str | Path, as_of: date) -> Path:
    """Write the raw activity up to ``as_of`` in the format ``load_clinic`` reads."""
    root = Path(folder)
    root.mkdir(parents=True, exist_ok=True)

    def w(name: str, header: list[str], rows: list[list]) -> None:
        with (root / name).open("w", newline="", encoding="utf-8") as f:
            out = csv.writer(f)
            out.writerow(header)
            out.writerows(rows)

    tls = [m.timeline for m in members]
    w(
        "members.csv",
        ["id", "name", "coach", "annual_value_usd", "renewal_date", "joined"],
        [
            [
                t.member.id,
                t.member.name,
                t.member.coach,
                t.member.annual_value_usd,
                t.member.renewal_date.isoformat(),
                t.joined.isoformat() if t.joined else "",
            ]
            for t in tls
        ],
    )
    w(
        "syncs.csv",
        ["member_id", "date"],
        [[t.member.id, s.day.isoformat()] for t in tls for s in t.syncs if s.day <= as_of],
    )
    msg_rows = []
    for t in tls:
        for m in t.messages:
            if m.sent_at.date() <= as_of:
                sender = "coach" if m.from_coach else "member"
                msg_rows.append([t.member.id, m.sent_at.isoformat(timespec="seconds"), sender])
    w("messages.csv", ["member_id", "sent_at", "sender"], msg_rows)
    w(
        "habits.csv",
        ["member_id", "date", "adherence"],
        [
            [t.member.id, h.day.isoformat(), round(h.adherence, 1)]
            for t in tls
            for h in t.habits
            if h.day <= as_of
        ],
    )
    w(
        "labs.csv",
        ["member_id", "scheduled", "completed"],
        [
            [
                t.member.id,
                lab.scheduled.isoformat(),
                lab.completed.isoformat() if lab.completed and lab.completed <= as_of else "",
            ]
            for t in tls
            for lab in t.labs
            if lab.scheduled <= as_of
        ],
    )
    w(
        "calls.csv",
        ["member_id", "date"],
        [[t.member.id, c.day.isoformat()] for t in tls for c in t.calls if c.day <= as_of],
    )
    return root


def demo_clinic(n: int = 42, seed: int = 22, as_of: date = date(2026, 10, 26)) -> list[SynthMember]:
    """A small clinic whose renewals all fall in the next four months."""
    rng = random.Random(seed)
    params = SimParams(churn_rate=0.3)
    out = []
    for k in range(n):
        renew_in = rng.randint(3, 120)
        joined = as_of + timedelta(days=renew_in) - timedelta(days=365)
        name = f"{FIRST[(k * 5 + 3) % len(FIRST)]} {LAST[(k * 11 + 2) % len(LAST)]}"
        out.append(simulate_member(rng, f"m-{k:04d}", name, joined, params))
    return out


def _series(t: MemberTimeline, as_of: date) -> dict:
    start = as_of - timedelta(days=WINDOW - 1)
    idx = lambda d: (d - start).days  # noqa: E731
    in_win = lambda d: start <= d <= as_of  # noqa: E731
    habit: list[float | None] = [None] * WINDOW
    for h in t.habits:
        if in_win(h.day):
            habit[idx(h.day)] = round(h.adherence, 1)
    sync = [0] * WINDOW
    for s in t.syncs:
        if in_win(s.day):
            sync[idx(s.day)] = 1
    end = as_of
    msgs = [
        {"d": idx(m.sent_at.date()), "answered": bool(m.replied_at and m.replied_at.date() <= end)}
        for m in t.messages
        if m.from_coach and in_win(m.sent_at.date())
    ]
    labs = [
        {"d": idx(lab.scheduled), "missed": not (lab.completed and lab.completed <= end)}
        for lab in t.labs
        if in_win(lab.scheduled) and lab.scheduled < as_of
    ]
    calls = [idx(c.day) for c in t.calls if in_win(c.day)]
    return {"habit": habit, "sync": sync, "messages": msgs, "labs": labs, "calls": calls}


def _flagged_since(t: MemberTimeline, as_of: date) -> int | None:
    """Days ago the member was first flagged in an unbroken run ending today."""
    if not assess(t, as_of).flagged:
        return None
    back = 0
    while back < WINDOW - 1 and assess(t, as_of - timedelta(days=back + 1)).flagged:
        back += 1
    return back


def demo_payload(members: list[SynthMember], as_of: date) -> dict:
    tls = [m.timeline for m in members]
    assessments = [assess(t, as_of) for t in tls]
    out = []
    for t, a in zip(tls, assessments, strict=True):
        out.append(
            {
                "id": t.member.id,
                "name": t.member.name,
                "coach": t.member.coach,
                "value_usd": t.member.annual_value_usd,
                "renews_in": a.days_to_renewal,
                "score": a.score,
                "band": a.band.value,
                "hits": [h.model_dump() for h in a.hits],
                "flagged_since": _flagged_since(t, as_of),
                "draft": draft_checkin(a, use_llm=False) if a.flagged else None,
                "series": _series(t, as_of),
            }
        )
    out.sort(key=lambda m: (-m["score"], m["renews_in"]))
    return {
        "synthetic": True,
        "generated_by": "retention_radar.export.demo_payload",
        "as_of": as_of.isoformat(),
        "window_days": WINDOW,
        "at_risk_usd": at_risk_value(assessments),
        "members": out,
    }


def write_demo_json(path: str | Path, as_of: date = date(2026, 10, 26)) -> dict:
    payload = demo_payload(demo_clinic(as_of=as_of), as_of)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload
