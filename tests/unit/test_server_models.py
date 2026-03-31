from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import ValidationError

from health_quantification.server import (
    ActivityIngestRequest,
    BodyIngestRequest,
    LifestyleIngestRequest,
    SleepIngestRequest,
    VitalsIngestRequest,
)


def build_sleep_payload() -> dict[str, object]:
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


def build_vitals_payload() -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
                "source_id": "vitals-1",
                "recorded_at": "2026-03-31T06:30:00Z",
                "metric_type": "resting_heart_rate",
                "value": 62.0,
                "unit": "count/min",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            }
        ],
    }


def build_body_payload() -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
                "source_id": "body-1",
                "recorded_at": "2026-03-31T06:30:00Z",
                "metric_type": "body_mass",
                "value": 75.5,
                "unit": "kg",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {},
            }
        ],
    }


def build_lifestyle_payload() -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
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
    }


def build_activity_payload() -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
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
    }


def test_sleep_ingest_request_accepts_valid_payload() -> None:
    request = SleepIngestRequest.model_validate(build_sleep_payload())
    assert request.source == "apple_health_ios"
    assert request.exported_at == datetime(2026, 3, 31, 2, 35, 56, tzinfo=UTC)
    assert request.samples[0].source_id == "uuid-from-healthkit"


@pytest.mark.parametrize(
    ("request_model", "payload_builder", "metric_type"),
    [
        (VitalsIngestRequest, build_vitals_payload, "resting_heart_rate"),
        (BodyIngestRequest, build_body_payload, "body_mass"),
        (LifestyleIngestRequest, build_lifestyle_payload, "dietary_caffeine"),
        (ActivityIngestRequest, build_activity_payload, "step_count"),
    ],
)
def test_phase_2_ingest_requests_accept_valid_payloads(
    request_model: type[VitalsIngestRequest | BodyIngestRequest | LifestyleIngestRequest | ActivityIngestRequest],
    payload_builder: Callable[[], dict[str, object]],
    metric_type: str,
) -> None:
    request = request_model.model_validate(payload_builder())
    assert request.source == "apple_health_ios"
    assert request.samples[0].metric_type == metric_type


@pytest.mark.parametrize(
    ("request_model", "payload_builder"),
    [
        (SleepIngestRequest, build_sleep_payload),
        (VitalsIngestRequest, build_vitals_payload),
        (BodyIngestRequest, build_body_payload),
        (LifestyleIngestRequest, build_lifestyle_payload),
        (ActivityIngestRequest, build_activity_payload),
    ],
)
def test_ingest_requests_reject_missing_samples(
    request_model: type[SleepIngestRequest | VitalsIngestRequest | BodyIngestRequest | LifestyleIngestRequest | ActivityIngestRequest],
    payload_builder: Callable[[], dict[str, object]],
) -> None:
    payload = dict(payload_builder())
    del payload["samples"]
    with pytest.raises(ValidationError):
        _ = request_model.model_validate(payload)


@pytest.mark.parametrize(
    ("request_model", "payload_builder", "bad_metric_type"),
    [
        (VitalsIngestRequest, build_vitals_payload, "vo2_max"),
        (BodyIngestRequest, build_body_payload, "body_fat_percentage"),
        (LifestyleIngestRequest, build_lifestyle_payload, "water_intake"),
        (ActivityIngestRequest, build_activity_payload, "distance_walking_running"),
    ],
)
def test_phase_2_ingest_requests_reject_unknown_metric_type(
    request_model: type[VitalsIngestRequest | BodyIngestRequest | LifestyleIngestRequest | ActivityIngestRequest],
    payload_builder: Callable[[], dict[str, object]],
    bad_metric_type: str,
) -> None:
    payload = dict(payload_builder())
    samples = cast(list[dict[str, object]], payload["samples"])
    invalid_sample = dict(samples[0])
    invalid_sample["metric_type"] = bad_metric_type
    payload["samples"] = [invalid_sample]
    with pytest.raises(ValidationError):
        _ = request_model.model_validate(payload)


def test_sleep_ingest_request_rejects_unknown_fields() -> None:
    payload = dict(build_sleep_payload())
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        _ = SleepIngestRequest.model_validate(payload)
