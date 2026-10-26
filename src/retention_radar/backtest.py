"""Backtest the radar against what clinics watch today.

For every simulated member we replay their year and ask, at each weekly check-in
before renewal, whether a method would have flagged them. Three methods:

* **Radar**: band is Drifting or Needs care.
* **Logins**: fewer than ``LOGIN_FLOOR`` portal logins in the last 30 days.
* **NPS**: latest survey answer was a detractor score (6 or below).

Metrics are reported at a single decision point (``DECISION_DAYS`` before renewal,
the last moment a coach can realistically act) plus how early each method first
caught a member who went on to leave.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from retention_radar.scoring import assess
from retention_radar.synth import SimParams, SynthMember, simulate_clinic

DECISION_DAYS = 30
LOOKBACK_DAYS = 120
LOGIN_FLOOR = 2

Flagger = Callable[[SynthMember, date], bool]


def radar_flag(m: SynthMember, day: date) -> bool:
    return assess(m.timeline, day).flagged


def logins_flag(m: SynthMember, day: date) -> bool:
    start = day - timedelta(days=30)
    return sum(1 for d in m.logins if start < d <= day) < LOGIN_FLOOR


def nps_flag(m: SynthMember, day: date) -> bool:
    answered = [score for d, score in m.nps if d <= day]
    return bool(answered) and answered[-1] <= 6


METHODS: dict[str, Flagger] = {"Radar": radar_flag, "Logins": logins_flag, "NPS": nps_flag}


@dataclass
class MethodResult:
    method: str
    precision: float
    recall: float
    flag_rate: float
    revenue_caught: float
    median_lead_days: float | None
    churners_caught_by_decision: int
    churners_total: int


def _safe(a: float, b: float) -> float:
    return a / b if b else 0.0


def evaluate(members: list[SynthMember], method: str, flag: Flagger) -> MethodResult:
    tp = fp = fn = 0
    caught_value = churn_value = 0
    leads: list[int] = []
    for m in members:
        renewal = m.timeline.member.renewal_date
        decision = renewal - timedelta(days=DECISION_DAYS)
        flagged = flag(m, decision)
        if m.churned:
            churn_value += m.timeline.member.annual_value_usd
            if flagged:
                tp += 1
                caught_value += m.timeline.member.annual_value_usd
            else:
                fn += 1
            # earliest weekly check that flags, scanning forward to the decision point
            for back in range(LOOKBACK_DAYS, DECISION_DAYS - 1, -7):
                if flag(m, renewal - timedelta(days=back)):
                    leads.append(back)
                    break
        elif flagged:
            fp += 1
    churners = tp + fn
    return MethodResult(
        method=method,
        precision=round(_safe(tp, tp + fp), 3),
        recall=round(_safe(tp, churners), 3),
        flag_rate=round(_safe(tp + fp, len(members)), 3),
        revenue_caught=round(_safe(caught_value, churn_value), 3),
        median_lead_days=statistics.median(leads) if leads else None,
        churners_caught_by_decision=tp,
        churners_total=churners,
    )


def threshold_sweep(members: list[SynthMember], thresholds: range = range(10, 65, 5)) -> list[dict]:
    """Precision and recall at the decision point for each radar score cut-off."""
    scored = []
    for m in members:
        decision = m.timeline.member.renewal_date - timedelta(days=DECISION_DAYS)
        scored.append((assess(m.timeline, decision).score, m.churned))
    churners = sum(c for _, c in scored)
    out = []
    for cut in thresholds:
        tp = sum(1 for s, c in scored if s >= cut and c)
        fp = sum(1 for s, c in scored if s >= cut and not c)
        out.append(
            {
                "threshold": cut,
                "precision": round(_safe(tp, tp + fp), 3),
                "recall": round(_safe(tp, churners), 3),
                "flag_rate": round(_safe(tp + fp, len(scored)), 3),
            }
        )
    return out


def run(n: int = 1000, seed: int = 7, params: SimParams | None = None) -> dict:
    members = simulate_clinic(n=n, seed=seed, params=params)
    results = [evaluate(members, name, fn) for name, fn in METHODS.items()]
    return {
        "members": n,
        "seed": seed,
        "churn_rate_observed": round(sum(m.churned for m in members) / n, 3),
        "decision_days_before_renewal": DECISION_DAYS,
        "params": asdict(params or SimParams()),
        "results": [asdict(r) for r in results],
        "radar_threshold_sweep": threshold_sweep(members),
    }


def to_markdown(report: dict) -> str:
    rows = [
        "| Method | Precision | Recall | Flagged | Revenue caught | Median lead |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["results"]:
        lead = f"{r['median_lead_days']:.0f} days" if r["median_lead_days"] else "n/a"
        rows.append(
            f"| {r['method']} | {r['precision']:.0%} | {r['recall']:.0%} | {r['flag_rate']:.0%} "
            f"| {r['revenue_caught']:.0%} | {lead} |"
        )
    return "\n".join(rows)


def plot(reports: dict[str, dict], path: str) -> None:
    """Recall and precision per method, one panel per scenario."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, mist, violet, track = "#E9EDEE", "#8A9497", "#C4B5FF", "#2A3033"
    fig, axes = plt.subplots(1, len(reports), figsize=(5.2 * len(reports), 3.6), dpi=160)
    fig.patch.set_facecolor("#050708")
    if len(reports) == 1:
        axes = [axes]
    for ax, (title, rep) in zip(axes, reports.items(), strict=True):
        ax.set_facecolor("#050708")
        names = [r["method"] for r in rep["results"]]
        rec = [r["recall"] for r in rep["results"]]
        pre = [r["precision"] for r in rep["results"]]
        y = range(len(names))
        ax.barh([i + 0.18 for i in y], rec, height=0.32, color=violet, label="Recall")
        ax.barh([i - 0.18 for i in y], pre, height=0.32, color=mist, label="Precision")
        for i, (rv, pv) in enumerate(zip(rec, pre, strict=True)):
            ax.text(rv + 0.02, i + 0.18, f"{rv:.0%}", va="center", color=ink, fontsize=8)
            ax.text(pv + 0.02, i - 0.18, f"{pv:.0%}", va="center", color=mist, fontsize=8)
        ax.set_yticks(list(y), names, color=ink, fontsize=9)
        ax.set_xlim(0, 1.12)
        ax.invert_yaxis()
        ax.tick_params(axis="x", colors=mist, labelsize=7)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(track)
        ax.set_title(title, color=ink, fontsize=10, loc="left", pad=10)
    axes[0].legend(frameon=False, labelcolor=ink, fontsize=8, loc="lower right")
    fig.text(
        0.01,
        0.01,
        "Synthetic clinic, 1,000 members. Flag checked 30 days before renewal.",
        color=mist,
        fontsize=7,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def plot_sweep(reports: dict[str, dict], path: str) -> None:
    """Precision and recall as the radar's flag threshold moves."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, mist, violet, mint, track = "#E9EDEE", "#8A9497", "#C4B5FF", "#7DE3A6", "#2A3033"
    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=160)
    fig.patch.set_facecolor("#050708")
    ax.set_facecolor("#050708")
    styles = ["-", "--"]
    for (name, rep), ls in zip(reports.items(), styles, strict=False):
        sw = rep["radar_threshold_sweep"]
        xs = [r["threshold"] for r in sw]
        ax.plot(xs, [r["recall"] for r in sw], ls, color=violet, lw=1.6, label=f"Recall · {name}")
        ax.plot(
            xs, [r["precision"] for r in sw], ls, color=mint, lw=1.6, label=f"Precision · {name}"
        )
    ax.axvline(30, color=mist, lw=0.8, ls=":")
    ax.text(30.6, 0.04, "default Drifting cut-off", color=mist, fontsize=7)
    ax.set_xlabel("Radar score threshold", color=mist, fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.tick_params(colors=mist, labelsize=7)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(track)
    ax.legend(frameon=False, labelcolor=ink, fontsize=7, loc="center right")
    ax.set_title("Where to set the flag", color=ink, fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
