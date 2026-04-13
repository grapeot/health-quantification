from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from health_quantification.analysis.sleep import (
    compute_analysis,
    compute_day_metrics,
)


def _make_sample(
    source_id: str,
    start_at: str,
    end_at: str,
    stage: str,
    stage_value: int = 0,
) -> dict[str, object]:
    return {
        "source": "test",
        "source_id": source_id,
        "start_at": start_at,
        "end_at": end_at,
        "stage": stage,
        "stage_value": stage_value,
        "source_bundle_id": "com.apple.health",
        "source_name": "Test",
        "metadata_json": "{}",
    }


def _local_to_utc(day_offset: int, hour: int, minute: int) -> str:
    tz = ZoneInfo("America/Los_Angeles")
    base_date = datetime.now(tz).date() - timedelta(days=2)
    local_dt = datetime.combine(base_date + timedelta(days=day_offset), datetime.min.time(), tzinfo=tz)
    local_dt = local_dt.replace(hour=hour, minute=minute)
    return local_dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_compute_day_metrics_basic() -> None:
    samples = [
        _make_sample("s1", "2026-03-29T22:30:00Z", "2026-03-29T23:00:00Z", "in_bed", 0),
        _make_sample("s2", "2026-03-29T23:00:00Z", "2026-03-30T00:30:00Z", "asleep_core", 2),
        _make_sample("s3", "2026-03-30T00:30:00Z", "2026-03-30T01:30:00Z", "asleep_deep", 3),
        _make_sample("s4", "2026-03-30T01:30:00Z", "2026-03-30T02:00:00Z", "asleep_rem", 4),
        _make_sample("s5", "2026-03-30T06:30:00Z", "2026-03-30T07:00:00Z", "awake", 1),
    ]
    metrics = compute_day_metrics(samples, "2026-03-29", "America/Los_Angeles")
    assert metrics.date == "2026-03-29"
    assert metrics.timezone == "America/Los_Angeles"
    assert metrics.total_sleep_hours > 0
    assert metrics.deep_sleep_hours == 1.0
    assert metrics.core_sleep_hours == 1.5
    assert metrics.rem_sleep_hours == 0.5
    assert metrics.sample_count == 5


def test_compute_day_metrics_empty() -> None:
    metrics = compute_day_metrics([], "2026-03-29", "America/Los_Angeles")
    assert metrics.date == "2026-03-29"
    assert metrics.sample_count == 0
    assert metrics.total_sleep_hours == 0.0
    assert metrics.nap_hours == 0.0
    assert metrics.bedtime is None
    assert metrics.wake_time is None
    assert metrics.sleep_efficiency is None
    assert metrics.sessions == []


def test_compute_day_metrics_nap_detection() -> None:
    samples = [
        _make_sample("n1", "2026-03-29T21:12:00Z", "2026-03-29T22:12:00Z", "asleep_unspecified", 5),
    ]
    metrics = compute_day_metrics(samples, "2026-03-29", "America/Los_Angeles")
    assert metrics.has_nap is True
    assert metrics.total_sleep_hours == 1.0
    assert metrics.main_sleep_hours == 0.0
    assert metrics.nap_hours == 1.0
    assert metrics.sessions is not None
    assert len(metrics.sessions) == 1
    assert metrics.sessions[0].session_type == "nap"


def test_compute_day_metrics_no_nap() -> None:
    samples = [
        _make_sample("s1", "2026-03-29T22:00:00Z", "2026-03-29T22:30:00Z", "in_bed", 0),
        _make_sample("s2", "2026-03-29T22:30:00Z", "2026-03-30T05:30:00Z", "asleep_core", 2),
        _make_sample("s3", "2026-03-30T05:30:00Z", "2026-03-30T06:00:00Z", "awake", 1),
    ]
    metrics = compute_day_metrics(samples, "2026-03-29", "America/Los_Angeles")
    assert metrics.has_nap is False
    assert metrics.nap_hours == 0.0


def test_compute_day_metrics_overnight_not_nap() -> None:
    samples = [
        _make_sample("s1", "2026-03-29T22:30:00Z", "2026-03-30T02:30:00Z", "asleep_core", 2),
    ]
    metrics = compute_day_metrics(samples, "2026-03-29", "America/Los_Angeles")
    assert metrics.has_nap is False
    assert metrics.total_sleep_hours == 4.0
    assert metrics.nap_hours == 0.0


