from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast


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


SCHEMA_STATEMENTS = [
    create_observations_table(),
    create_daily_summaries_table(),
    create_sleep_table(),
    create_vitals_table(),
    create_body_table(),
    create_lifestyle_table(),
    create_activity_table(),
]


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


def _upsert_samples(
    db_path: Path,
    *,
    table_name: str,
    insert_columns: tuple[str, ...],
    update_columns: tuple[str, ...],
    conflict_columns: tuple[str, ...],
    samples: list[dict[str, object]],
) -> int:
    upserted = 0
    placeholders = ", ".join("?" for _ in insert_columns)
    columns_sql = ", ".join(insert_columns)
    update_sql = ", ".join(
        f"{column} = excluded.{column}" for column in update_columns
    )
    conflict_sql = ", ".join(conflict_columns)
    sql = f"""
        INSERT INTO {table_name} ({columns_sql}, updated_at)
        VALUES ({placeholders}, CURRENT_TIMESTAMP)
        ON CONFLICT({conflict_sql}) DO UPDATE SET
            {update_sql},
            updated_at = CURRENT_TIMESTAMP
    """

    with connect(db_path) as conn:
        for sample in samples:
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
