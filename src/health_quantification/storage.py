from __future__ import annotations

import json
import sqlite3
from pathlib import Path


SCHEMA_STATEMENTS = [
    """
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
    """,
    """
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
    """,
    """
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
    """,
]


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def initialize_database(db_path: Path) -> None:
    with connect(db_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.commit()


def upsert_sleep_samples(db_path: Path, samples: list[dict[str, object]]) -> int:
    upserted = 0
    with connect(db_path) as conn:
        for s in samples:
            metadata_json = json.dumps(s.get("metadata", {}))
            conn.execute(
                """
                INSERT INTO sleep_samples
                    (source, source_id, start_at, end_at, stage, stage_value,
                     source_bundle_id, source_name, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source, source_id) DO UPDATE SET
                    start_at = excluded.start_at,
                    end_at = excluded.end_at,
                    stage = excluded.stage,
                    stage_value = excluded.stage_value,
                    source_bundle_id = excluded.source_bundle_id,
                    source_name = excluded.source_name,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    s["source"],
                    s["source_id"],
                    s["start_at"],
                    s["end_at"],
                    s["stage"],
                    s["stage_value"],
                    s.get("source_bundle_id"),
                    s.get("source_name"),
                    metadata_json,
                ),
            )
            upserted += 1
        conn.commit()
    return upserted


def query_sleep_samples(
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    source: str | None = None,
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

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM sleep_samples{where} ORDER BY start_at",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def delete_sleep_samples(db_path: Path, source: str | None = None) -> int:
    with connect(db_path) as conn:
        if source:
            cursor = conn.execute(
                "DELETE FROM sleep_samples WHERE source = ?", (source,)
            )
        else:
            cursor = conn.execute("DELETE FROM sleep_samples")
        conn.commit()
    return cursor.rowcount