def test_compute_day_metrics_main_sleep_and_afternoon_nap() -> None:
    samples = [
        _make_sample("m1", "2026-03-31T09:03:00Z", "2026-03-31T10:33:00Z", "asleep_core", 2),
        _make_sample("m2", "2026-03-31T10:33:00Z", "2026-03-31T11:33:00Z", "asleep_deep", 3),
        _make_sample("m3", "2026-03-31T11:33:00Z", "2026-03-31T12:45:00Z", "asleep_rem", 4),
        _make_sample("n1", "2026-03-31T19:41:00Z", "2026-03-31T21:56:00Z", "asleep_unspecified", 5),
    ]
    metrics = compute_day_metrics(samples, "2026-03-31", "America/Los_Angeles")
    assert metrics.bedtime == "02:03"
    assert metrics.wake_time == "05:45"
    assert metrics.total_sleep_hours == 5.95
    assert metrics.nap_hours == 2.25
    assert metrics.additional_sleep_hours == 0.0
    assert metrics.has_nap is True
    assert metrics.lead_in_sleep is not None
    assert metrics.lead_in_sleep.sleep_hours == 3.7
    assert metrics.lead_in_sleep.session_type == "main"
    assert metrics.sessions is not None
    assert [session.session_type for session in metrics.sessions] == ["main", "nap"]
    assert metrics.sessions[0].start_local == "2026-03-31T02:03:00-07:00"
    assert metrics.sessions[1].start_local == "2026-03-31T12:41:00-07:00"


def test_compute_day_metrics_main_sleep_and_staged_nap() -> None:
    samples = [
        _make_sample("m1", "2026-03-14T06:00:00Z", "2026-03-14T08:00:00Z", "asleep_core", 2),
        _make_sample("m2", "2026-03-14T08:00:00Z", "2026-03-14T09:00:00Z", "asleep_deep", 3),
        _make_sample("m3", "2026-03-14T09:00:00Z", "2026-03-14T10:00:00Z", "asleep_rem", 4),
        _make_sample("n1", "2026-03-14T18:30:00Z", "2026-03-14T19:00:00Z", "asleep_core", 2),
        _make_sample("n2", "2026-03-14T19:00:00Z", "2026-03-14T19:15:00Z", "asleep_deep", 3),
        _make_sample("n3", "2026-03-14T19:15:00Z", "2026-03-14T19:30:00Z", "asleep_rem", 4),
    ]
    metrics = compute_day_metrics(samples, "2026-03-14", "America/Los_Angeles")
    assert metrics.total_sleep_hours == 5.0
    assert metrics.deep_sleep_hours == 1.0
    assert metrics.core_sleep_hours == 2.0
    assert metrics.rem_sleep_hours == 1.0
    assert metrics.nap_hours == 1.0
    assert metrics.has_nap is True
    assert metrics.sessions is not None
    assert [session.session_type for session in metrics.sessions] == ["main", "nap"]
    assert metrics.sessions[1].deep_sleep_hours == 0.25


def test_compute_day_metrics_multiple_naps_accumulate_nap_hours() -> None:
    samples = [
        _make_sample("m1", "2026-03-16T06:00:00Z", "2026-03-16T09:00:00Z", "asleep_core", 2),
        _make_sample("m2", "2026-03-16T09:00:00Z", "2026-03-16T11:00:00Z", "asleep_rem", 4),
        _make_sample("n1", "2026-03-16T18:00:00Z", "2026-03-16T18:30:00Z", "asleep_unspecified", 5),
        _make_sample("n2", "2026-03-16T22:00:00Z", "2026-03-16T22:45:00Z", "asleep_unspecified", 5),
    ]
    metrics = compute_day_metrics(samples, "2026-03-16", "America/Los_Angeles")
    assert metrics.total_sleep_hours == 6.25
    assert metrics.nap_hours == 1.25
    assert metrics.has_nap is True
    assert metrics.sessions is not None
    assert [session.session_type for session in metrics.sessions] == ["main", "nap", "nap"]


