from __future__ import annotations

import sqlite3

from health_quantification.storage import (
    initialize_database,
    query_ecg_records,
    query_ecg_voltage,
    upsert_ecg_records,
    upsert_sleep_samples,
)


def _ecg_sample(source_id: str = "ecg-1") -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "source_id": source_id,
        "start_at": "2026-03-31T02:00:00Z",
        "end_at": "2026-03-31T02:00:30Z",
        "algorithm_classification": "inconclusive_other",
        "algorithm_classification_value": 6,
        "symptoms_status": "not_set",
        "symptoms_status_value": 0,
        "average_heart_rate_bpm": None,
        "sampling_frequency_hz": None,
        "number_of_voltage_measurements": 1,
        "voltage_count": 1,
        "voltage_unit": "V",
        "lead": "apple_watch_similar_to_lead_i",
        "voltage_status": "partial",
        "voltage_error_code": "voltage_count_mismatch",
        "algorithm_version": None,
        "source_bundle_id": "com.apple.health",
        "source_name": "Health",
        "symptoms": [],
        "symptoms_read_status": "not_applicable",
        "metadata": {},
        "voltage": [{"time_offset_seconds": 0.0, "voltage_volts": 0.2}],
    }


def test_initialize_database_adds_ecg_table_without_dropping_sleep(tmp_path) -> None:
    db_path = tmp_path / "existing.db"
    initialize_database(db_path)
    upsert_sleep_samples(
        db_path,
        [
            {
                "source": "apple_health_ios",
                "source_id": "sleep-keep",
                "start_at": "2026-03-30T22:00:00Z",
                "end_at": "2026-03-31T06:00:00Z",
                "stage": "asleep_core",
                "stage_value": 2,
                "metadata": {},
            }
        ],
    )
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        sleep_count = connection.execute("SELECT COUNT(*) FROM sleep_samples").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert sleep_count == 1
    assert "ecg_records" in tables


def test_ecg_upsert_is_idempotent_and_list_excludes_voltage(tmp_path) -> None:
    db_path = tmp_path / "ecg.db"
    initialize_database(db_path)
    sample = _ecg_sample()
    assert upsert_ecg_records(db_path, [sample]) == 1
    sample["voltage"] = [{"time_offset_seconds": 0.0, "voltage_volts": 0.4}]
    assert upsert_ecg_records(db_path, [sample]) == 1
    rows, truncated = query_ecg_records(db_path)
    assert truncated is False
    assert len(rows) == 1
    assert "voltage" not in rows[0]
    assert "voltage_json" not in rows[0]
    with sqlite3.connect(db_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM ecg_records").fetchone()[0]
        stored = connection.execute(
            "SELECT voltage_json FROM ecg_records WHERE source_id = 'ecg-1'"
        ).fetchone()[0]
    assert count == 1
    assert "0.4" in stored


def _complete_sample(source_id: str = "ecg-complete") -> dict[str, object]:
    sample = _ecg_sample(source_id)
    sample["voltage_status"] = "complete"
    sample["voltage_error_code"] = None
    sample["number_of_voltage_measurements"] = 2
    sample["voltage_count"] = 2
    sample["voltage"] = [
        {"time_offset_seconds": 0.0, "voltage_volts": 0.00051},
        {"time_offset_seconds": 0.001953125, "voltage_volts": -0.00052},
    ]
    return sample


def _stored_voltage(db_path) -> tuple[str, str]:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT voltage_status, voltage_json FROM ecg_records WHERE source_id = 'ecg-complete'"
        ).fetchone()
    assert row is not None
    return str(row[0]), str(row[1])


