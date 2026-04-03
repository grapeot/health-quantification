from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

import pytest

from health_quantification.storage import (
    initialize_database,
    query_illness_episodes,
    record_illness_episode,
    record_sample,
)


def fetch_one(db_path, query: str) -> sqlite3.Row:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(query).fetchone()
    assert row is not None
    return row


def test_record_sample_routes_to_lifestyle_samples(tmp_path) -> None:
    db_path = tmp_path / "record_lifestyle.db"
    initialize_database(db_path)

    result = record_sample(
        db_path,
        "lifestyle",
        {
            "source": "manual_test",
            "source_id": "life-1",
            "recorded_at": "2026-03-31T12:00:00-07:00",
            "metric_type": "dietary_caffeine",
            "value": 57.0,
            "unit": "mg",
            "metadata": {"note": "Costco Mexican Coke 500ml"},
        },
    )

    row = fetch_one(db_path, "SELECT * FROM lifestyle_samples")
    assert row["source"] == "manual_test"
    assert row["source_id"] == "life-1"
    assert row["metric_type"] == "dietary_caffeine"
    assert row["value"] == 57.0
    assert row["unit"] == "mg"
    assert json.loads(row["metadata_json"]) == {"note": "Costco Mexican Coke 500ml"}
    assert result == {
        "status": "recorded",
        "source_id": "life-1",
        "data_type": "lifestyle",
        "metric_type": "dietary_caffeine",
        "value": 57.0,
    }


def test_record_sample_routes_to_body_samples(tmp_path) -> None:
    db_path = tmp_path / "record_body.db"
    initialize_database(db_path)

    record_sample(
        db_path,
        "body",
        {
            "source": "manual_test",
            "source_id": "body-1",
            "recorded_at": "2026-03-31T07:00:00Z",
            "metric_type": "body_mass",
            "value": 75.5,
            "unit": "kg",
            "metadata": {},
        },
    )

    row = fetch_one(db_path, "SELECT * FROM body_samples")
    assert row["source_id"] == "body-1"
    assert row["metric_type"] == "body_mass"
    assert row["value"] == 75.5
    assert row["unit"] == "kg"


def test_record_sample_routes_to_vitals_samples(tmp_path) -> None:
    db_path = tmp_path / "record_vitals.db"
    initialize_database(db_path)

    record_sample(
        db_path,
        "vitals",
        {
            "source": "manual_test",
            "source_id": "vitals-1",
            "recorded_at": "2026-03-31T07:00:00Z",
            "metric_type": "resting_heart_rate",
            "value": 62.0,
            "unit": "count/min",
            "metadata": {},
        },
    )

    row = fetch_one(db_path, "SELECT * FROM vitals_samples")
    assert row["source_id"] == "vitals-1"
    assert row["metric_type"] == "resting_heart_rate"
    assert row["value"] == 62.0
    assert row["unit"] == "count/min"


def test_record_sample_generates_source_id_when_missing(tmp_path) -> None:
    db_path = tmp_path / "record_source_id.db"
    initialize_database(db_path)

    result = record_sample(
        db_path,
        "lifestyle",
        {
            "metric_type": "dietary_caffeine",
            "value": 57.0,
            "unit": "mg",
            "metadata": {},
        },
    )

    row = fetch_one(db_path, "SELECT source_id FROM lifestyle_samples")
    assert isinstance(result["source_id"], str)
    assert result["source_id"]
    assert row["source_id"] == result["source_id"]


def test_record_sample_uses_ai_manual_as_default_source(tmp_path) -> None:
    db_path = tmp_path / "record_default_source.db"
    initialize_database(db_path)

    record_sample(
        db_path,
        "body",
        {
            "source_id": "body-default-source",
            "metric_type": "body_mass",
            "value": 75.5,
            "unit": "kg",
            "metadata": {},
        },
    )

    row = fetch_one(db_path, "SELECT source FROM body_samples")
    assert row["source"] == "ai_manual"