def test_compute_day_metrics_nap_only_day() -> None:
    samples = [
        _make_sample("n1", "2026-03-15T20:00:00Z", "2026-03-15T21:00:00Z", "asleep_unspecified", 5),
    ]
    metrics = compute_day_metrics(samples, "2026-03-15", "America/Los_Angeles")
    assert metrics.total_sleep_hours == 1.0
    assert metrics.main_sleep_hours == 0.0
    assert metrics.nap_hours == 1.0
    assert metrics.has_nap is True
    assert metrics.sessions is not None
    assert metrics.sessions[0].session_type == "nap"


def test_compute_day_metrics_brief_gap_not_false_nap() -> None:
    samples = [
        _make_sample("s1", "2026-03-20T06:00:00Z", "2026-03-20T08:00:00Z", "asleep_core", 2),
        _make_sample("s2", "2026-03-20T09:00:00Z", "2026-03-20T11:00:00Z", "asleep_rem", 4),
    ]
    metrics = compute_day_metrics(samples, "2026-03-20", "America/Los_Angeles")
    assert metrics.total_sleep_hours == 4.0
    assert metrics.nap_hours == 0.0
    assert metrics.has_nap is False
    assert metrics.wake_time == "04:00"


def test_compute_analysis_summary() -> None:
    tz = ZoneInfo("America/Los_Angeles")
    base_date = datetime.now(tz).date() - timedelta(days=2)
    samples = [
        _make_sample("s1", _local_to_utc(0, 7, 0), _local_to_utc(0, 8, 0), "in_bed", 0),
        _make_sample("s2", _local_to_utc(0, 8, 0), _local_to_utc(0, 15, 0), "asleep_core", 2),
        _make_sample("s3", _local_to_utc(1, 7, 0), _local_to_utc(1, 8, 0), "in_bed", 0),
        _make_sample("s4", _local_to_utc(1, 8, 0), _local_to_utc(2, 15, 0), "asleep_core", 2),
    ]
    analysis = compute_analysis(samples, days=3, tz_name="America/Los_Angeles")
    assert analysis.total_samples == 4
    assert analysis.days_with_data == 2
    assert analysis.avg_sleep_hours > 0
    assert len(analysis.daily) == 3
    assert base_date.isoformat() in [day.date for day in analysis.daily]


def test_compute_analysis_to_dict() -> None:
    samples = [
        _make_sample("s1", "2026-03-29T22:00:00Z", "2026-03-29T22:30:00Z", "in_bed", 0),
        _make_sample("s2", "2026-03-29T22:30:00Z", "2026-03-30T06:30:00Z", "asleep_core", 2),
    ]
    analysis = compute_analysis(samples, days=30, tz_name="America/Los_Angeles")
    d = analysis.to_dict()
    assert "daily" in d
    assert "avg_sleep_hours" in d
    assert analysis.days_with_data == 1
    daily = cast(list[dict[str, object]], d["daily"])
    days_with_sleep = [
        day
        for day in daily
        if float(cast(int | float, day["total_sleep_hours"])) > 0
    ]
    assert len(days_with_sleep) == 1


def test_assign_samples_to_days_cross_midnight() -> None:
    from health_quantification.analysis.sleep import assign_samples_to_days

    # Sleep from 22:01 PT to 06:58 PT (crosses midnight).
    # All samples should be assigned to 2026-03-31 (bedtime date),
    # not split across 3/31 and 4/1.
    samples = [
        _make_sample("s1", "2026-04-01T05:01:48Z", "2026-04-01T05:28:17Z", "asleep_core", 2),
        _make_sample("s2", "2026-04-01T05:28:17Z", "2026-04-01T05:30:17Z", "asleep_deep", 3),
        _make_sample("s3", "2026-04-01T05:30:17Z", "2026-04-01T13:58:51Z", "asleep_core", 2),
    ]
    days = assign_samples_to_days(samples, "America/Los_Angeles")
    assert "2026-03-31" in days
    assert len(days["2026-03-31"]) == 3
    assert "2026-04-01" not in days

    metrics = compute_day_metrics(days["2026-03-31"], "2026-03-31", "America/Los_Angeles")
    assert metrics.bedtime == "22:01"
    assert metrics.sample_count == 3


