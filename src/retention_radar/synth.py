"""Synthetic clinic generator.

Real member data is protected health information, so the repo ships with a
simulator instead. It produces a year of daily activity per member plus ground
truth (did they renew) and the two metrics clinics usually watch today: portal
logins and quarterly NPS.

**Read this before trusting any number from it.** The simulator encodes a
hypothesis: members who are going to leave change their behaviour in the months
before renewal, and that change shows up in day-to-day signals sooner than in
logins or surveys. Every parameter below is an assumption, listed in
``SimParams``, not a measured fact. The backtest therefore tests the pipeline and
shows how sensitive the method is to that hypothesis. It does not prove the
hypothesis. That needs real clinic data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from retention_radar.ingest.clinic_csv import pair_replies
from retention_radar.models import (
    CoachCall,
    HabitLog,
    LabDraw,
    Member,
    MemberTimeline,
    WearableSync,
)

FIRST = [
    "Ava",
    "Noah",
    "Chloe",
    "Ethan",
    "Maya",
    "Lucas",
    "Zoe",
    "Owen",
    "Isla",
    "Leo",
    "Nora",
    "Caleb",
    "Ruby",
    "Felix",
    "Hana",
    "Jonah",
    "Lila",
    "Theo",
    "Iris",
    "Ezra",
    "June",
    "Miles",
    "Cora",
    "Adrian",
    "Esme",
    "Hugo",
    "Vera",
    "Silas",
    "Pia",
    "Rowan",
    "Tara",
    "Kai",
    "Elena",
    "Rob",
    "Priya",
    "Mei",
    "Sofia",
    "James",
    "Tom",
    "Daniel",
    "Aisha",
    "Grant",
    "Nadia",
    "Omar",
    "Clara",
    "Victor",
    "Lena",
    "Marco",
    "Ines",
    "Raj",
]
LAST = [
    "Holt",
    "Nakamura",
    "Silva",
    "Pryor",
    "Adler",
    "Moreau",
    "Quinn",
    "Desai",
    "Farrow",
    "Lund",
    "Ortiz",
    "Hale",
    "Iyer",
    "Vance",
    "Sato",
    "Blake",
    "Romero",
    "Keller",
    "Ahmed",
    "Novak",
    "Price",
    "Laurent",
    "Cho",
    "Mercer",
    "Ibarra",
    "Wolfe",
    "Banerjee",
    "Strand",
    "Duarte",
    "Rhee",
    "Paige",
    "Lowe",
    "Marsh",
    "Castellano",
    "Natarajan",
    "Okafor",
    "Reyes",
    "Whitfield",
    "Brandt",
    "Kim",
    "Bello",
]
COACHES = ("Dana", "Marcus", "Leah")


@dataclass(frozen=True)
class SimParams:
    churn_rate: float = 0.22
    """Share of members who will not renew. Assumption."""

    drift_strength: float = 1.0
    """How strongly churners' behaviour shifts. 1.0 is the default scenario,
    lower values make churners look more like everyone else."""

    drift_lead_days: tuple[int, int] = (40, 130)
    """Drift starts this many days before renewal, uniform. Assumption."""

    sync_rate: tuple[float, float] = (0.86, 0.98)
    travel_gaps_per_year: float = 1.6
    travel_gap_days: tuple[int, int] = (4, 12)

    habit_baseline: tuple[float, float] = (55, 90)
    habit_noise: float = 9
    habit_log_rate: float = 0.9

    coach_msg_every_days: float = 9
    reply_rate: tuple[float, float] = (0.78, 0.97)
    lab_every_days: int = 90
    lab_completion: float = 0.92
    call_every_days: tuple[int, int] = (28, 45)
    call_completion: float = 0.9

    logins_per_week: tuple[float, float] = (0.5, 4.0)
    login_drop_in_drift: float = 0.25
    """Churners log in this much less while drifting. Small on purpose: members
    still open the portal to read results while they are deciding to leave."""

    nps_every_days: int = 90
    nps_response_rate: float = 0.4
    nps_mean: tuple[float, float] = (8.6, 7.7)
    """Mean NPS answer for renewers and for churners."""

    value_usd: tuple[int, int] = (12_000, 48_000)


@dataclass
class SynthMember:
    timeline: MemberTimeline
    churned: bool
    drift_start: date | None
    logins: list[date] = field(default_factory=list)
    nps: list[tuple[date, int]] = field(default_factory=list)


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def simulate_member(
    rng: random.Random,
    member_id: str,
    name: str,
    joined: date,
    params: SimParams,
    churned: bool | None = None,
) -> SynthMember:
    p = params
    renewal = joined + timedelta(days=365)
    if churned is None:
        churned = rng.random() < p.churn_rate
    lead = rng.randint(*p.drift_lead_days)
    drift_start = renewal - timedelta(days=lead) if churned else None
    s = p.drift_strength

    sync_rate = rng.uniform(*p.sync_rate)
    habit_base = rng.uniform(*p.habit_baseline)
    reply_rate = rng.uniform(*p.reply_rate)
    login_rate = rng.uniform(*p.logins_per_week) / 7
    habit_target_drop = rng.uniform(20, 45) * s
    drawer_day = None
    if churned and rng.random() < 0.55 * s:
        drawer_day = drift_start + timedelta(days=rng.randint(0, max(1, lead - 10)))

    # pre-plan travel gaps for everyone
    gaps: set[date] = set()
    n_gaps = sum(1 for _ in range(4) if rng.random() < p.travel_gaps_per_year / 4)
    for _ in range(n_gaps):
        g0 = joined + timedelta(days=rng.randint(20, 340))
        for k in range(rng.randint(*p.travel_gap_days)):
            gaps.add(g0 + timedelta(days=k))

    syncs, habits, raw_msgs, labs, calls, logins, nps = [], [], [], [], [], [], []
    next_call = joined + timedelta(days=rng.randint(7, 21))
    next_lab = joined + timedelta(days=rng.randint(10, 30))
    next_nps = joined + timedelta(days=rng.randint(30, p.nps_every_days))

    for i in range(365):
        day = joined + timedelta(days=i)
        drifting = churned and day >= drift_start
        frac = ((day - drift_start).days / max(1, lead)) if drifting else 0.0

        # wearable
        rate = sync_rate * (1 - 0.8 * s * frac) if drifting else sync_rate
        if drawer_day and day >= drawer_day:
            rate = 0.0  # device in a drawer: it stops syncing entirely
        if day not in gaps and rng.random() < rate:
            syncs.append(WearableSync(day=day))

        # habits
        log_rate = p.habit_log_rate * (1 - 0.6 * s * frac)
        if rng.random() < log_rate:
            level = habit_base - habit_target_drop * frac
            habits.append(
                HabitLog(day=day, adherence=_clip(rng.gauss(level, p.habit_noise), 0, 100))
            )

        # coach messages and replies
        if rng.random() < 1 / p.coach_msg_every_days:
            sent = datetime.combine(day, time(rng.randint(8, 18), rng.randint(0, 59)))
            rr = reply_rate * (1 - 0.7 * s * frac)
            raw_msgs.append((sent, "coach"))
            if rng.random() < rr:
                raw_msgs.append((sent + timedelta(hours=rng.uniform(1, 40)), "member"))

        # labs
        if day == next_lab:
            done_p = p.lab_completion * (1 - 0.5 * s * frac)
            completed = day + timedelta(days=rng.randint(0, 3)) if rng.random() < done_p else None
            labs.append(LabDraw(scheduled=day, completed=completed))
            next_lab = day + timedelta(days=p.lab_every_days)

        # coach calls
        if day >= next_call:
            done_p = p.call_completion * (1 - 0.65 * s * frac)
            if rng.random() < done_p:
                calls.append(CoachCall(day=day))
            next_call = day + timedelta(days=rng.randint(*p.call_every_days))

        # baselines clinics watch today
        lr = login_rate * (1 - p.login_drop_in_drift * s) if drifting else login_rate
        if rng.random() < lr:
            logins.append(day)
        if day >= next_nps:
            if rng.random() < p.nps_response_rate:
                mean = p.nps_mean[1] if churned else p.nps_mean[0]
                nps.append((day, round(_clip(rng.gauss(mean, 1.5), 0, 10))))
            next_nps = day + timedelta(days=p.nps_every_days)

    # Same reply semantics as the CSV adapter: a member message answers every
    # coach message before it. So "unanswered" means the member went quiet.
    msgs = pair_replies(raw_msgs)

    member = Member(
        id=member_id,
        name=name,
        coach=COACHES[int(member_id.split("-")[-1]) % len(COACHES)],
        annual_value_usd=round(rng.randint(*p.value_usd), -3),
        renewal_date=renewal,
    )
    timeline = MemberTimeline(
        member=member,
        joined=joined,
        syncs=syncs,
        messages=msgs,
        habits=habits,
        labs=labs,
        calls=calls,
    )
    return SynthMember(timeline, churned, drift_start, logins, nps)


def simulate_clinic(
    n: int = 1000,
    seed: int = 7,
    params: SimParams | None = None,
    first_join: date = date(2025, 1, 1),
    join_spread_days: int = 180,
) -> list[SynthMember]:
    rng = random.Random(seed)
    params = params or SimParams()
    out = []
    for k in range(n):
        name = f"{FIRST[k % len(FIRST)]} {LAST[(k * 7) % len(LAST)]}"
        joined = first_join + timedelta(days=rng.randint(0, join_spread_days))
        out.append(simulate_member(rng, f"m-{k:04d}", name, joined, params))
    return out