def test_failed_reexport_does_not_replace_complete_waveform(tmp_path) -> None:
    db_path = tmp_path / "ecg.db"
    initialize_database(db_path)
    upsert_ecg_records(db_path, [_complete_sample()])
    original_status, original_voltage = _stored_voltage(db_path)

    degraded = _complete_sample()
    degraded["voltage_status"] = "unavailable"
    degraded["voltage_error_code"] = "voltage_unavailable"
    degraded["voltage"] = []
    degraded["voltage_count"] = 0
    degraded["number_of_voltage_measurements"] = 2
    upsert_ecg_records(db_path, [degraded])

    partial = _complete_sample()
    partial["voltage_status"] = "partial"
    partial["voltage_error_code"] = "voltage_query_failed"
    partial["voltage"] = [{"time_offset_seconds": 0.0, "voltage_volts": 9.9}]
    partial["voltage_count"] = 1
    partial["number_of_voltage_measurements"] = 2
    upsert_ecg_records(db_path, [partial])

    failed = _complete_sample()
    failed["voltage_status"] = "query_failed"
    failed["voltage_error_code"] = "voltage_query_failed"
    failed["voltage"] = []
    failed["voltage_count"] = 0
    upsert_ecg_records(
        db_path,
        [failed, _ecg_sample("ecg-sibling")],
    )

    assert _stored_voltage(db_path) == (original_status, original_voltage)
    rows, _truncated = query_ecg_records(db_path, source_id="ecg-complete")
    assert "voltage" not in rows[0]
    assert rows[0]["voltage_status"] == "complete"
    exported = query_ecg_voltage(db_path, source_id="ecg-complete", max_points=2)
    assert exported is not None
    assert exported["voltage"] == _complete_sample()["voltage"]
    sibling, _sibling_truncated = query_ecg_records(db_path, source_id="ecg-sibling")
    assert sibling[0]["voltage_status"] == "partial"

    refreshed = _complete_sample()
    refreshed["voltage"] = [
        {"time_offset_seconds": 0.0, "voltage_volts": 0.00061},
        {"time_offset_seconds": 0.001953125, "voltage_volts": -0.00062},
    ]
    upsert_ecg_records(db_path, [refreshed])
    status, stored = _stored_voltage(db_path)
    assert status == "complete"
    assert "0.00061" in stored


def _stored_ecg(db_path, source_id: str) -> tuple[str, str | None, str, str]:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT voltage_status, voltage_json, symptoms_json, symptoms_read_status
            FROM ecg_records WHERE source_id = ?
            """,
            (source_id,),
        ).fetchone()
    assert row is not None
    return str(row[0]), None if row[1] is None else str(row[1]), str(row[2]), str(row[3])


def test_partial_waveform_and_symptoms_are_not_downgraded(tmp_path) -> None:
    db_path = tmp_path / "ecg.db"
    initialize_database(db_path)
    stored = _ecg_sample("ecg-partial")
    stored["voltage"] = [
        {"time_offset_seconds": 0.0, "voltage_volts": 0.11},
        {"time_offset_seconds": 0.002, "voltage_volts": 0.22},
    ]
    stored["voltage_count"] = 2
    stored["number_of_voltage_measurements"] = 4
    stored["symptoms"] = [
        {
            "symptom_type": "dizziness",
            "severity": "mild",
            "severity_value": 2,
            "source_id": "symptom-synthetic-1",
        }
    ]
    stored["symptoms_status"] = "present"
    stored["symptoms_status_value"] = 2
    stored["symptoms_read_status"] = "complete"
    upsert_ecg_records(db_path, [stored])
    original = _stored_ecg(db_path, "ecg-partial")

    failed = _ecg_sample("ecg-partial")
    failed["voltage_status"] = "query_failed"
    failed["voltage_error_code"] = "voltage_query_failed"
    failed["voltage"] = []
    failed["voltage_count"] = 0
    failed["symptoms"] = []
    failed["symptoms_read_status"] = "query_failed"
    upsert_ecg_records(db_path, [failed])
    assert _stored_ecg(db_path, "ecg-partial") == original

    shorter = _ecg_sample("ecg-partial")
    shorter["voltage"] = [{"time_offset_seconds": 0.0, "voltage_volts": 9.9}]
    shorter["voltage_count"] = 1
    shorter["symptoms"] = []
    shorter["symptoms_read_status"] = "partial"
    upsert_ecg_records(db_path, [shorter])
    assert _stored_ecg(db_path, "ecg-partial") == original

    longer = _ecg_sample("ecg-partial")
    longer["voltage"] = [
        {"time_offset_seconds": 0.0, "voltage_volts": 0.31},
        {"time_offset_seconds": 0.002, "voltage_volts": 0.32},
        {"time_offset_seconds": 0.004, "voltage_volts": 0.33},
    ]
    longer["voltage_count"] = 3
    longer["number_of_voltage_measurements"] = 4
    longer["symptoms"] = []
    longer["symptoms_read_status"] = "query_failed"
    upsert_ecg_records(db_path, [longer])
    status, waveform, symptoms, symptom_status = _stored_ecg(db_path, "ecg-partial")
    assert status == "partial"
    assert waveform is not None and "0.31" in waveform
    assert "dizziness" in symptoms
    assert symptom_status == "complete"
