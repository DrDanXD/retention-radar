import json
from datetime import date, datetime

from retention_radar.export import demo_clinic, write_clinic_csv
from retention_radar.ingest import (
    load_clinic,
    pair_replies,
    syncs_from_daily_csv,
    syncs_from_strava_activities,
)
from retention_radar.ingest.strava import load_strava_file
from retention_radar.scoring import assess


def test_pair_replies_marks_every_coach_message_before_a_reply():
    log = [
        (datetime(2026, 10, 1, 9), "coach"),
        (datetime(2026, 10, 3, 9), "coach"),
        (datetime(2026, 10, 3, 18), "member"),
        (datetime(2026, 10, 10, 9), "coach"),
    ]
    msgs = [m for m in pair_replies(log) if m.from_coach]
    assert msgs[0].replied_at == datetime(2026, 10, 3, 18)
    assert msgs[1].replied_at == datetime(2026, 10, 3, 18)
    assert msgs[2].replied_at is None


def test_strava_activities_become_unique_sync_days(tmp_path):
    acts = [
        {
            "name": "Morning Run",
            "start_date": "2026-10-01T06:10:00Z",
            "start_date_local": "2026-10-01T02:10:00",
        },
        {"name": "Ride", "start_date": "2026-10-01T22:00:00Z"},
        {"name": "Walk", "start_date": "2026-10-04T12:00:00Z"},
        {"name": "Manual entry, no date"},
    ]
    days = [s.day for s in syncs_from_strava_activities(acts)]
    assert days == [date(2026, 10, 1), date(2026, 10, 4)]
    path = tmp_path / "acts.json"
    path.write_text(json.dumps(acts))
    assert all(s.source == "strava" for s in load_strava_file(path))


def test_daily_csv_skips_empty_and_zero_rows(tmp_path):
    p = tmp_path / "garmin_daily.csv"
    p.write_text(
        "calendarDate,totalSteps,restingHeartRate,sleepSeconds\n"
        "2026-10-01,8123,52,27000\n"
        "2026-10-02,0,,\n"
        "2026-10-03,,,\n"
        "2026-10-04,0,51,0\n"
    )
    days = [s.day for s in syncs_from_daily_csv(p, source="garmin")]
    assert days == [date(2026, 10, 1), date(2026, 10, 4)]


def test_csv_round_trip_scores_match_in_memory(tmp_path):
    """Exporting a clinic to CSV and loading it back must not change any score."""
    as_of = date(2026, 10, 26)
    members = demo_clinic(n=20, seed=3, as_of=as_of)
    write_clinic_csv(members, tmp_path, as_of)
    loaded = {t.member.id: t for t in load_clinic(tmp_path)}
    for m in members:
        expected = assess(m.timeline, as_of)
        got = assess(loaded[m.timeline.member.id], as_of)
        assert (got.score, got.band) == (expected.score, expected.band), m.timeline.member.id
