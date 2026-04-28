from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import health_quantification.analysis.metrics as metrics_module
import health_quantification.cli as cli_module
from health_quantification.cli import main
from health_quantification.storage import (
    initialize_database,
    upsert_activity_samples,
    upsert_body_samples,
    upsert_lifestyle_samples,
    upsert_sleep_samples,
    upsert_vitals_samples,
    upsert_workout_samples,
)


def _local_to_utc(day_offset: int, hour: int, minute: int) -> str:
    tz = ZoneInfo("America/Los_Angeles")
    base_date = datetime.now(tz).date() - timedelta(days=2)
    local_dt = datetime.combine(base_date + timedelta(days=day_offset), datetime.min.time(), tzinfo=tz)
    local_dt = local_dt.replace(hour=hour, minute=minute)
    return local_dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_doctor_config_runs() -> None:
    exit_code = main(["doctor", "config"])
    assert exit_code == 0


def test_phase_2_cli_commands_run(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    initialize_database(db_path)

    upsert_vitals_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "vitals-1",
                "recorded_at": "2026-03-31T23:30:00Z",
                "metric_type": "resting_heart_rate",
                "value": 62.0,
                "unit": "count/min",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            }
        ],
    )
    upsert_body_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "body-1",
                "recorded_at": "2026-03-31T23:30:00Z",
                "metric_type": "body_mass",
                "value": 75.5,
                "unit": "kg",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            }
        ],
    )
    upsert_lifestyle_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "life-1",
                "recorded_at": "2026-03-31T18:00:00Z",
                "metric_type": "dietary_caffeine",
                "value": 150.0,
                "unit": "mg",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            }
        ],
    )
    upsert_activity_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "activity-1",
                "start_at": "2026-03-31T08:00:00Z",
                "end_at": "2026-03-31T09:00:00Z",
                "metric_type": "step_count",
                "value": 8500,
                "unit": "count",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            }
        ],
    )
    upsert_workout_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "workout-1",
                "workout_type": "HIIT",
                "start_at": "2026-03-31T08:00:00Z",
                "end_at": "2026-03-31T08:30:00Z",
                "duration_seconds": 1800.0,
                "total_energy_burned": 280.0,
                "total_distance_meters": None,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            }
        ],
    )

    commands = [
        (["vitals", "analyze", "--days", "30", "--metric", "resting_heart_rate", "--format", "json"], "metric_type", "resting_heart_rate"),
        (["vitals", "daily", "--date", "2026-03-31", "--format", "json"], "data_type", "vitals"),
        (["body", "analyze", "--days", "30", "--metric", "body_mass", "--format", "json"], "metric_type", "body_mass"),
        (["body", "daily", "--date", "2026-03-31", "--format", "json"], "data_type", "body"),
        (["lifestyle", "analyze", "--days", "30", "--metric", "dietary_caffeine", "--format", "json"], "metric_type", "dietary_caffeine"),
        (["lifestyle", "daily", "--date", "2026-03-31", "--format", "json"], "data_type", "lifestyle"),
        (["activity", "analyze", "--days", "30", "--metric", "step_count", "--format", "json"], "metric_type", "step_count"),
        (["activity", "daily", "--date", "2026-03-31", "--format", "json"], "data_type", "activity"),
        (["workouts", "analyze", "--days", "30", "--format", "json"], "metric_type", "duration_seconds"),
        (["workouts", "daily", "--date", "2026-03-31", "--format", "json"], "data_type", "workouts"),
    ]

    for argv, field_name, expected in commands:
        assert main(argv) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload[field_name] == expected


