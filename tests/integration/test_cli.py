from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import health_quantification.analysis.metrics as metrics_module
import health_quantification.cli as cli_module
from health_quantification.cli import main
from health_quantification.storage import (
    append_daily_note,
    initialize_database,
    upsert_activity_samples,
    upsert_body_samples,
    upsert_lifestyle_samples,
    upsert_ecg_records,
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
    assert append_daily_note(
        db_path, "2026-03-31", "America/Los_Angeles", "Synthetic daily context"
    ) == 1

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
    assert payload["notes"] == ["Synthetic daily context"]
    assert [session["session_type"] for session in payload["sessions"]] == ["main", "nap"]


def test_sleep_cli_analyze_outputs_daily(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_sleep_analyze.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    initialize_database(db_path)
    tz = ZoneInfo("America/Los_Angeles")
    base_date = datetime.now(tz).date() - timedelta(days=2)
    second_date = base_date + timedelta(days=1)
    assert append_daily_note(db_path, second_date.isoformat(), "America/Los_Angeles", "Synthetic analysis context") == 1

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
    assert "daily" in payload
    daily = {day["date"]: day for day in payload["daily"]}
    assert daily[base_date.isoformat()]["main_sleep_hours"] == 3.7
    assert daily[second_date.isoformat()]["main_sleep_hours"] == 8.0
    assert daily[base_date.isoformat()]["notes"] == []
    assert daily[second_date.isoformat()]["notes"] == ["Synthetic analysis context"]


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
    assert payload["sample_count"] == 4
    assert payload["nap_hours"] == 1.0
    assert len(payload["sessions"]) == 2
    session_types = [s["session_type"] for s in payload["sessions"]]
    assert "main" in session_types
    assert "nap" in session_types


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
                "source_name": "Example Watch",
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
                "source_name": "Example Watch",
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
                "source_name": "Example Phone",
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
                "source_name": "Example Phone",
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
        {"source_name": "Example Watch", "steps": 10454.0},
        {"source_name": "Example Phone", "steps": 9676.0},
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
                "source_name": "Example Watch",
                "metadata": {},
            }
        ],
    )

    assert main(["activity", "analyze", "--days", "1", "--metric", "step_count", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["daily"][0]["step_estimate"]["estimated_steps"] == 8000
    assert payload["daily"][0]["step_estimate"]["method"] == "single_source_total"


def test_ecg_cli_list_hides_voltage_and_export_writes_file(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    initialize_database(db_path)
    upsert_ecg_records(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "ecg-cli-1",
                "start_at": "2026-03-31T02:00:00Z",
                "end_at": "2026-03-31T02:00:30Z",
                "algorithm_classification": "sinus_rhythm",
                "algorithm_classification_value": 1,
                "symptoms_status": "none",
                "symptoms_status_value": 1,
                "average_heart_rate_bpm": 61.0,
                "sampling_frequency_hz": 512.0,
                "number_of_voltage_measurements": 1,
                "voltage_count": 1,
                "voltage_unit": "V",
                "lead": "apple_watch_similar_to_lead_i",
                "voltage_status": "partial",
                "voltage_error_code": "voltage_count_mismatch",
                "algorithm_version": 2,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "symptoms": [],
                "symptoms_read_status": "not_applicable",
                "metadata": {},
                "voltage": [{"time_offset_seconds": 0.0, "voltage_volts": 0.00077}],
            }
        ],
    )

    assert main(["ecg", "list", "--format", "json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["not_a_diagnosis"] is True
    assert listed["empty_result_does_not_prove_absence_or_normal"] is True
    assert "voltage" not in listed["records"][0]
    assert "0.00077" not in json.dumps(listed)

    output = tmp_path / "ecg.json"
    assert main(["ecg", "export", "--source-id", "ecg-cli-1", "--output", str(output), "--max-points", "1"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "exported"
    assert "0.00077" not in json.dumps(summary)
    exported = json.loads(output.read_text(encoding="utf-8"))
    assert exported["voltage"][0]["voltage_volts"] == 0.00077
    assert exported["not_a_diagnosis"] is True

    blocked = Path(cli_module.__file__).resolve().parents[2] / "docs" / "ecg_should_not_exist.json"
    with pytest.raises(ValueError, match="data/exports/"):
        cli_module._private_export_path(blocked)
    assert main(["ecg", "export", "--source-id", "ecg-cli-1", "--output", str(blocked)]) == 2
    assert not blocked.exists()


def test_ecg_export_rejects_unignored_repo_paths_without_writing(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    repo = Path(cli_module.__file__).resolve().parents[2]
    inside = repo / "data" / "ecg.json"
    assert not inside.exists()
    allowed = repo / "data" / "exports" / "synthetic_not_written.json"
    assert cli_module._private_export_path(allowed) == allowed.resolve()
    assert not allowed.exists()

    assert main(["ecg", "export", "--source-id", "missing", "--output", str(inside)]) == 2
    assert not inside.exists()
    assert "data/exports/" in capsys.readouterr().out

    leaf = tmp_path / "linked-ecg.json"
    leaf.symlink_to(inside)
    assert main(["ecg", "export", "--source-id", "missing", "--output", str(leaf)]) == 2
    assert not inside.exists()

    parent = tmp_path / "linked-data"
    parent.symlink_to(repo / "data", target_is_directory=True)
    assert main(["ecg", "export", "--source-id", "missing", "--output", str(parent / "ecg.json")]) == 2
    assert not inside.exists()


def test_ecg_list_days_help_documents_rolling_window(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["ecg", "list", "--help"])
    assert exc.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "Rolling window ending at the current instant" in help_text
    assert "previous 30 days from now" in help_text


def _ecg_at(source_id: str, start_at: str) -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "source_id": source_id,
        "start_at": start_at,
        "end_at": start_at,
        "algorithm_classification": "sinus_rhythm",
        "algorithm_classification_value": 1,
        "symptoms_status": "none",
        "symptoms_status_value": 1,
        "average_heart_rate_bpm": 60.0,
        "sampling_frequency_hz": 512.0,
        "number_of_voltage_measurements": 1,
        "voltage_count": 1,
        "voltage_unit": "V",
        "lead": "apple_watch_similar_to_lead_i",
        "voltage_status": "partial",
        "voltage_error_code": "voltage_count_mismatch",
        "algorithm_version": 2,
        "source_bundle_id": "com.apple.health",
        "source_name": "Health",
        "symptoms": [],
        "symptoms_read_status": "not_applicable",
        "metadata": {},
        "voltage": [{"time_offset_seconds": 0.0, "voltage_volts": 0.1}],
    }


def test_ecg_list_date_bounds_use_local_day_and_reject_bad_input(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    monkeypatch.setenv("HEALTH_QUANT_TIMEZONE", "America/Los_Angeles")
    initialize_database(db_path)
    upsert_ecg_records(
        db_path,
        [
            _ecg_at("local-prev", "2026-03-31T06:00:00Z"),
            _ecg_at("local-end", "2026-04-01T06:30:00Z"),
            _ecg_at("local-next", "2026-04-01T07:30:00Z"),
        ],
    )

    assert main(["ecg", "list", "--to-date", "2026-03-31", "--format", "json"]) == 0
    to_ids = {row["source_id"] for row in json.loads(capsys.readouterr().out)["records"]}
    assert to_ids == {"local-prev", "local-end"}

    assert main(["ecg", "list", "--from-date", "2026-03-31", "--to-date", "2026-03-31", "--format", "json"]) == 0
    day_ids = {row["source_id"] for row in json.loads(capsys.readouterr().out)["records"]}
    assert day_ids == {"local-end"}

    assert main(["ecg", "list", "--from-date", "2026-03-31T23:45:00-07:00", "--format", "json"]) == 0
    offset_ids = {row["source_id"] for row in json.loads(capsys.readouterr().out)["records"]}
    assert offset_ids == {"local-next"}

    assert main(["ecg", "list", "--to-date", "2026-02-31"]) == 2
    assert "YYYY-MM-DD" in capsys.readouterr().out
    assert main(["ecg", "list", "--from-date", "2026-03-31T12:00:00"]) == 2
    assert "timezone offset" in capsys.readouterr().out
    assert main(["ecg", "list", "--days", "0"]) == 2
    assert "greater than 0" in capsys.readouterr().out
    assert main(["ecg", "list", "--days", "-1"]) == 2


def test_ecg_list_includes_local_last_second_and_excludes_earlier_whole_second(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))
    monkeypatch.setenv("HEALTH_QUANT_TIMEZONE", "America/Los_Angeles")
    initialize_database(db_path)
    upsert_ecg_records(
        db_path,
        [
            _ecg_at("last-second", "2026-04-01T06:59:59Z"),
            _ecg_at("next-midnight", "2026-04-01T07:00:00Z"),
            _ecg_at("same-second-later", "2026-04-01T06:59:59.200000Z"),
        ],
    )

    assert main(["ecg", "list", "--to-date", "2026-03-31", "--format", "json"]) == 0
    end_ids = {row["source_id"] for row in json.loads(capsys.readouterr().out)["records"]}
    assert "last-second" in end_ids
    assert "next-midnight" not in end_ids

    assert main(["ecg", "list", "--from-date", "2026-03-31T23:59:59.123456-07:00", "--format", "json"]) == 0
    start_ids = {row["source_id"] for row in json.loads(capsys.readouterr().out)["records"]}
    assert "last-second" not in start_ids
    assert "same-second-later" in start_ids
    assert "next-midnight" in start_ids
