"""Command line entry point: ``radar <command>``."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from retention_radar.ingest import load_clinic
from retention_radar.scoring import assess_all, at_risk_value


def _score(args: argparse.Namespace) -> None:
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    results = assess_all(load_clinic(args.folder), as_of)
    flagged = [a for a in results if a.flagged]
    if args.json:
        print(json.dumps([a.model_dump(mode="json") for a in flagged], indent=2))
        return
    print(
        f"As of {as_of}: ${at_risk_value(results):,} in renewals at risk "
        f"({len(flagged)} of {len(results)} members flagged)\n"
    )
    for a in flagged:
        reasons = ", ".join(h.short for h in a.hits)
        print(
            f"  {a.score:>3}  {a.band.value:<10}  {a.name:<22}  renews in {a.days_to_renewal:>3}d  "
            f"${a.annual_value_usd:>7,}  {reasons}"
        )


def _backtest(args: argparse.Namespace) -> None:
    from retention_radar.backtest import plot, plot_sweep, run, to_markdown
    from retention_radar.synth import SimParams

    scenarios = {
        "Default scenario": SimParams(),
        "Subtle drift (strength 0.5)": SimParams(drift_strength=0.5),
    }
    reports = {name: run(n=args.n, seed=args.seed, params=p) for name, p in scenarios.items()}
    for name, rep in reports.items():
        print(f"\n{name}  (churn {rep['churn_rate_observed']:.0%}, n={rep['members']})")
        print(to_markdown(rep))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "backtest.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
        plot(reports, str(out / "backtest.png"))
        plot_sweep(reports, str(out / "threshold_sweep.png"))
        print(f"\nWrote backtest.json, backtest.png and threshold_sweep.png to {out}")


def _demo(args: argparse.Namespace) -> None:
    from retention_radar.export import write_demo_json

    p = write_demo_json(args.out, date.fromisoformat(args.as_of))
    flagged = sum(1 for m in p["members"] if m["band"] != "steady")
    print(
        f"Wrote {args.out}: {len(p['members'])} members, {flagged} flagged, "
        f"${p['at_risk_usd']:,} at risk"
    )


def _sample(args: argparse.Namespace) -> None:
    from retention_radar.export import demo_clinic, write_clinic_csv

    as_of = date.fromisoformat(args.as_of)
    path = write_clinic_csv(demo_clinic(as_of=as_of), args.out, as_of)
    print(f"Wrote sample clinic CSVs to {path}")


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from retention_radar.api import create_app

    uvicorn.run(create_app(load_clinic(args.folder)), host=args.host, port=args.port)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="radar", description="Retention Radar")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="Score a clinic folder of CSV exports")
    s.add_argument("folder")
    s.add_argument("--as-of", help="YYYY-MM-DD, defaults to today")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_score)

    b = sub.add_parser(
        "backtest", help="Compare the radar with logins and NPS on a synthetic clinic"
    )
    b.add_argument("--n", type=int, default=1000)
    b.add_argument("--seed", type=int, default=7)
    b.add_argument("--out", help="Folder for backtest.json and backtest.png")
    b.set_defaults(func=_backtest)

    d = sub.add_parser("demo", help="Write the dashboard's demo.json")
    d.add_argument("--out", default="docs/demo.json")
    d.add_argument("--as-of", default="2026-10-26")
    d.set_defaults(func=_demo)

    c = sub.add_parser("sample", help="Write a synthetic clinic as CSV exports")
    c.add_argument("--out", default="data/sample_clinic")
    c.add_argument("--as-of", default="2026-10-26")
    c.set_defaults(func=_sample)

    v = sub.add_parser("serve", help="Run the HTTP API over a clinic folder")
    v.add_argument("folder")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8000)
    v.set_defaults(func=_serve)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