def test_sleep_cli_daily_outputs_sessions(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_sleep.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    initialize_database(db_path)

    upsert_sleep_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "sleep-main-1",
                "start_at": "2026-03-31T09:03:00Z",
                "end_at": "2026-03-31T10:33:00Z",
                "stage": "asleep_core",
                "stage_value": 2,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "sleep-main-2",
                "start_at": "2026-03-31T10:33:00Z",
                "end_at": "2026-03-31T11:33:00Z",
                "stage": "asleep_deep",
                "stage_value": 3,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "sleep-main-3",
                "start_at": "2026-03-31T11:33:00Z",
                "end_at": "2026-03-31T12:45:00Z",
                "stage": "asleep_rem",
                "stage_value": 4,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "sleep-nap-1",
                "start_at": "2026-03-31T19:41:00Z",
                "end_at": "2026-03-31T21:56:00Z",
                "stage": "asleep_unspecified",
                "stage_value": 5,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
        ],
    )

    assert main(["sleep", "daily", "--date", "2026-03-31", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["date"] == "2026-03-31"
    assert payload["main_sleep_hours"] == 3.7
    assert payload["nap_hours"] == 2.25
    assert payload["additional_sleep_hours"] == 0.0
    assert [session["session_type"] for session in payload["sessions"]] == ["main", "nap"]


def test_sleep_cli_analyze_outputs_functional_daily(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_sleep_analyze.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    initialize_database(db_path)
    tz = ZoneInfo("America/Los_Angeles")
    base_date = datetime.now(tz).date() - timedelta(days=2)
    second_date = base_date + timedelta(days=1)

    upsert_sleep_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "sleep-early-1",
                "start_at": _local_to_utc(0, 2, 3),
                "end_at": _local_to_utc(0, 3, 33),
                "stage": "asleep_core",
                "stage_value": 2,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "sleep-early-2",
                "start_at": _local_to_utc(0, 3, 33),
                "end_at": _local_to_utc(0, 4, 33),
                "stage": "asleep_deep",
                "stage_value": 3,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "sleep-early-3",
                "start_at": _local_to_utc(0, 4, 33),
                "end_at": _local_to_utc(0, 5, 45),
                "stage": "asleep_rem",
                "stage_value": 4,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "sleep-main-overnight",
                "start_at": _local_to_utc(0, 22, 1),
                "end_at": _local_to_utc(1, 6, 1),
                "stage": "asleep_core",
                "stage_value": 2,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
        ],
    )

    assert main(["sleep", "analyze", "--days", "3", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "functional_daily" in payload
    functional = {day["date"]: day for day in payload["functional_daily"]}
    assert functional[base_date.isoformat()]["lead_in_sleep"]["sleep_hours"] == 3.7
    assert functional[second_date.isoformat()]["lead_in_sleep"]["sleep_hours"] == 8.0


def test_sleep_cli_last_night_uses_latest_functional_sleep(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_sleep_last_night.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    initialize_database(db_path)

    tz = ZoneInfo("America/Los_Angeles")
    fake_now = datetime(2026, 4, 28, 8, 0, tzinfo=tz)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return fake_now.replace(tzinfo=None)
            return fake_now.astimezone(tz)

    monkeypatch.setattr(cli_module, "datetime", FixedDateTime)
    monkeypatch.setattr(metrics_module, "datetime", FixedDateTime)

    upsert_sleep_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "nap-yesterday",
                "start_at": "2026-04-27T21:00:00Z",
                "end_at": "2026-04-27T22:00:00Z",
                "stage": "asleep_unspecified",
                "stage_value": 5,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "last-night-1",
                "start_at": "2026-04-27T07:02:32Z",
                "end_at": "2026-04-27T07:04:01Z",
                "stage": "asleep_core",
                "stage_value": 2,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "last-night-2",
                "start_at": "2026-04-27T07:04:01Z",
                "end_at": "2026-04-27T07:06:31Z",
                "stage": "awake",
                "stage_value": 1,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "last-night-3",
                "start_at": "2026-04-27T07:06:31Z",
                "end_at": "2026-04-27T13:50:11Z",
                "stage": "asleep_core",
                "stage_value": 2,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            },
        ],
    )

    assert main(["sleep", "daily", "--last-night", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["date"] == "2026-04-27"
    assert payload["bedtime"] == "00:02"
    assert payload["main_sleep_hours"] == 6.75
    assert payload["sample_count"] == 3
    assert payload["nap_hours"] == 0.0
    assert len(payload["sessions"]) == 1
    assert payload["sessions"][0]["session_type"] == "main"


def test_activity_daily_outputs_step_estimate_for_overlapping_sources(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_steps_daily.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    initialize_database(db_path)

    upsert_activity_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "watch-1",
                "start_at": "2026-04-12T08:00:00Z",
                "end_at": "2026-04-12T09:00:00Z",
                "metric_type": "step_count",
                "value": 6000,
                "unit": "count",
                "source_bundle_id": "com.apple.health.watch",
                "source_name": "Yan's Apple Watch",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "watch-2",
                "start_at": "2026-04-12T10:00:00Z",
                "end_at": "2026-04-12T11:00:00Z",
                "metric_type": "step_count",
                "value": 4454,
                "unit": "count",
                "source_bundle_id": "com.apple.health.watch",
                "source_name": "Yan's Apple Watch",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "phone-1",
                "start_at": "2026-04-12T08:00:00Z",
                "end_at": "2026-04-12T09:00:00Z",
                "metric_type": "step_count",
                "value": 5000,
                "unit": "count",
                "source_bundle_id": "com.apple.health.phone",
                "source_name": "Ether",
                "metadata": {},
            },
            {
                "source": "apple_health_ios",
                "source_id": "phone-2",
                "start_at": "2026-04-12T10:00:00Z",
                "end_at": "2026-04-12T11:00:00Z",
                "metric_type": "step_count",
                "value": 4676,
                "unit": "count",
                "source_bundle_id": "com.apple.health.phone",
                "source_name": "Ether",
                "metadata": {},
            },
        ],
    )

    assert main(["activity", "daily", "--date", "2026-04-12", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    metric = payload["metrics"][0]
    assert metric["metric_type"] == "step_count"
    assert metric["step_estimate"]["estimated_steps"] == 10977
    assert metric["step_estimate"]["method"] == "overlapping_sources_max_times_1.05"
    assert metric["step_estimate"]["source_daily_totals"] == [
        {"source_name": "Yan's Apple Watch", "steps": 10454.0},
        {"source_name": "Ether", "steps": 9676.0},
    ]


def test_activity_analyze_outputs_step_estimate_for_step_count(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_steps_analyze.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    initialize_database(db_path)

    tz = ZoneInfo("America/Los_Angeles")
    fake_now = datetime(2026, 4, 13, 12, 0, tzinfo=tz)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return fake_now.replace(tzinfo=None)
            return fake_now.astimezone(tz)

    monkeypatch.setattr(cli_module, "datetime", FixedDateTime)
    monkeypatch.setattr(metrics_module, "datetime", FixedDateTime)

    upsert_activity_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "watch-single",
                "start_at": "2026-04-13T08:00:00Z",
                "end_at": "2026-04-13T09:00:00Z",
                "metric_type": "step_count",
                "value": 8000,
                "unit": "count",
                "source_bundle_id": "com.apple.health.watch",
                "source_name": "Yan's Apple Watch",
                "metadata": {},
            }
        ],
    )

    assert main(["activity", "analyze", "--days", "1", "--metric", "step_count", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["daily"][0]["step_estimate"]["estimated_steps"] == 8000
    assert payload["daily"][0]["step_estimate"]["method"] == "single_source_total"
