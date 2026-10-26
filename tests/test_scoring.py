from datetime import timedelta

from retention_radar.config import Thresholds
from retention_radar.models import Band, CoachCall, LabDraw, Message, WearableSync
from retention_radar.scoring import assess, assess_all, at_risk_value, band_for

from .conftest import AS_OF, at, days_ago


def test_bands():
    assert band_for(29) is Band.STEADY
    assert band_for(30) is Band.DRIFTING
    assert band_for(54) is Band.DRIFTING
    assert band_for(55) is Band.NEEDS_CARE


def test_score_is_sum_of_hits_sorted_by_points(healthy):
    t = healthy.model_copy(
        update={
            "syncs": [WearableSync(day=days_ago(16))],
            "labs": [LabDraw(scheduled=days_ago(8))],
            "messages": [Message(sent_at=at(10), from_coach=True)],
        }
    )
    a = assess(t, AS_OF)
    assert a.score == 30 + 15 + 8
    assert [h.points for h in a.hits] == [30, 15, 8]
    assert a.band is Band.DRIFTING
    assert a.days_to_renewal == 18


def test_custom_thresholds_change_the_band(healthy):
    t = healthy.model_copy(update={"calls": [CoachCall(day=days_ago(95))]})
    assert assess(t, AS_OF).band is Band.STEADY
    strict = Thresholds(drifting_at=10)
    assert assess(t, AS_OF, strict).band is Band.DRIFTING


def test_at_risk_value_respects_horizon(healthy, member):
    risky = healthy.model_copy(update={"syncs": [WearableSync(day=days_ago(20))]})
    near = assess(risky, AS_OF)
    far_member = member.model_copy(update={"id": "m-2", "renewal_date": AS_OF + timedelta(days=90)})
    far = assess(risky.model_copy(update={"member": far_member}), AS_OF)
    calm = assess(healthy, AS_OF)
    assert near.flagged and far.flagged and not calm.flagged
    assert at_risk_value([near, far, calm]) == 32_000


def test_assess_all_orders_by_risk(healthy, member):
    risky = healthy.model_copy(
        update={"member": member.model_copy(update={"id": "m-2"}), "syncs": []}
    )
    out = assess_all([healthy, risky], AS_OF)
    assert [a.member_id for a in out] == ["m-2", "m-1"]