def test_record_sample_uses_current_time_when_missing(tmp_path) -> None:
    db_path = tmp_path / "record_default_time.db"
    initialize_database(db_path)
    before = datetime.now(UTC)

    record_sample(
        db_path,
        "vitals",
        {
            "source_id": "vitals-now",
            "metric_type": "resting_heart_rate",
            "value": 62.0,
            "unit": "count/min",
            "metadata": {},
        },
    )
    after = datetime.now(UTC)

    row = fetch_one(db_path, "SELECT recorded_at FROM vitals_samples")
    recorded_at = datetime.fromisoformat(str(row["recorded_at"]).replace("Z", "+00:00"))
    assert before <= recorded_at <= after


def test_record_sample_stores_note_from_metadata_json(tmp_path) -> None:
    db_path = tmp_path / "record_metadata_json.db"
    initialize_database(db_path)

    record_sample(
        db_path,
        "lifestyle",
        {
            "source_id": "life-metadata-json",
            "metric_type": "dietary_caffeine",
            "value": 57.0,
            "unit": "mg",
            "metadata_json": json.dumps({"note": "Afternoon coffee"}),
        },
    )

    row = fetch_one(db_path, "SELECT metadata_json FROM lifestyle_samples")
    assert json.loads(row["metadata_json"]) == {"note": "Afternoon coffee"}


def test_record_sample_rejects_unknown_data_type(tmp_path) -> None:
    db_path = tmp_path / "record_unknown.db"
    initialize_database(db_path)

    with pytest.raises(ValueError, match="unknown data_type"):
        record_sample(
            db_path,
            "unknown",
            {
                "metric_type": "dietary_caffeine",
                "value": 57.0,
                "unit": "mg",
                "metadata": {},
            },
        )


def test_record_illness_episode_routes_to_illness_episodes(tmp_path) -> None:
    db_path = tmp_path / "record_illness.db"
    initialize_database(db_path)

    result = record_illness_episode(
        db_path,
        {
            "source": "manual_test",
            "source_id": "illness-1",
            "label": "flu_like",
            "severity": "moderate",
            "status": "active",
            "start_at": "2026-04-01T03:00:00Z",
            "notes": [
                "Started feeling congested the night before last",
                "Today slightly better but still sick",
            ],
            "metadata": {
                "symptoms": ["nasal_congestion"],
                "progression": ["yesterday worse", "today slightly improved"],
            },
        },
    )

    row = fetch_one(db_path, "SELECT * FROM illness_episodes")
    assert row["source"] == "manual_test"
    assert row["source_id"] == "illness-1"
    assert row["label"] == "flu_like"
    assert row["severity"] == "moderate"
    assert row["status"] == "active"
    assert row["start_at"] == "2026-04-01T03:00:00Z"
    assert row["end_at"] is None
    assert json.loads(row["notes_json"]) == [
        "Started feeling congested the night before last",
        "Today slightly better but still sick",
    ]
    assert json.loads(row["metadata_json"]) == {
        "symptoms": ["nasal_congestion"],
        "progression": ["yesterday worse", "today slightly improved"],
    }
    assert result == {
        "status": "recorded",
        "data_type": "illness",
        "source_id": "illness-1",
        "label": "flu_like",
        "severity": "moderate",
        "episode_status": "active",
        "start_at": "2026-04-01T03:00:00Z",
        "end_at": None,
    }


def test_query_illness_episodes_decodes_json_fields(tmp_path) -> None:
    db_path = tmp_path / "query_illness.db"
    initialize_database(db_path)

    record_illness_episode(
        db_path,
        {
            "source_id": "illness-query-1",
            "label": "cold",
            "severity": "mild",
            "status": "resolved",
            "start_at": "2026-04-01T03:00:00Z",
            "end_at": "2026-04-02T18:00:00Z",
            "notes_json": json.dumps(["Recovered after one day"]),
            "metadata_json": json.dumps({"symptoms": ["congestion"]}),
        },
    )

    episodes = query_illness_episodes(db_path, status="resolved")
    assert len(episodes) == 1
    assert episodes[0]["notes"] == ["Recovered after one day"]
    assert episodes[0]["metadata"] == {"symptoms": ["congestion"]}
