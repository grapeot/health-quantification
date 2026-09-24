from __future__ import annotations

import pytest

from scripts.ios_probe import validate_artifact

RUN_ID = "456EEB81-F801-4F0A-9C3F-9C9AFD9AB123"


def test_accepts_matching_synthetic_met_summary() -> None:
    payload: dict[str, object] = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "kind": "physical-effort",
        "status": "completed",
        "days": 30,
        "sample_count": 4,
        "unit": "MET",
        "minimum": 1.0,
        "median": 3.0,
        "p90": 5.0,
        "maximum": 6.0,
    }
    assert validate_artifact(payload, RUN_ID, 30) == payload


@pytest.mark.parametrize(
    "changes",
    [
        {"run_id": "not-this-run"},
        {"kind": "export-all"},
        {"status": "completed", "sample_count": 0},
        {"status": "completed", "unit": "count"},
        {"minimum": 9.0},
        {"p90": float("nan")},
        {"days": 31},
    ],
)
def test_rejects_mismatched_or_incomplete_artifacts(changes: dict[str, object]) -> None:
    payload: dict[str, object] = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "kind": "physical-effort",
        "status": "completed",
        "days": 30,
        "sample_count": 4,
        "unit": "MET",
        "minimum": 1.0,
        "median": 3.0,
        "p90": 5.0,
        "maximum": 6.0,
    }
    payload.update(changes)
    with pytest.raises(ValueError):
        validate_artifact(payload, RUN_ID, 30)


def test_accepts_explicit_no_data_without_claiming_permission_denial() -> None:
    payload: dict[str, object] = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "kind": "physical-effort",
        "status": "no_data",
        "days": 7,
        "sample_count": 0,
        "unit": "MET",
    }
    assert validate_artifact(payload, RUN_ID, 7) == payload
