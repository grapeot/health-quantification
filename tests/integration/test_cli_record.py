from __future__ import annotations

import json
import sqlite3

import pytest

from health_quantification.cli import main


def fetch_one(db_path, query: str) -> sqlite3.Row:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(query).fetchone()
    assert row is not None
    return row


def test_record_lifestyle_command_outputs_json(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_record_lifestyle.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))

    exit_code = main(
        [
            "record",
            "lifestyle",
            "--metric",
            "dietary_caffeine",
            "--value",
            "57",
            "--unit",
            "mg",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "recorded"
    assert payload["data_type"] == "lifestyle"
    assert payload["metric_type"] == "dietary_caffeine"
    assert payload["value"] == 57.0
    row = fetch_one(db_path, "SELECT metric_type, value, unit, source FROM lifestyle_samples")
    assert row["metric_type"] == "dietary_caffeine"
    assert row["value"] == 57.0
    assert row["unit"] == "mg"
    assert row["source"] == "ai_manual"


def test_record_body_command_outputs_json(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_record_body.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))

    exit_code = main(
        ["record", "body", "--metric", "body_mass", "--value", "75.5", "--unit", "kg"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_type"] == "body"
    assert payload["metric_type"] == "body_mass"
    assert payload["value"] == 75.5
    row = fetch_one(db_path, "SELECT metric_type, value, unit FROM body_samples")
    assert row["metric_type"] == "body_mass"


def test_record_vitals_command_outputs_json(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_record_vitals.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))

    exit_code = main(
        [
            "record",
            "vitals",
            "--metric",
            "resting_heart_rate",
            "--value",
            "62",
            "--unit",
            "count/min",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_type"] == "vitals"
    assert payload["metric_type"] == "resting_heart_rate"
    row = fetch_one(db_path, "SELECT metric_type, value, unit FROM vitals_samples")
    assert row["metric_type"] == "resting_heart_rate"
    assert row["value"] == 62.0
    assert row["unit"] == "count/min"


def test_record_activity_command_outputs_json(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_record_activity.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))

    exit_code = main(
        ["record", "activity", "--metric", "step_count", "--value", "8500", "--unit", "count"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_type"] == "activity"
    assert payload["metric_type"] == "step_count"
    row = fetch_one(db_path, "SELECT metric_type, value, unit, start_at FROM activity_samples")
    assert row["metric_type"] == "step_count"
    assert row["value"] == 8500.0
    assert row["unit"] == "count"
    assert row["start_at"] is not None


def test_record_sleep_command_outputs_json(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_record_sleep.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))

    exit_code = main(
        [
            "record",
            "sleep",
            "--metric",
            "asleep_core",
            "--value",
            "2",
            "--unit",
            "stage",
            "--time",
            "2026-03-31T22:30:00Z",
            "--note",
            "Manual sleep sample",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_type"] == "sleep"
    assert payload["metric_type"] == "asleep_core"
    assert payload["value"] == 2
    row = fetch_one(db_path, "SELECT stage, stage_value, start_at, end_at, metadata_json FROM sleep_samples")
    assert row["stage"] == "asleep_core"
    assert row["stage_value"] == 2
    assert row["start_at"] == "2026-03-31T22:30:00Z"
    assert row["end_at"] == "2026-03-31T22:30:00Z"
    assert json.loads(row["metadata_json"]) == {"note": "Manual sleep sample"}


def test_record_command_requires_metric(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_record_requires_metric.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))

    with pytest.raises(SystemExit) as exc_info:
        main(["record", "lifestyle", "--value", "57", "--unit", "mg"])

    assert exc_info.value.code == 2
    assert "--metric" in capsys.readouterr().err


def test_record_command_requires_value(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "cli_record_requires_value.db"
    monkeypatch.setenv("HEALTH_QUANT_DB_PATH", str(db_path))

    with pytest.raises(SystemExit) as exc_info:
        main(["record", "lifestyle", "--metric", "dietary_caffeine", "--unit", "mg"])

    assert exc_info.value.code == 2
    assert "--value" in capsys.readouterr().err
