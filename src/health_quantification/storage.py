from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo


def create_observations_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric TEXT NOT NULL,
        value REAL NOT NULL,
        unit TEXT NOT NULL,
        start_at TEXT NOT NULL,
        end_at TEXT,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """


def create_daily_summaries_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS daily_summaries (
        date TEXT PRIMARY KEY,
        timezone TEXT NOT NULL,
        sleep_hours REAL,
        resting_hr_bpm REAL,
        hrv_sdnn_ms REAL,
        steps INTEGER,
        active_energy_kcal REAL,
        notes_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """


def create_sleep_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS sleep_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        start_at TEXT NOT NULL,
        end_at TEXT,
        stage TEXT NOT NULL,
        stage_value INTEGER NOT NULL,
        source_bundle_id TEXT,
        source_name TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id)
    )
    """


def create_vitals_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS vitals_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        metric_type TEXT NOT NULL,
        value REAL NOT NULL,
        unit TEXT,
        source_bundle_id TEXT,
        source_name TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id, metric_type)
    )
    """


def create_body_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS body_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        metric_type TEXT NOT NULL,
        value REAL NOT NULL,
        unit TEXT,
        source_bundle_id TEXT,
        source_name TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id, metric_type)
    )
    """


def create_lifestyle_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS lifestyle_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        metric_type TEXT NOT NULL,
        value REAL NOT NULL,
        unit TEXT,
        source_bundle_id TEXT,
        source_name TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id)
    )
    """


def create_activity_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS activity_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        start_at TEXT,
        end_at TEXT,
        metric_type TEXT NOT NULL,
        value REAL NOT NULL,
        unit TEXT,
        source_bundle_id TEXT,
        source_name TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id)
    )
    """


def create_workouts_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        workout_type TEXT NOT NULL,
        start_at TEXT NOT NULL,
        end_at TEXT NOT NULL,
        duration_seconds REAL,
        total_energy_burned REAL,
        total_distance_meters REAL,
        source_bundle_id TEXT,
        source_name TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id)
    )
    """


