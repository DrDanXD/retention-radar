from datetime import date

import pytest

from retention_radar.backtest import evaluate, nps_flag, radar_flag, threshold_sweep
from retention_radar.drafts import _clean, draft_checkin, template_draft
from retention_radar.models import WearableSync
from retention_radar.scoring import assess
from retention_radar.synth import SimParams, simulate_clinic

from .conftest import AS_OF, days_ago


def test_template_draft_is_personal_and_on_voice(healthy):
    t = healthy.model_copy(update={"syncs": [WearableSync(day=days_ago(16))]})
    text = template_draft(assess(t, AS_OF))
    assert text.startswith("Hi Elena, Dana here.")
    assert "a couple of weeks" in text
    assert "—" not in text and "score" not in text.lower()


def test_draft_falls_back_to_template_without_key(healthy, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    a = assess(healthy, AS_OF)
    assert draft_checkin(a) == template_draft(a)


def test_clean_strips_dashes_and_quotes():
    assert _clean('"Hi Sam — quick one."') == "Hi Sam. quick one."


def test_simulator_is_deterministic():
    a = simulate_clinic(n=15, seed=4)
    b = simulate_clinic(n=15, seed=4)
    assert [m.churned for m in a] == [m.churned for m in b]
    assert [len(m.timeline.syncs) for m in a] == [len(m.timeline.syncs) for m in b]


def test_backtest_metrics_are_well_formed():
    members = simulate_clinic(n=120, seed=1)
    for name, fn in (("Radar", radar_flag), ("NPS", nps_flag)):
        r = evaluate(members, name, fn)
        assert 0 <= r.precision <= 1 and 0 <= r.recall <= 1
        assert r.churners_total == sum(m.churned for m in members)
    sweep = threshold_sweep(members)
    recalls = [s["recall"] for s in sweep]
    assert recalls == sorted(recalls, reverse=True), "raising the cut-off can never add recall"


def test_no_drift_means_radar_has_no_edge():
    """Sanity check on the simulator: with zero drift the radar should not find churners."""
    members = simulate_clinic(n=300, seed=2, params=SimParams(drift_strength=0.0))
    r = evaluate(members, "Radar", radar_flag)
    assert r.recall < 0.15


fastapi = pytest.importorskip("fastapi")


def test_api_endpoints(healthy, member):
    from fastapi.testclient import TestClient

    from retention_radar.api import create_app

    risky = healthy.model_copy(
        update={"member": member.model_copy(update={"id": "m-2", "name": "Rob Lee"}), "syncs": []}
    )
    client = TestClient(create_app([healthy, risky]))
    assert client.get("/health").json() == {"status": "ok"}
    body = client.get("/members/at-risk", params={"as_of": AS_OF.isoformat()}).json()
    assert [m["member_id"] for m in body["members"]] == ["m-2"]
    assert body["at_risk_usd"] == 32_000
    assert client.get("/members/m-1", params={"as_of": "2026-10-26"}).json()["band"] == "steady"
    assert client.get("/members/nope").status_code == 404
    draft = client.get("/members/m-2/draft", params={"as_of": date(2026, 10, 26).isoformat()})
    assert draft.json()["draft"].startswith("Hi Rob")