def test_assign_samples_to_days_after_midnight_session() -> None:
    from health_quantification.analysis.sleep import assign_samples_to_days

    # Sleep starting at 01:00 PT (after midnight) should be assigned to that date,
    # not the previous day.
    samples = [
        _make_sample("s1", "2026-04-01T08:00:00Z", "2026-04-01T09:00:00Z", "asleep_core", 2),
        _make_sample("s2", "2026-04-01T09:00:00Z", "2026-04-01T10:00:00Z", "asleep_deep", 3),
    ]
    days = assign_samples_to_days(samples, "America/Los_Angeles")
    assert "2026-04-01" in days
    assert len(days["2026-04-01"]) == 2
    assert "2026-03-31" not in days

    metrics = compute_day_metrics(days["2026-04-01"], "2026-04-01", "America/Los_Angeles")
    assert metrics.bedtime == "01:00"


def test_compute_day_metrics_separates_additional_sleep_from_nap() -> None:
    samples = [
        _make_sample("a1", "2026-03-31T09:03:00Z", "2026-03-31T10:33:00Z", "asleep_core", 2),
        _make_sample("a2", "2026-03-31T10:33:00Z", "2026-03-31T11:33:00Z", "asleep_deep", 3),
        _make_sample("a3", "2026-03-31T11:33:00Z", "2026-03-31T12:45:00Z", "asleep_rem", 4),
        _make_sample("b1", "2026-03-31T19:41:00Z", "2026-03-31T21:56:00Z", "asleep_unspecified", 5),
        _make_sample("c1", "2026-04-01T05:01:48Z", "2026-04-01T06:01:48Z", "asleep_core", 2),
        _make_sample("c2", "2026-04-01T06:01:48Z", "2026-04-01T13:01:48Z", "asleep_rem", 4),
    ]
    metrics = compute_day_metrics(samples, "2026-03-31", "America/Los_Angeles")
    assert metrics.main_sleep_hours == 8.0
    assert metrics.nap_hours == 2.25
    assert metrics.additional_sleep_hours == 3.7
    assert metrics.total_sleep_hours == 13.95
    assert metrics.sessions is not None
    assert [session.session_type for session in metrics.sessions] == ["additional_sleep", "nap", "main"]
    assert metrics.lead_in_sleep is not None
    assert metrics.lead_in_sleep.sleep_hours == 3.7
    assert metrics.lead_in_sleep.session_type == "additional_sleep"


def test_compute_analysis_functional_daily_captures_bad_night() -> None:
    tz = ZoneInfo("America/Los_Angeles")
    base_date = datetime.now(tz).date() - timedelta(days=2)
    second_date = base_date + timedelta(days=1)
    samples = [
        _make_sample("a1", _local_to_utc(0, 2, 3), _local_to_utc(0, 3, 33), "asleep_core", 2),
        _make_sample("a2", _local_to_utc(0, 3, 33), _local_to_utc(0, 4, 33), "asleep_deep", 3),
        _make_sample("a3", _local_to_utc(0, 4, 33), _local_to_utc(0, 5, 45), "asleep_rem", 4),
        _make_sample("b1", _local_to_utc(0, 12, 41), _local_to_utc(0, 14, 56), "asleep_unspecified", 5),
        _make_sample("c1", _local_to_utc(0, 22, 1), _local_to_utc(0, 23, 1), "asleep_core", 2),
        _make_sample("c2", _local_to_utc(0, 23, 1), _local_to_utc(1, 6, 1), "asleep_rem", 4),
        _make_sample("d1", _local_to_utc(1, 23, 10), _local_to_utc(2, 6, 30), "asleep_core", 2),
    ]
    analysis = compute_analysis(samples, days=3, tz_name="America/Los_Angeles")
    functional_by_date = {day.date: day for day in analysis.functional_daily}
    first_lead_in = functional_by_date[base_date.isoformat()].lead_in_sleep
    second_lead_in = functional_by_date[second_date.isoformat()].lead_in_sleep
    assert first_lead_in is not None
    assert first_lead_in.sleep_hours == 3.7
    assert second_lead_in is not None
    assert second_lead_in.sleep_hours == 8.0