def create_illness_episodes_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS illness_episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        label TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL,
        start_at TEXT NOT NULL,
        end_at TEXT,
        notes_json TEXT NOT NULL DEFAULT '[]',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id)
    )
    """


def create_ecg_table() -> str:
    return """
    CREATE TABLE IF NOT EXISTS ecg_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        start_at TEXT NOT NULL,
        end_at TEXT,
        algorithm_classification TEXT NOT NULL,
        algorithm_classification_value INTEGER NOT NULL,
        symptoms_status TEXT NOT NULL,
        symptoms_status_value INTEGER NOT NULL,
        average_heart_rate_bpm REAL,
        sampling_frequency_hz REAL,
        number_of_voltage_measurements INTEGER NOT NULL,
        voltage_count INTEGER NOT NULL,
        voltage_unit TEXT,
        lead TEXT NOT NULL,
        voltage_status TEXT NOT NULL,
        voltage_error_code TEXT,
        algorithm_version INTEGER,
        source_bundle_id TEXT,
        source_name TEXT,
        symptoms_json TEXT NOT NULL DEFAULT '[]',
        symptoms_read_status TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        voltage_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id)
    )
    """


SCHEMA_STATEMENTS = [
    create_observations_table(),
    create_daily_summaries_table(),
    create_sleep_table(),
    create_vitals_table(),
    create_body_table(),
    create_lifestyle_table(),
    create_activity_table(),
    create_workouts_table(),
    create_illness_episodes_table(),
    create_ecg_table(),
]

ECG_LIST_LIMIT_DEFAULT = 50
ECG_LIST_LIMIT_MAX = 200
ECG_VOLTAGE_POINT_CAP = 65536
ECG_LIST_COLUMNS = (
    "id",
    "source",
    "source_id",
    "start_at",
    "end_at",
    "algorithm_classification",
    "algorithm_classification_value",
    "symptoms_status",
    "symptoms_status_value",
    "average_heart_rate_bpm",
    "sampling_frequency_hz",
    "number_of_voltage_measurements",
    "voltage_count",
    "voltage_unit",
    "lead",
    "voltage_status",
    "voltage_error_code",
    "algorithm_version",
    "source_bundle_id",
    "source_name",
    "symptoms_json",
    "symptoms_read_status",
    "metadata_json",
    "created_at",
    "updated_at",
)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def initialize_database(db_path: Path) -> None:
    with connect(db_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            _ = connection.execute(statement)
        connection.commit()


def _metadata_json(sample: dict[str, object]) -> str:
    return json.dumps(sample.get("metadata", {}))


def _notes_json(sample: dict[str, object]) -> str:
    notes = sample.get("notes", [])
    if isinstance(notes, list):
        return json.dumps(notes)
    return json.dumps([notes])


def append_daily_note(db_path: Path, date_str: str, timezone: str, note: str) -> int:
    try:
        date.fromisoformat(date_str)
    except ValueError as error:
        raise ValueError("date must use YYYY-MM-DD format") from error
    if not note.strip():
        raise ValueError("daily note must not be blank")

    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT timezone, notes_json FROM daily_summaries WHERE date = ?", (date_str,)
        ).fetchone()
        if row is None:
            notes = [note]
            _ = conn.execute(
                "INSERT INTO daily_summaries (date, timezone, notes_json) VALUES (?, ?, ?)",
                (date_str, timezone, json.dumps(notes)),
            )
        else:
            existing_timezone, notes_json = row
            if existing_timezone != timezone:
                raise ValueError(f"daily note timezone mismatch for {date_str}")
            try:
                notes = json.loads(notes_json)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid notes_json for {date_str}") from error
            if not isinstance(notes, list) or not all(isinstance(item, str) for item in notes):
                raise ValueError(f"invalid notes_json for {date_str}")
            notes.append(note)
            _ = conn.execute(
                "UPDATE daily_summaries SET notes_json = ?, updated_at = CURRENT_TIMESTAMP WHERE date = ?",
                (json.dumps(notes), date_str),
            )
        conn.commit()
    return len(notes)


def query_daily_notes(
    db_path: Path,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    if from_date:
        clauses.append("date >= ?")
        params.append(from_date)
    if to_date:
        clauses.append("date <= ?")
        params.append(to_date)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT date, notes_json FROM daily_summaries{where} ORDER BY date", params
        ).fetchall()

    notes_by_date: dict[str, list[str]] = {}
    for date_str, notes_json in rows:
        try:
            notes = json.loads(notes_json)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid notes_json for {date_str}") from error
        if not isinstance(notes, list) or not all(isinstance(item, str) for item in notes):
            raise ValueError(f"invalid notes_json for {date_str}")
        notes_by_date[date_str] = notes
    return notes_by_date


def _upsert_samples(
    db_path: Path,
    *,
    table_name: str,
    insert_columns: tuple[str, ...],
    update_columns: tuple[str, ...],
    conflict_columns: tuple[str, ...],
    samples: list[dict[str, object]],
    conflict_where: str | None = None,
    merge_existing: Callable[[sqlite3.Connection, dict[str, object]], dict[str, object]] | None = None,
) -> int:
    upserted = 0
    placeholders = ", ".join("?" for _ in insert_columns)
    columns_sql = ", ".join(insert_columns)
    update_sql = ", ".join(
        f"{column} = excluded.{column}" for column in update_columns
    )
    conflict_sql = ", ".join(conflict_columns)
    where_sql = f"\n        WHERE {conflict_where}" if conflict_where else ""
    sql = f"""
        INSERT INTO {table_name} ({columns_sql}, updated_at)
        VALUES ({placeholders}, CURRENT_TIMESTAMP)
        ON CONFLICT({conflict_sql}) DO UPDATE SET
            {update_sql},
            updated_at = CURRENT_TIMESTAMP{where_sql}
    """

    with connect(db_path) as conn:
        for sample in samples:
            if merge_existing is not None:
                sample = merge_existing(conn, sample)
            _ = conn.execute(sql, tuple(sample[column] for column in insert_columns))
            upserted += 1
        conn.commit()
    return upserted


def upsert_sleep_samples(db_path: Path, samples: list[dict[str, object]]) -> int:
    prepared_samples = [
        {
            "source": sample["source"],
            "source_id": sample["source_id"],
            "start_at": sample["start_at"],
            "end_at": sample["end_at"],
            "stage": sample["stage"],
            "stage_value": sample["stage_value"],
            "source_bundle_id": sample.get("source_bundle_id"),
            "source_name": sample.get("source_name"),
            "metadata_json": _metadata_json(sample),
        }
        for sample in samples
    ]
    return _upsert_samples(
        db_path,
        table_name="sleep_samples",
        insert_columns=(
            "source",
            "source_id",
            "start_at",
            "end_at",
            "stage",
            "stage_value",
            "source_bundle_id",
            "source_name",
            "metadata_json",
        ),
        update_columns=(
            "start_at",
            "end_at",
            "stage",
            "stage_value",
            "source_bundle_id",
            "source_name",
            "metadata_json",
        ),
        conflict_columns=("source", "source_id"),
        samples=prepared_samples,
    )


def upsert_vitals_samples(db_path: Path, samples: list[dict[str, object]]) -> int:
    return _upsert_samples_by_metric_type(
        db_path,
        table_name="vitals_samples",
        conflict_columns=("source", "source_id", "metric_type"),
        samples=samples,
    )


def upsert_body_samples(db_path: Path, samples: list[dict[str, object]]) -> int:
    return _upsert_samples_by_metric_type(
        db_path,
        table_name="body_samples",
        conflict_columns=("source", "source_id", "metric_type"),
        samples=samples,
    )


def upsert_lifestyle_samples(db_path: Path, samples: list[dict[str, object]]) -> int:
    return _upsert_samples_by_metric_type(
        db_path,
        table_name="lifestyle_samples",
        conflict_columns=("source", "source_id"),
        samples=samples,
    )


def _upsert_samples_by_metric_type(
    db_path: Path,
    *,
    table_name: str,
    conflict_columns: tuple[str, ...],
    samples: list[dict[str, object]],
) -> int:
    prepared_samples = [
        {
            "source": sample["source"],
            "source_id": sample["source_id"],
            "recorded_at": sample["recorded_at"],
            "metric_type": sample["metric_type"],
            "value": sample["value"],
            "unit": sample.get("unit"),
            "source_bundle_id": sample.get("source_bundle_id"),
            "source_name": sample.get("source_name"),
            "metadata_json": _metadata_json(sample),
        }
        for sample in samples
    ]
    return _upsert_samples(
        db_path,
        table_name=table_name,
        insert_columns=(
            "source",
            "source_id",
            "recorded_at",
            "metric_type",
            "value",
            "unit",
            "source_bundle_id",
            "source_name",
            "metadata_json",
        ),
        update_columns=(
            "recorded_at",
            "metric_type",
            "value",
            "unit",
            "source_bundle_id",
            "source_name",
            "metadata_json",
        ),
        conflict_columns=conflict_columns,
        samples=prepared_samples,
    )


def upsert_activity_samples(db_path: Path, samples: list[dict[str, object]]) -> int:
    prepared_samples = [
        {
            "source": sample["source"],
            "source_id": sample["source_id"],
            "start_at": sample.get("start_at"),
            "end_at": sample.get("end_at"),
            "metric_type": sample["metric_type"],
            "value": sample["value"],
            "unit": sample.get("unit"),
            "source_bundle_id": sample.get("source_bundle_id"),
            "source_name": sample.get("source_name"),
            "metadata_json": _metadata_json(sample),
        }
        for sample in samples
    ]
    return _upsert_samples(
        db_path,
        table_name="activity_samples",
        insert_columns=(
            "source",
            "source_id",
            "start_at",
            "end_at",
            "metric_type",
            "value",
            "unit",
            "source_bundle_id",
            "source_name",
            "metadata_json",
        ),
        update_columns=(
            "start_at",
            "end_at",
            "metric_type",
            "value",
            "unit",
            "source_bundle_id",
            "source_name",
            "metadata_json",
        ),
        conflict_columns=("source", "source_id"),
        samples=prepared_samples,
    )


def upsert_workout_samples(db_path: Path, samples: list[dict[str, object]]) -> int:
    prepared_samples = [
        {
            "source": sample["source"],
            "source_id": sample["source_id"],
            "workout_type": sample["workout_type"],
            "start_at": sample["start_at"],
            "end_at": sample["end_at"],
            "duration_seconds": sample.get("duration_seconds"),
            "total_energy_burned": sample.get("total_energy_burned"),
            "total_distance_meters": sample.get("total_distance_meters"),
            "source_bundle_id": sample.get("source_bundle_id"),
            "source_name": sample.get("source_name"),
            "metadata_json": _metadata_json(sample),
        }
        for sample in samples
    ]
    return _upsert_samples(
        db_path,
        table_name="workouts",
        insert_columns=(
            "source",
            "source_id",
            "workout_type",
            "start_at",
            "end_at",
            "duration_seconds",
            "total_energy_burned",
            "total_distance_meters",
            "source_bundle_id",
            "source_name",
            "metadata_json",
        ),
        update_columns=(
            "workout_type",
            "start_at",
            "end_at",
            "duration_seconds",
            "total_energy_burned",
            "total_distance_meters",
            "source_bundle_id",
            "source_name",
            "metadata_json",
        ),
        conflict_columns=("source", "source_id"),
        samples=prepared_samples,
    )


def upsert_illness_episodes(db_path: Path, samples: list[dict[str, object]]) -> int:
    prepared_samples = [
        {
            "source": sample["source"],
            "source_id": sample["source_id"],
            "label": sample["label"],
            "severity": sample["severity"],
            "status": sample["status"],
            "start_at": sample["start_at"],
            "end_at": sample.get("end_at"),
            "notes_json": _notes_json(sample),
            "metadata_json": _metadata_json(sample),
        }
        for sample in samples
    ]
    return _upsert_samples(
        db_path,
        table_name="illness_episodes",
        insert_columns=(
            "source",
            "source_id",
            "label",
            "severity",
            "status",
            "start_at",
            "end_at",
            "notes_json",
            "metadata_json",
        ),
        update_columns=(
            "label",
            "severity",
            "status",
            "start_at",
            "end_at",
            "notes_json",
            "metadata_json",
        ),
        conflict_columns=("source", "source_id"),
        samples=prepared_samples,
    )


def record_sample(
    db_path: Path, data_type: str, sample: dict[str, object]
) -> dict[str, object]:
    normalized_sample = dict(sample)
    metadata = normalized_sample.get("metadata")
    metadata_json = normalized_sample.get("metadata_json")
    if metadata is None and metadata_json is not None:
        if isinstance(metadata_json, str):
            normalized_sample["metadata"] = json.loads(metadata_json)
        else:
            normalized_sample["metadata"] = metadata_json

    source_id = str(normalized_sample.get("source_id") or str(uuid.uuid4()))
    source = str(normalized_sample.get("source") or "ai_manual")
    current_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    normalized_sample["source_id"] = source_id
    normalized_sample["source"] = source

    if data_type == "sleep":
        start_at = str(normalized_sample.get("start_at") or current_time)
        end_at = str(normalized_sample.get("end_at") or start_at)
        normalized_sample["start_at"] = start_at
        normalized_sample["end_at"] = end_at
        upsert_sleep_samples(db_path, [normalized_sample])
        metric_type = str(normalized_sample["stage"])
        value = normalized_sample["stage_value"]
    elif data_type == "activity":
        start_at = str(normalized_sample.get("start_at") or current_time)
        normalized_sample["start_at"] = start_at
        upsert_activity_samples(db_path, [normalized_sample])
        metric_type = str(normalized_sample["metric_type"])
        value = normalized_sample["value"]
    elif data_type == "lifestyle":
        normalized_sample["recorded_at"] = str(
            normalized_sample.get("recorded_at") or current_time
        )
        upsert_lifestyle_samples(db_path, [normalized_sample])
        metric_type = str(normalized_sample["metric_type"])
        value = normalized_sample["value"]
    elif data_type == "body":
        normalized_sample["recorded_at"] = str(
            normalized_sample.get("recorded_at") or current_time
        )
        upsert_body_samples(db_path, [normalized_sample])
        metric_type = str(normalized_sample["metric_type"])
        value = normalized_sample["value"]
    elif data_type == "vitals":
        normalized_sample["recorded_at"] = str(
            normalized_sample.get("recorded_at") or current_time
        )
        upsert_vitals_samples(db_path, [normalized_sample])
        metric_type = str(normalized_sample["metric_type"])
        value = normalized_sample["value"]
    else:
        raise ValueError(f"unknown data_type: {data_type}")

    return {
        "status": "recorded",
        "source_id": source_id,
        "data_type": data_type,
        "metric_type": metric_type,
        "value": value,
    }


def record_illness_episode(db_path: Path, sample: dict[str, object]) -> dict[str, object]:
    normalized_sample = dict(sample)
    metadata = normalized_sample.get("metadata")
    metadata_json = normalized_sample.get("metadata_json")
    if metadata is None and metadata_json is not None:
        if isinstance(metadata_json, str):
            normalized_sample["metadata"] = json.loads(metadata_json)
        else:
            normalized_sample["metadata"] = metadata_json

    notes = normalized_sample.get("notes")
    notes_json = normalized_sample.get("notes_json")
    if notes is None and notes_json is not None:
        if isinstance(notes_json, str):
            normalized_sample["notes"] = json.loads(notes_json)
        else:
            normalized_sample["notes"] = notes_json

    source_id = str(normalized_sample.get("source_id") or str(uuid.uuid4()))
    source = str(normalized_sample.get("source") or "ai_manual")
    current_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    status = str(normalized_sample.get("status") or "active")
    normalized_sample["source_id"] = source_id
    normalized_sample["source"] = source
    normalized_sample["status"] = status
    normalized_sample["start_at"] = str(normalized_sample.get("start_at") or current_time)
    normalized_sample["severity"] = str(normalized_sample.get("severity") or "unknown")
    normalized_sample["label"] = str(normalized_sample["label"])
    if normalized_sample.get("end_at") is not None:
        normalized_sample["end_at"] = str(normalized_sample["end_at"])
    if normalized_sample.get("notes") is None:
        normalized_sample["notes"] = []

    upsert_illness_episodes(db_path, [normalized_sample])
    return {
        "status": "recorded",
        "data_type": "illness",
        "source_id": source_id,
        "label": normalized_sample["label"],
        "severity": normalized_sample["severity"],
        "episode_status": status,
        "start_at": normalized_sample["start_at"],
        "end_at": normalized_sample.get("end_at"),
    }


def count_samples(db_path: Path, *, table_name: str, source: str | None = None) -> int:
    allowed_tables = {"sleep_samples", "vitals_samples", "body_samples", "lifestyle_samples", "activity_samples", "workouts"}
    if table_name not in allowed_tables:
        raise ValueError("unsupported sample table")
    where = " WHERE source = ?" if source else ""
    with connect(db_path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}{where}", (source,) if source else ()).fetchone()[0])


def _query_samples(
    db_path: Path,
    *,
    table_name: str,
    time_column: str,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
    metric_type: str | None = None,
) -> list[dict[str, object]]:
    clauses: list[str] = []
    params: list[object] = []
    if from_date:
        clauses.append(f"{time_column} >= ?")
        params.append(from_date)
    if to_date:
        clauses.append(f"{time_column} <= ?")
        params.append(to_date)
    if source:
        clauses.append("source = ?")
        params.append(source)
    if metric_type:
        clauses.append("metric_type = ?")
        params.append(metric_type)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM {table_name}{where} ORDER BY {time_column}",
            params,
        ).fetchall()
    return [dict(cast(sqlite3.Row, row)) for row in rows]


def query_sleep_samples(
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
) -> list[dict[str, object]]:
    return _query_samples(
        db_path,
        table_name="sleep_samples",
        time_column="start_at",
        from_date=from_date,
        to_date=to_date,
        source=source,
    )


def query_vitals_samples(
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
    metric_type: str | None = None,
) -> list[dict[str, object]]:
    return _query_samples(
        db_path,
        table_name="vitals_samples",
        time_column="recorded_at",
        from_date=from_date,
        to_date=to_date,
        source=source,
        metric_type=metric_type,
    )


def query_body_samples(
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
    metric_type: str | None = None,
) -> list[dict[str, object]]:
    return _query_samples(
        db_path,
        table_name="body_samples",
        time_column="recorded_at",
        from_date=from_date,
        to_date=to_date,
        source=source,
        metric_type=metric_type,
    )


def query_lifestyle_samples(
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
    metric_type: str | None = None,
) -> list[dict[str, object]]:
    return _query_samples(
        db_path,
        table_name="lifestyle_samples",
        time_column="recorded_at",
        from_date=from_date,
        to_date=to_date,
        source=source,
        metric_type=metric_type,
    )


def query_activity_samples(
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
    metric_type: str | None = None,
) -> list[dict[str, object]]:
    return _query_samples(
        db_path,
        table_name="activity_samples",
        time_column="start_at",
        from_date=from_date,
        to_date=to_date,
        source=source,
        metric_type=metric_type,
    )


def query_workout_samples(
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
) -> list[dict[str, object]]:
    return _query_samples(
        db_path,
        table_name="workouts",
        time_column="start_at",
        from_date=from_date,
        to_date=to_date,
        source=source,
    )


def query_illness_episodes(
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
    status: str | None = None,
) -> list[dict[str, object]]:
    clauses: list[str] = []
    params: list[object] = []
    if from_date:
        clauses.append("start_at >= ?")
        params.append(from_date)
    if to_date:
        clauses.append("start_at <= ?")
        params.append(to_date)
    if source:
        clauses.append("source = ?")
        params.append(source)
    if status:
        clauses.append("status = ?")
        params.append(status)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM illness_episodes{where} ORDER BY start_at DESC",
            params,
        ).fetchall()

    episodes: list[dict[str, object]] = []
    for row in rows:
        episode = dict(cast(sqlite3.Row, row))
        notes_json = episode.get("notes_json")
        metadata_json = episode.get("metadata_json")
        episode["notes"] = json.loads(notes_json) if isinstance(notes_json, str) else []
        episode["metadata"] = json.loads(metadata_json) if isinstance(metadata_json, str) else {}
        episodes.append(episode)
    return episodes


def _delete_samples(db_path: Path, *, table_name: str, source: str | None = None) -> int:
    with connect(db_path) as conn:
        if source:
            cursor = conn.execute(f"DELETE FROM {table_name} WHERE source = ?", (source,))
        else:
            cursor = conn.execute(f"DELETE FROM {table_name}")
        conn.commit()
    return cursor.rowcount


def delete_sleep_samples(db_path: Path, source: str | None = None) -> int:
    return _delete_samples(db_path, table_name="sleep_samples", source=source)


def delete_vitals_samples(db_path: Path, source: str | None = None) -> int:
    return _delete_samples(db_path, table_name="vitals_samples", source=source)


def delete_body_samples(db_path: Path, source: str | None = None) -> int:
    return _delete_samples(db_path, table_name="body_samples", source=source)


def delete_lifestyle_samples(db_path: Path, source: str | None = None) -> int:
    return _delete_samples(db_path, table_name="lifestyle_samples", source=source)


def delete_activity_samples(db_path: Path, source: str | None = None) -> int:
    return _delete_samples(db_path, table_name="activity_samples", source=source)


def delete_workout_samples(db_path: Path, source: str | None = None) -> int:
    return _delete_samples(db_path, table_name="workouts", source=source)


def _symptoms_json(sample: dict[str, object]) -> str:
    symptoms = sample.get("symptoms", [])
    if not isinstance(symptoms, list):
        raise ValueError("symptoms must be a list")
    return json.dumps(symptoms)


def _voltage_json(sample: dict[str, object]) -> str | None:
    voltage = sample.get("voltage", [])
    if voltage is None:
        return None
    if not isinstance(voltage, list):
        raise ValueError("voltage must be a list")
    if not voltage:
        return None
    return json.dumps(voltage)


_ECG_VOLTAGE_FIELDS = (
    "voltage_json",
    "voltage_status",
    "voltage_error_code",
    "voltage_count",
    "voltage_unit",
    "number_of_voltage_measurements",
    "sampling_frequency_hz",
)
_ECG_SYMPTOM_FIELDS = (
    "symptoms_json",
    "symptoms_read_status",
    "symptoms_status",
    "symptoms_status_value",
)
_SYMPTOM_FAILURE_STATUSES = frozenset({"query_failed", "unavailable", "not_returned"})


def _json_list_len(raw: object) -> int:
    if not isinstance(raw, str) or not raw:
        return 0
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    return len(parsed) if isinstance(parsed, list) else 0


def _point_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _has_waveform(raw: object, count: int) -> bool:
    return count > 0 and isinstance(raw, str) and raw not in ("", "null")


def _incoming_voltage_replaces(existing: sqlite3.Row, incoming: dict[str, object]) -> bool:
    incoming_count = _point_count(incoming.get("voltage_count"))
    incoming_has = _has_waveform(incoming.get("voltage_json"), incoming_count)
    existing_count = _point_count(existing["voltage_count"])
    existing_has = _has_waveform(existing["voltage_json"], existing_count)
    if incoming.get("voltage_status") == "complete" and incoming_has:
        return True
    if existing["voltage_status"] == "complete" and existing_has:
        return False
    if not existing_has:
        return True
    return (
        incoming.get("voltage_status") == "partial"
        and incoming_has
        and incoming_count >= existing_count
    )


def _keep_existing_symptoms(existing: sqlite3.Row, incoming: dict[str, object]) -> bool:
    existing_count = _json_list_len(existing["symptoms_json"])
    incoming_status = incoming.get("symptoms_read_status")
    incoming_count = _json_list_len(incoming.get("symptoms_json"))
    if not isinstance(incoming_status, str):
        return existing_count > 0
    if incoming_status in _SYMPTOM_FAILURE_STATUSES and (
        existing_count > 0 or existing["symptoms_read_status"] not in _SYMPTOM_FAILURE_STATUSES
    ):
        return True
    return existing_count > 0 and incoming_status == "partial" and incoming_count < existing_count


def _merge_ecg_quality(conn: sqlite3.Connection, sample: dict[str, object]) -> dict[str, object]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT voltage_json, voltage_status, voltage_error_code, voltage_count, voltage_unit,
               number_of_voltage_measurements, sampling_frequency_hz, symptoms_json,
               symptoms_read_status, symptoms_status, symptoms_status_value
        FROM ecg_records
        WHERE source = ? AND source_id = ?
        """,
        (sample["source"], sample["source_id"]),
    ).fetchone()
    if row is None:
        return sample
    merged = dict(sample)
    if not _incoming_voltage_replaces(row, sample):
        for field in _ECG_VOLTAGE_FIELDS:
            merged[field] = row[field]
    if _keep_existing_symptoms(row, sample):
        for field in _ECG_SYMPTOM_FIELDS:
            merged[field] = row[field]
    return merged


