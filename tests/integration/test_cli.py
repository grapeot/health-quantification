from __future__ import annotations

import json

from health_quantification.cli import main
from health_quantification.storage import (
    initialize_database,
    upsert_activity_samples,
    upsert_body_samples,
    upsert_lifestyle_samples,
    upsert_vitals_samples,
)


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

    commands = [
        (["vitals", "analyze", "--days", "30", "--metric", "resting_heart_rate", "--format", "json"], "metric_type", "resting_heart_rate"),
        (["vitals", "daily", "--date", "2026-03-31", "--format", "json"], "data_type", "vitals"),
        (["body", "analyze", "--days", "30", "--metric", "body_mass", "--format", "json"], "metric_type", "body_mass"),
        (["body", "daily", "--date", "2026-03-31", "--format", "json"], "data_type", "body"),
        (["lifestyle", "analyze", "--days", "30", "--metric", "dietary_caffeine", "--format", "json"], "metric_type", "dietary_caffeine"),
        (["lifestyle", "daily", "--date", "2026-03-31", "--format", "json"], "data_type", "lifestyle"),
        (["activity", "analyze", "--days", "30", "--metric", "step_count", "--format", "json"], "metric_type", "step_count"),
        (["activity", "daily", "--date", "2026-03-31", "--format", "json"], "data_type", "activity"),
    ]

    for argv, field_name, expected in commands:
        assert main(argv) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload[field_name] == expected
