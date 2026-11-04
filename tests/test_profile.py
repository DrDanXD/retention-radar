from datetime import date

from pydantic import Field

from retention_radar import DEFAULT_PROFILE, Band, Profile, SignalHit, assess, assess_all
from retention_radar.config import Thresholds
from retention_radar.models import MemberTimeline

from .conftest import AS_OF


class StrictThresholds(Thresholds):
    always_points: int = Field(default=60)


def always_flag(t: MemberTimeline, as_of: date, cfg: StrictThresholds) -> SignalHit:
    return SignalHit(signal="always", points=cfg.always_points, detail="test", short="test")


PROFILE = Profile(name="test", signals=(always_flag,), thresholds=StrictThresholds())


def test_assess_all_uses_profile_signals(healthy, member):
    other = healthy.model_copy(update={"member": member.model_copy(update={"id": "m-2"})})
    default = assess_all([healthy, other], AS_OF)
    custom = assess_all([healthy, other], AS_OF, profile=PROFILE)
    assert all(a.band is Band.STEADY for a in default)
    assert all(a.band is Band.NEEDS_CARE and a.score == 60 for a in custom)
    assert custom[0].hits[0].signal == "always"


def test_profile_thresholds_reach_custom_signals(healthy):
    tuned = Profile(name="t", signals=(always_flag,), thresholds=StrictThresholds(always_points=31))
    assert assess(healthy, AS_OF, profile=tuned).band is Band.DRIFTING


def test_default_profile_matches_plain_call(healthy):
    assert assess(healthy, AS_OF, profile=DEFAULT_PROFILE) == assess(healthy, AS_OF)