def upsert_ecg_records(db_path: Path, samples: list[dict[str, object]]) -> int:
    prepared_samples = [
        {
            "source": sample["source"],
            "source_id": sample["source_id"],
            "start_at": sample["start_at"],
            "end_at": sample.get("end_at"),
            "algorithm_classification": sample["algorithm_classification"],
            "algorithm_classification_value": sample["algorithm_classification_value"],
            "symptoms_status": sample["symptoms_status"],
            "symptoms_status_value": sample["symptoms_status_value"],
            "average_heart_rate_bpm": sample.get("average_heart_rate_bpm"),
            "sampling_frequency_hz": sample.get("sampling_frequency_hz"),
            "number_of_voltage_measurements": sample["number_of_voltage_measurements"],
            "voltage_count": sample["voltage_count"],
            "voltage_unit": sample.get("voltage_unit"),
            "lead": sample["lead"],
            "voltage_status": sample["voltage_status"],
            "voltage_error_code": sample.get("voltage_error_code"),
            "algorithm_version": sample.get("algorithm_version"),
            "source_bundle_id": sample.get("source_bundle_id"),
            "source_name": sample.get("source_name"),
            "symptoms_json": _symptoms_json(sample),
            "symptoms_read_status": sample["symptoms_read_status"],
            "metadata_json": _metadata_json(sample),
            "voltage_json": _voltage_json(sample),
        }
        for sample in samples
    ]
    return _upsert_samples(
        db_path,
        table_name="ecg_records",
        insert_columns=(
            "source",
            "source_id",
            "start_at",
            "end_at",
            "algorithm_classification",
            "algorithm_classification_value",
            "symptoms_status",
            "symptoms_status_value",
            "average_heart_rate_bpm",
            "sampling_frequency_hz",
            "number_of_voltage_measurements",
            "voltage_count",
            "voltage_unit",
            "lead",
            "voltage_status",
            "voltage_error_code",
            "algorithm_version",
            "source_bundle_id",
            "source_name",
            "symptoms_json",
            "symptoms_read_status",
            "metadata_json",
            "voltage_json",
        ),
        update_columns=(
            "start_at",
            "end_at",
            "algorithm_classification",
            "algorithm_classification_value",
            "symptoms_status",
            "symptoms_status_value",
            "average_heart_rate_bpm",
            "sampling_frequency_hz",
            "number_of_voltage_measurements",
            "voltage_count",
            "voltage_unit",
            "lead",
            "voltage_status",
            "voltage_error_code",
            "algorithm_version",
            "source_bundle_id",
            "source_name",
            "symptoms_json",
            "symptoms_read_status",
            "metadata_json",
            "voltage_json",
        ),
        conflict_columns=("source", "source_id"),
        samples=prepared_samples,
        merge_existing=_merge_ecg_quality,
    )


