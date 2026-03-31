from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

import pytest
from pydantic import ValidationError

from health_quantification.server import SleepIngestRequest


class SleepSamplePayload(TypedDict):
    source_id: str
    start_at: str
    end_at: str
    stage: str
    stage_value: int
    source_bundle_id: str
    source_name: str
    metadata: dict[str, str]


class SleepIngestPayload(TypedDict):
    source: str
    exported_at: str
    schema_version: str
    samples: list[SleepSamplePayload]


def build_valid_payload() -> SleepIngestPayload:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
                "source_id": "uuid-from-healthkit",
                "start_at": "2026-03-30T22:30:00Z",
                "end_at": "2026-03-31T06:30:00Z",
                "stage": "asleep_deep",
                "stage_value": 3,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            }
        ],
    }


def test_sleep_ingest_request_accepts_valid_payload() -> None:
    payload = build_valid_payload()

    request = SleepIngestRequest.model_validate(payload)

    assert request.source == "apple_health_ios"
    assert request.exported_at == datetime(2026, 3, 31, 2, 35, 56, tzinfo=UTC)
    assert request.samples[0].source_id == "uuid-from-healthkit"
    assert request.samples[0].metadata == {}


def test_sleep_ingest_request_rejects_missing_required_field() -> None:
    payload = dict(build_valid_payload())
    del payload["samples"]

    with pytest.raises(ValidationError):
        _ = SleepIngestRequest.model_validate(payload)


def test_sleep_ingest_request_rejects_wrong_stage_value_type() -> None:
    valid_payload = build_valid_payload()
    invalid_sample = dict(valid_payload["samples"][0])
    invalid_sample["stage_value"] = "deep"
    payload: dict[str, object] = dict(valid_payload)
    payload["samples"] = [invalid_sample]

    with pytest.raises(ValidationError):
        _ = SleepIngestRequest.model_validate(payload)


def test_sleep_ingest_request_rejects_unknown_fields() -> None:
    payload = dict(build_valid_payload())
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        _ = SleepIngestRequest.model_validate(payload)