def count_ecg_records(db_path: Path, source: str | None = None) -> int:
    with connect(db_path) as conn:
        if source:
            row = conn.execute(
                "SELECT COUNT(*) FROM ecg_records WHERE source = ?",
                (source,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM ecg_records").fetchone()
    return int(row[0]) if row else 0


def _decode_ecg_row(row: sqlite3.Row, *, include_voltage: bool = False) -> dict[str, object]:
    record = dict(row)
    symptoms_json = record.pop("symptoms_json", "[]")
    metadata_json = record.pop("metadata_json", "{}")
    voltage_json = record.pop("voltage_json", None) if "voltage_json" in record else None
    record["symptoms"] = json.loads(symptoms_json) if isinstance(symptoms_json, str) else []
    record["metadata"] = json.loads(metadata_json) if isinstance(metadata_json, str) else {}
    if include_voltage:
        if isinstance(voltage_json, str) and voltage_json:
            parsed = json.loads(voltage_json)
            record["voltage"] = parsed if isinstance(parsed, list) else []
        else:
            record["voltage"] = []
    return record


def normalize_ecg_bound(value: str, *, timezone: str, end: bool) -> str:
    text = value.strip()
    label = "to_date" if end else "from_date"
    if len(text) == 10:
        try:
            day = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError as error:
            raise ValueError(f"{label} must be YYYY-MM-DD or an offset ISO-8601 datetime") from error
        local_time = time.max if end else time.min
        local = datetime.combine(day, local_time, tzinfo=ZoneInfo(timezone))
        return local.astimezone(UTC).isoformat().replace("+00:00", "Z")
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"{label} must be YYYY-MM-DD or an offset ISO-8601 datetime") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label} datetime must include a timezone offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _ecg_instant_key(value: str) -> str:
    text = value.strip()
    if len(text) == 10:
        parsed = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC)
    else:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond:06d}"


def _ecg_start_key_sql() -> str:
    stripped = "replace(replace(start_at, 'Z', ''), '+00:00', '')"
    return (
        "CASE "
        f"WHEN instr({stripped}, '.') = 0 THEN {stripped} || '.000000' "
        "ELSE substr("
        f"{stripped}, 1, instr({stripped}, '.')) || "
        f"substr(substr({stripped}, instr({stripped}, '.') + 1) || '000000', 1, 6) "
        "END"
    )


def query_ecg_records(
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
    source_id: str | None = None,
    limit: int = ECG_LIST_LIMIT_DEFAULT,
) -> tuple[list[dict[str, object]], bool]:
    bounded_limit = max(1, min(limit, ECG_LIST_LIMIT_MAX))
    clauses: list[str] = []
    params: list[object] = []
    start_key = _ecg_start_key_sql()
    if from_date:
        clauses.append(f"{start_key} >= ?")
        params.append(_ecg_instant_key(from_date))
    if to_date:
        clauses.append(f"{start_key} <= ?")
        params.append(_ecg_instant_key(to_date))
    if source:
        clauses.append("source = ?")
        params.append(source)
    if source_id:
        clauses.append("source_id = ?")
        params.append(source_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    columns = ", ".join(ECG_LIST_COLUMNS)
    params.append(bounded_limit + 1)
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT {columns} FROM ecg_records{where} ORDER BY start_at DESC LIMIT ?",
            params,
        ).fetchall()
    truncated = len(rows) > bounded_limit
    visible = rows[:bounded_limit]
    return [_decode_ecg_row(row) for row in visible], truncated


def query_ecg_voltage(
    db_path: Path,
    *,
    source_id: str,
    source: str | None = None,
    max_points: int,
) -> dict[str, object] | None:
    if max_points < 1 or max_points > ECG_VOLTAGE_POINT_CAP:
        raise ValueError("max_points is outside the allowed range")
    clauses = ["source_id = ?"]
    params: list[object] = [source_id]
    if source:
        clauses.append("source = ?")
        params.append(source)
    columns = ", ".join((*ECG_LIST_COLUMNS, "voltage_json"))
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"SELECT {columns} FROM ecg_records WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
    if row is None:
        return None
    record = _decode_ecg_row(row, include_voltage=True)
    voltage = record.get("voltage")
    points = voltage if isinstance(voltage, list) else []
    record["returned_points"] = min(len(points), max_points)
    record["truncated"] = len(points) > max_points
    record["voltage"] = points[:max_points]
    return record


def delete_ecg_records(db_path: Path, source: str | None = None) -> int:
    return _delete_samples(db_path, table_name="ecg_records", source=source)
