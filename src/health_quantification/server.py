from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Annotated, Callable, ClassVar, Literal, TypeAlias, cast

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from health_quantification.config import Settings, load_settings
from health_quantification.storage import (
    ECG_LIST_LIMIT_DEFAULT,
    ECG_LIST_LIMIT_MAX,
    ECG_VOLTAGE_POINT_CAP,
    count_ecg_records,
    count_samples,
    normalize_ecg_bound,
    delete_activity_samples,
    delete_body_samples,
    delete_ecg_records,
    delete_lifestyle_samples,
    delete_sleep_samples,
    delete_vitals_samples,
    delete_workout_samples,
    initialize_database,
    query_activity_samples,
    query_body_samples,
    query_ecg_records,
    query_ecg_voltage,
    query_lifestyle_samples,
    query_sleep_samples,
    query_vitals_samples,
    query_workout_samples,
    upsert_activity_samples,
    upsert_body_samples,
    upsert_ecg_records,
    upsert_lifestyle_samples,
    upsert_sleep_samples,
    upsert_vitals_samples,
    upsert_workout_samples,
)

API_VERSION = "0.1.0"
ECG_MAX_BODY_BYTES = 8_000_000
ECG_MAX_SAMPLES = 4
ECG_INGEST_PATH = "/ingest/ecg"
_SAFE_ERROR_TYPE = re.compile(r"^[A-Za-z0-9_.]+$")
_ECG_ERROR_FIELDS = frozenset(
    {
        "source",
        "exported_at",
        "schema_version",
        "samples",
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
        "symptoms",
        "symptom_type",
        "severity",
        "severity_value",
        "symptoms_read_status",
        "metadata",
        "voltage",
        "time_offset_seconds",
        "voltage_volts",
    }
)
StorageRow: TypeAlias = dict[str, object]
DataTypeName = Literal["sleep", "vitals", "body", "lifestyle", "activity", "workouts"]
VitalsMetricType = Literal[
    "resting_heart_rate",
    "heart_rate",
    "heart_rate_variability_sdnn",
    "heart_rate_variability_rmssd",
    "respiratory_rate",
    "sleeping_breathing_disturbances",
    "sleeping_wrist_temperature",
    "vo2_max",
    "oxygen_saturation",
    "active_energy_burned",
]
BodyMetricType = Literal[
    "body_mass",
    "body_fat_percentage",
    "lean_body_mass",
    "waist_circumference",
    "blood_glucose",
    "blood_pressure_systolic",
    "blood_pressure_diastolic",
]
LifestyleMetricType = Literal["dietary_caffeine", "dietary_alcohol"]
ActivityMetricType = Literal["step_count"]


def _normalize_from_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        if len(value) == 10:
            return datetime.fromisoformat(value).date().isoformat()
        return _parse_datetime(value).isoformat().replace("+00:00", "Z")
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="from_date must be YYYY-MM-DD or an ISO-8601 datetime",
        ) from exc


def _normalize_to_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        if len(value) == 10:
            date_value = datetime.fromisoformat(value).date()
            return datetime.combine(date_value, time.max, tzinfo=UTC).isoformat().replace(
                "+00:00", "Z"
            )
        return _parse_datetime(value).isoformat().replace("+00:00", "Z")
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="to_date must be YYYY-MM-DD or an ISO-8601 datetime",
        ) from exc


def _is_ecg_ingest(request: Request) -> bool:
    return request.method == "POST" and request.url.path == ECG_INGEST_PATH


def _safe_error_loc(loc: object) -> list[str | int]:
    if not isinstance(loc, tuple):
        return ["rejected_field"]
    safe: list[str | int] = []
    for part in loc:
        if part == "body":
            continue
        if isinstance(part, int):
            safe.append(part)
        elif isinstance(part, str) and part in _ECG_ERROR_FIELDS:
            safe.append(part)
        else:
            safe.append("rejected_field")
    return safe


def _safe_error_type(value: object) -> str:
    if isinstance(value, str) and _SAFE_ERROR_TYPE.fullmatch(value):
        return value
    return "value_error"


def _redacted_ecg_errors(exc: RequestValidationError) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for err in exc.errors():
        summary.append(
            {
                "loc": _safe_error_loc(err.get("loc")),
                "type": _safe_error_type(err.get("type")),
            }
        )
    return summary


async def _send_json(send: Send, status_code: int, payload: dict[str, object]) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class ECGIngestBodyLimit:
    def __init__(self, app: ASGIApp, max_bytes: int = ECG_MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != ECG_INGEST_PATH
        ):
            await self.app(scope, receive, send)
            return

        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                declared = value.decode("ascii", errors="ignore")
                if declared.isdigit() and int(declared) > self.max_bytes:
                    await _send_json(send, 413, {"detail": "ecg payload exceeds size limit"})
                    return

        total = 0
        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body = message.get("body", b"")
            if not isinstance(body, bytes):
                body = bytes(body)
            total += len(body)
            if total > self.max_bytes:
                await _send_json(send, 413, {"detail": "ecg payload exceeds size limit"})
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        payload = b"".join(chunks)
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": payload, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class SleepSampleIn(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source_id: str = Field(...)
    start_at: datetime = Field(...)
    end_at: datetime | None = Field(...)
    stage: str = Field(...)
    stage_value: int = Field(...)
    source_bundle_id: str | None = Field(None)
    source_name: str | None = Field(None)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class RecordedMetricSampleIn(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source_id: str = Field(...)
    recorded_at: datetime = Field(...)
    value: float = Field(...)
    unit: str | None = Field(None)
    source_bundle_id: str | None = Field(None)
    source_name: str | None = Field(None)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class VitalsSampleIn(RecordedMetricSampleIn):
    metric_type: VitalsMetricType = Field(...)


class BodySampleIn(RecordedMetricSampleIn):
    metric_type: BodyMetricType = Field(...)


class LifestyleSampleIn(RecordedMetricSampleIn):
    metric_type: LifestyleMetricType = Field(...)


class ActivitySampleIn(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source_id: str = Field(...)
    start_at: datetime = Field(...)
    end_at: datetime | None = Field(...)
    metric_type: ActivityMetricType = Field(...)
    value: float = Field(...)
    unit: str | None = Field(None)
    source_bundle_id: str | None = Field(None)
    source_name: str | None = Field(None)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class WorkoutSampleIn(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source_id: str = Field(...)
    workout_type: str = Field(...)
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    duration_seconds: float | None = Field(None)
    total_energy_burned: float | None = Field(None)
    total_distance_meters: float | None = Field(None)
    source_bundle_id: str | None = Field(None)
    source_name: str | None = Field(None)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SleepIngestRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source: str = Field(...)
    exported_at: datetime = Field(...)
    schema_version: str = Field(...)
    samples: list[SleepSampleIn] = Field(..., min_length=1)


class VitalsIngestRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source: str = Field(...)
    exported_at: datetime = Field(...)
    schema_version: str = Field(...)
    samples: list[VitalsSampleIn] = Field(..., min_length=1)


class BodyIngestRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source: str = Field(...)
    exported_at: datetime = Field(...)
    schema_version: str = Field(...)
    samples: list[BodySampleIn] = Field(..., min_length=1)


class LifestyleIngestRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source: str = Field(...)
    exported_at: datetime = Field(...)
    schema_version: str = Field(...)
    samples: list[LifestyleSampleIn] = Field(..., min_length=1)


class ActivityIngestRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source: str = Field(...)
    exported_at: datetime = Field(...)
    schema_version: str = Field(...)
    samples: list[ActivitySampleIn] = Field(..., min_length=1)


class WorkoutIngestRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source: str = Field(...)
    exported_at: datetime = Field(...)
    schema_version: str = Field(...)
    samples: list[WorkoutSampleIn] = Field(..., min_length=1)


class ECGVoltagePointIn(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    time_offset_seconds: float = Field(..., ge=0)
    voltage_volts: float | None = Field(None)


class ECGSymptomIn(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    symptom_type: str = Field(..., pattern=r"^[a-z0-9_]{1,64}$")
    severity: str = Field(..., pattern=r"^[a-z0-9_]{1,64}$")
    severity_value: int = Field(...)
    source_id: str = Field(..., min_length=1, max_length=128)


class ECGSampleIn(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, max_length=128)
    start_at: datetime = Field(...)
    end_at: datetime | None = Field(None)
    algorithm_classification: str = Field(..., pattern=r"^[a-z0-9_]{1,64}$")
    algorithm_classification_value: int = Field(...)
    symptoms_status: str = Field(..., pattern=r"^[a-z0-9_]{1,64}$")
    symptoms_status_value: int = Field(...)
    average_heart_rate_bpm: float | None = Field(None)
    sampling_frequency_hz: float | None = Field(None, gt=0)
    number_of_voltage_measurements: int = Field(..., ge=0)
    voltage_count: int = Field(..., ge=0)
    voltage_unit: str | None = Field(None)
    lead: Literal["apple_watch_similar_to_lead_i"] = Field(...)
    voltage_status: Literal["complete", "unavailable", "partial", "query_failed"] = Field(...)
    voltage_error_code: str | None = Field(None, pattern=r"^[a-z0-9_]{1,64}$")
    algorithm_version: int | None = Field(None)
    source_bundle_id: str | None = Field(None)
    source_name: str | None = Field(None)
    symptoms: list[ECGSymptomIn] = Field(default_factory=list, max_length=32)
    symptoms_read_status: Literal[
        "not_applicable",
        "complete",
        "unavailable",
        "partial",
        "query_failed",
        "not_returned",
    ] = Field(...)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    voltage: list[ECGVoltagePointIn] = Field(default_factory=list, max_length=ECG_VOLTAGE_POINT_CAP)

    @model_validator(mode="after")
    def check_voltage_consistency(self) -> "ECGSampleIn":
        if self.voltage_count != len(self.voltage):
            raise ValueError("voltage_count must equal the number of voltage points")
        if self.voltage_unit not in {None, "V"}:
            raise ValueError("voltage_unit must be V when present")
        if self.voltage_status == "unavailable" and self.voltage:
            raise ValueError("unavailable voltage_status cannot include voltage points")
        if self.voltage_status == "complete":
            if not self.voltage or self.voltage_count != self.number_of_voltage_measurements:
                raise ValueError("complete voltage_status requires every expected measurement")
            if any(point.voltage_volts is None for point in self.voltage):
                raise ValueError("complete voltage_status cannot contain missing lead voltage")
        if self.voltage_status == "query_failed" and self.voltage_error_code is None:
            raise ValueError("query_failed voltage_status requires voltage_error_code")
        return self


class ECGIngestRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source: str = Field(...)
    exported_at: datetime = Field(...)
    schema_version: str = Field(...)
    samples: list[ECGSampleIn] = Field(..., min_length=1, max_length=ECG_MAX_SAMPLES)


class IngestResponse(BaseModel):
    status: Literal["accepted"] = Field(...)
    upserted: int = Field(...)
    total_samples: int = Field(...)


class SleepSampleOut(BaseModel):
    id: int = Field(...)
    source: str = Field(...)
    source_id: str = Field(...)
    start_at: str = Field(...)
    end_at: str | None = Field(...)
    stage: str = Field(...)
    stage_value: int = Field(...)
    source_bundle_id: str | None = Field(...)
    source_name: str | None = Field(...)
    metadata: dict[str, JsonValue] = Field(...)
    created_at: str = Field(...)
    updated_at: str = Field(...)


class RecordedMetricSampleOut(BaseModel):
    id: int = Field(...)
    source: str = Field(...)
    source_id: str = Field(...)
    recorded_at: str = Field(...)
    metric_type: str = Field(...)
    value: float = Field(...)
    unit: str | None = Field(...)
    source_bundle_id: str | None = Field(...)
    source_name: str | None = Field(...)
    metadata: dict[str, JsonValue] = Field(...)
    created_at: str = Field(...)
    updated_at: str = Field(...)


class ActivitySampleOut(BaseModel):
    id: int = Field(...)
    source: str = Field(...)
    source_id: str = Field(...)
    start_at: str | None = Field(...)
    end_at: str | None = Field(...)
    metric_type: str = Field(...)
    value: float = Field(...)
    unit: str | None = Field(...)
    source_bundle_id: str | None = Field(...)
    source_name: str | None = Field(...)
    metadata: dict[str, JsonValue] = Field(...)
    created_at: str = Field(...)
    updated_at: str = Field(...)


class WorkoutSampleOut(BaseModel):
    id: int = Field(...)
    source: str = Field(...)
    source_id: str = Field(...)
    workout_type: str = Field(...)
    start_at: str = Field(...)
    end_at: str = Field(...)
    duration_seconds: float | None = Field(...)
    total_energy_burned: float | None = Field(...)
    total_distance_meters: float | None = Field(...)
    source_bundle_id: str | None = Field(...)
    source_name: str | None = Field(...)
    metadata: dict[str, JsonValue] = Field(...)
    created_at: str = Field(...)
    updated_at: str = Field(...)


class ECGRecordOut(BaseModel):
    id: int = Field(...)
    source: str = Field(...)
    source_id: str = Field(...)
    start_at: str = Field(...)
    end_at: str | None = Field(...)
    algorithm_classification: str = Field(...)
    algorithm_classification_value: int = Field(...)
    symptoms_status: str = Field(...)
    symptoms_status_value: int = Field(...)
    average_heart_rate_bpm: float | None = Field(...)
    sampling_frequency_hz: float | None = Field(...)
    number_of_voltage_measurements: int = Field(...)
    voltage_count: int = Field(...)
    voltage_unit: str | None = Field(...)
    lead: str = Field(...)
    voltage_status: str = Field(...)
    voltage_error_code: str | None = Field(...)
    algorithm_version: int | None = Field(...)
    source_bundle_id: str | None = Field(...)
    source_name: str | None = Field(...)
    symptoms: list[JsonValue] = Field(...)
    symptoms_read_status: str = Field(...)
    metadata: dict[str, JsonValue] = Field(...)
    created_at: str = Field(...)
    updated_at: str = Field(...)
    classification_kind: Literal["apple_watch_ecg_algorithm"] = "apple_watch_ecg_algorithm"
    not_a_diagnosis: Literal[True] = True


class ECGListResponse(BaseModel):
    records: list[ECGRecordOut] = Field(...)
    returned: int = Field(...)
    limit: int = Field(...)
    truncated: bool = Field(...)
    empty_result_does_not_prove_absence_or_normal: Literal[True] = True
    classification_kind: Literal["apple_watch_ecg_algorithm"] = "apple_watch_ecg_algorithm"
    not_a_diagnosis: Literal[True] = True


class ECGVoltageResponse(BaseModel):
    source_id: str = Field(...)
    voltage_status: str = Field(...)
    voltage_count: int = Field(...)
    returned_points: int = Field(...)
    truncated: bool = Field(...)
    lead: str = Field(...)
    voltage_unit: str | None = Field(...)
    sampling_frequency_hz: float | None = Field(...)
    number_of_voltage_measurements: int = Field(...)
    voltage: list[JsonValue] = Field(...)
    missing_row_does_not_prove_absence_or_normal: Literal[True] = True
    classification_kind: Literal["apple_watch_ecg_algorithm"] = "apple_watch_ecg_algorithm"
    not_a_diagnosis: Literal[True] = True


class DeleteSamplesResponse(BaseModel):
    deleted: int = Field(...)


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(...)
    version: str = Field(...)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _sleep_sample_to_storage_dict(source: str, sample: SleepSampleIn) -> dict[str, object]:
    return {
        "source": source,
        "source_id": sample.source_id,
        "start_at": _serialize_datetime(sample.start_at),
        "end_at": _serialize_datetime(sample.end_at),
        "stage": sample.stage,
        "stage_value": sample.stage_value,
        "source_bundle_id": sample.source_bundle_id,
        "source_name": sample.source_name,
        "metadata": sample.metadata,
    }


def _recorded_metric_sample_to_storage_dict(
    source: str, sample: VitalsSampleIn | BodySampleIn | LifestyleSampleIn
) -> dict[str, object]:
    return {
        "source": source,
        "source_id": sample.source_id,
        "recorded_at": _serialize_datetime(sample.recorded_at),
        "metric_type": sample.metric_type,
        "value": sample.value,
        "unit": sample.unit,
        "source_bundle_id": sample.source_bundle_id,
        "source_name": sample.source_name,
        "metadata": sample.metadata,
    }


def _activity_sample_to_storage_dict(source: str, sample: ActivitySampleIn) -> dict[str, object]:
    return {
        "source": source,
        "source_id": sample.source_id,
        "start_at": _serialize_datetime(sample.start_at),
        "end_at": _serialize_datetime(sample.end_at),
        "metric_type": sample.metric_type,
        "value": sample.value,
        "unit": sample.unit,
        "source_bundle_id": sample.source_bundle_id,
        "source_name": sample.source_name,
        "metadata": sample.metadata,
    }


def _ecg_sample_to_storage_dict(source: str, sample: ECGSampleIn) -> dict[str, object]:
    return {
        "source": source,
        "source_id": sample.source_id,
        "start_at": _serialize_datetime(sample.start_at),
        "end_at": _serialize_datetime(sample.end_at),
        "algorithm_classification": sample.algorithm_classification,
        "algorithm_classification_value": sample.algorithm_classification_value,
        "symptoms_status": sample.symptoms_status,
        "symptoms_status_value": sample.symptoms_status_value,
        "average_heart_rate_bpm": sample.average_heart_rate_bpm,
        "sampling_frequency_hz": sample.sampling_frequency_hz,
        "number_of_voltage_measurements": sample.number_of_voltage_measurements,
        "voltage_count": sample.voltage_count,
        "voltage_unit": sample.voltage_unit,
        "lead": sample.lead,
        "voltage_status": sample.voltage_status,
        "voltage_error_code": sample.voltage_error_code,
        "algorithm_version": sample.algorithm_version,
        "source_bundle_id": sample.source_bundle_id,
        "source_name": sample.source_name,
        "symptoms": [item.model_dump() for item in sample.symptoms],
        "symptoms_read_status": sample.symptoms_read_status,
        "metadata": sample.metadata,
        "voltage": [item.model_dump() for item in sample.voltage],
    }


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError(f"Expected numeric value, got {type(value).__name__}")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise TypeError(f"Expected int value, got {type(value).__name__}")


def _json_list(value: object) -> list[JsonValue]:
    if isinstance(value, list):
        return cast(list[JsonValue], value)
    return []


def _row_to_ecg_model(row: StorageRow) -> ECGRecordOut:
    return ECGRecordOut(
        id=_require_int(row["id"]),
        source=_require_str(row["source"]),
        source_id=_require_str(row["source_id"]),
        start_at=_require_str(row["start_at"]),
        end_at=_optional_str(row["end_at"]),
        algorithm_classification=_require_str(row["algorithm_classification"]),
        algorithm_classification_value=_require_int(row["algorithm_classification_value"]),
        symptoms_status=_require_str(row["symptoms_status"]),
        symptoms_status_value=_require_int(row["symptoms_status_value"]),
        average_heart_rate_bpm=_optional_float(row["average_heart_rate_bpm"]),
        sampling_frequency_hz=_optional_float(row["sampling_frequency_hz"]),
        number_of_voltage_measurements=_require_int(row["number_of_voltage_measurements"]),
        voltage_count=_require_int(row["voltage_count"]),
        voltage_unit=_optional_str(row["voltage_unit"]),
        lead=_require_str(row["lead"]),
        voltage_status=_require_str(row["voltage_status"]),
        voltage_error_code=_optional_str(row["voltage_error_code"]),
        algorithm_version=_optional_int(row["algorithm_version"]),
        source_bundle_id=_optional_str(row["source_bundle_id"]),
        source_name=_optional_str(row["source_name"]),
        symptoms=_json_list(row.get("symptoms")),
        symptoms_read_status=_require_str(row["symptoms_read_status"]),
        metadata=_metadata_object(row.get("metadata")),
        created_at=_require_str(row["created_at"]),
        updated_at=_require_str(row["updated_at"]),
    )


def _workout_sample_to_storage_dict(source: str, sample: WorkoutSampleIn) -> dict[str, object]:
    return {
        "source": source,
        "source_id": sample.source_id,
        "workout_type": sample.workout_type,
        "start_at": _serialize_datetime(sample.start_at),
        "end_at": _serialize_datetime(sample.end_at),
        "duration_seconds": sample.duration_seconds,
        "total_energy_burned": sample.total_energy_burned,
        "total_distance_meters": sample.total_distance_meters,
        "source_bundle_id": sample.source_bundle_id,
        "source_name": sample.source_name,
        "metadata": sample.metadata,
    }


def _require_int(value: object) -> int:
    if isinstance(value, int):
        return value
    raise TypeError(f"Expected int value, got {type(value).__name__}")


def _require_str(value: object) -> str:
    if isinstance(value, str):
        return value
    raise TypeError(f"Expected str value, got {type(value).__name__}")


def _require_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError(f"Expected numeric value, got {type(value).__name__}")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return _require_str(value)


def _metadata_object(value: object) -> dict[str, JsonValue]:
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return cast(dict[str, JsonValue], value)
    return _decode_metadata(value)


def _decode_metadata(value: object) -> dict[str, JsonValue]:
    if not isinstance(value, str):
        return {}
    decoded = cast(object, json.loads(value))
    if isinstance(decoded, dict) and all(isinstance(key, str) for key in decoded):
        return cast(dict[str, JsonValue], decoded)
    return {}


def _row_to_sleep_model(row: StorageRow) -> SleepSampleOut:
    return SleepSampleOut(
        id=_require_int(row["id"]),
        source=_require_str(row["source"]),
        source_id=_require_str(row["source_id"]),
        start_at=_require_str(row["start_at"]),
        end_at=_optional_str(row["end_at"]),
        stage=_require_str(row["stage"]),
        stage_value=_require_int(row["stage_value"]),
        source_bundle_id=_optional_str(row["source_bundle_id"]),
        source_name=_optional_str(row["source_name"]),
        metadata=_decode_metadata(row.get("metadata_json")),
        created_at=_require_str(row["created_at"]),
        updated_at=_require_str(row["updated_at"]),
    )


def _row_to_recorded_metric_model(row: StorageRow) -> RecordedMetricSampleOut:
    return RecordedMetricSampleOut(
        id=_require_int(row["id"]),
        source=_require_str(row["source"]),
        source_id=_require_str(row["source_id"]),
        recorded_at=_require_str(row["recorded_at"]),
        metric_type=_require_str(row["metric_type"]),
        value=_require_float(row["value"]),
        unit=_optional_str(row["unit"]),
        source_bundle_id=_optional_str(row["source_bundle_id"]),
        source_name=_optional_str(row["source_name"]),
        metadata=_decode_metadata(row.get("metadata_json")),
        created_at=_require_str(row["created_at"]),
        updated_at=_require_str(row["updated_at"]),
    )


def _row_to_activity_model(row: StorageRow) -> ActivitySampleOut:
    return ActivitySampleOut(
        id=_require_int(row["id"]),
        source=_require_str(row["source"]),
        source_id=_require_str(row["source_id"]),
        start_at=_optional_str(row["start_at"]),
        end_at=_optional_str(row["end_at"]),
        metric_type=_require_str(row["metric_type"]),
        value=_require_float(row["value"]),
        unit=_optional_str(row["unit"]),
        source_bundle_id=_optional_str(row["source_bundle_id"]),
        source_name=_optional_str(row["source_name"]),
        metadata=_decode_metadata(row.get("metadata_json")),
        created_at=_require_str(row["created_at"]),
        updated_at=_require_str(row["updated_at"]),
    )


def _row_to_workout_model(row: StorageRow) -> WorkoutSampleOut:
    return WorkoutSampleOut(
        id=_require_int(row["id"]),
        source=_require_str(row["source"]),
        source_id=_require_str(row["source_id"]),
        workout_type=_require_str(row["workout_type"]),
        start_at=_require_str(row["start_at"]),
        end_at=_require_str(row["end_at"]),
        duration_seconds=cast(float | None, row["duration_seconds"]),
        total_energy_burned=cast(float | None, row["total_energy_burned"]),
        total_distance_meters=cast(float | None, row["total_distance_meters"]),
        source_bundle_id=_optional_str(row["source_bundle_id"]),
        source_name=_optional_str(row["source_name"]),
        metadata=_decode_metadata(row.get("metadata_json")),
        created_at=_require_str(row["created_at"]),
        updated_at=_require_str(row["updated_at"]),
    )


@dataclass(frozen=True)
class DataTypeConfig:
    sleep_query_fn: Callable[[Path, str | None, str | None, str | None], list[StorageRow]] | None = None
    time_query_fn: Callable[[Path, str | None, str | None, str | None], list[StorageRow]] | None = None
    metric_query_fn: Callable[
        [Path, str | None, str | None, str | None, str | None],
        list[StorageRow],
    ] | None = None
    delete_fn: Callable[[Path, str | None], int] | None = None


DATA_TYPE_CONFIG: dict[DataTypeName, DataTypeConfig] = {
    "sleep": DataTypeConfig(sleep_query_fn=query_sleep_samples, delete_fn=delete_sleep_samples),
    "vitals": DataTypeConfig(metric_query_fn=query_vitals_samples, delete_fn=delete_vitals_samples),
    "body": DataTypeConfig(metric_query_fn=query_body_samples, delete_fn=delete_body_samples),
    "lifestyle": DataTypeConfig(metric_query_fn=query_lifestyle_samples, delete_fn=delete_lifestyle_samples),
    "activity": DataTypeConfig(metric_query_fn=query_activity_samples, delete_fn=delete_activity_samples),
    "workouts": DataTypeConfig(time_query_fn=query_workout_samples, delete_fn=delete_workout_samples),
}


def _query_rows(
    *,
    data_type: DataTypeName,
    db_path: Path,
    from_date: str | None,
    to_date: str | None,
    source: str | None,
    metric_type: str | None,
) -> list[StorageRow]:
    config = DATA_TYPE_CONFIG[data_type]
    if data_type == "sleep":
        query_fn = config.sleep_query_fn
        if query_fn is None:
            raise ValueError(f"sleep query function missing for {data_type}")
        return query_fn(db_path, from_date, to_date, source)
    if data_type == "workouts":
        query_fn = config.time_query_fn
        if query_fn is None:
            raise ValueError(f"time query function missing for {data_type}")
        return query_fn(db_path, from_date, to_date, source)
    query_fn = config.metric_query_fn
    if query_fn is None:
        raise ValueError(f"metric query function missing for {data_type}")
    return query_fn(db_path, from_date, to_date, source, metric_type)


def _serialize_rows(
    data_type: DataTypeName,
    rows: list[StorageRow],
) -> list[SleepSampleOut | RecordedMetricSampleOut | ActivitySampleOut | WorkoutSampleOut]:
    if data_type == "sleep":
        return [_row_to_sleep_model(row) for row in rows]
    if data_type == "workouts":
        return [_row_to_workout_model(row) for row in rows]
    if data_type == "activity":
        return [_row_to_activity_model(row) for row in rows]
    return [_row_to_recorded_metric_model(row) for row in rows]


def create_app(settings: Settings | None = None) -> FastAPI:
    from time import perf_counter
    from uuid import UUID
    from .profiling import current_timings, timed
    active_settings = settings or load_settings()

    app = FastAPI(
        title="Health Quantification Ingestion API",
        version=API_VERSION,
        summary="Health ingestion API for the health_quantification toolkit.",
        description=(
            "HTTP ingestion boundary for normalized personal health data. "
            "This server exposes idempotent POST endpoints for sleep, vitals, body, "
            "lifestyle, activity, workout, and electrocardiogram data, plus generic query and cleanup routes."
        ),
    )

    def get_initialized_db_path() -> Path:
        with timed("initialize"):
            initialize_database(active_settings.db_path)
        return active_settings.db_path

    @app.middleware("http")
    async def ingest_timings(request: Request, call_next):
        value = request.headers.get("X-Health-Profile", "")
        try:
            if len(value) != 36 or not request.url.path.startswith("/ingest/"):
                return await call_next(request)
            UUID(value)
        except ValueError:
            return await call_next(request)
        timings: dict[str, float] = {}
        token = current_timings.set(timings)
        start = perf_counter()
        try:
            response = await call_next(request)
            timings["total"] = (perf_counter() - start) * 1000
            response.headers["Server-Timing"] = ", ".join(
                f"{phase};dur={duration:.3f}" for phase, duration in timings.items()
            )
            return response
        finally:
            current_timings.reset(token)

    @app.exception_handler(RequestValidationError)
    async def redact_ecg_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if _is_ecg_ingest(request):
            return JSONResponse(
                status_code=422,
                content={"detail": "ecg request rejected", "errors": _redacted_ecg_errors(exc)},
            )
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def redact_ecg_unexpected(request: Request, exc: Exception) -> JSONResponse:
        if _is_ecg_ingest(request):
            return JSONResponse(status_code=500, content={"detail": "ecg request failed"})
        raise exc

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION)

    @app.post("/ingest/sleep", response_model=IngestResponse)
    def ingest_sleep(
        request: SleepIngestRequest,
        db_path: Path = Depends(get_initialized_db_path),
    ) -> IngestResponse:
        upserted = upsert_sleep_samples(
            db_path,
            [_sleep_sample_to_storage_dict(request.source, sample) for sample in request.samples],
        )
        total_samples = count_samples(db_path, table_name="sleep_samples", source=request.source)
        return IngestResponse(status="accepted", upserted=upserted, total_samples=total_samples)

    @app.post("/ingest/vitals", response_model=IngestResponse)
    def ingest_vitals(
        request: VitalsIngestRequest,
        db_path: Path = Depends(get_initialized_db_path),
    ) -> IngestResponse:
        with timed("convert"):
            samples = [_recorded_metric_sample_to_storage_dict(request.source, sample) for sample in request.samples]
        with timed("upsert"):
            upserted = upsert_vitals_samples(db_path, samples)
        with timed("count"):
            total_samples = count_samples(db_path, table_name="vitals_samples", source=request.source)
        return IngestResponse(status="accepted", upserted=upserted, total_samples=total_samples)

    @app.post("/ingest/body", response_model=IngestResponse)
    def ingest_body(
        request: BodyIngestRequest,
        db_path: Path = Depends(get_initialized_db_path),
    ) -> IngestResponse:
        upserted = upsert_body_samples(
            db_path,
            [_recorded_metric_sample_to_storage_dict(request.source, sample) for sample in request.samples],
        )
        total_samples = count_samples(db_path, table_name="body_samples", source=request.source)
        return IngestResponse(status="accepted", upserted=upserted, total_samples=total_samples)

    @app.post("/ingest/lifestyle", response_model=IngestResponse)
    def ingest_lifestyle(
        request: LifestyleIngestRequest,
        db_path: Path = Depends(get_initialized_db_path),
    ) -> IngestResponse:
        upserted = upsert_lifestyle_samples(
            db_path,
            [_recorded_metric_sample_to_storage_dict(request.source, sample) for sample in request.samples],
        )
        total_samples = count_samples(db_path, table_name="lifestyle_samples", source=request.source)
        return IngestResponse(status="accepted", upserted=upserted, total_samples=total_samples)

    @app.post("/ingest/activity", response_model=IngestResponse)
    def ingest_activity(
        request: ActivityIngestRequest,
        db_path: Path = Depends(get_initialized_db_path),
    ) -> IngestResponse:
        upserted = upsert_activity_samples(
            db_path,
            [_activity_sample_to_storage_dict(request.source, sample) for sample in request.samples],
        )
        total_samples = count_samples(db_path, table_name="activity_samples", source=request.source)
        return IngestResponse(status="accepted", upserted=upserted, total_samples=total_samples)

    @app.post("/ingest/workouts", response_model=IngestResponse)
    def ingest_workouts(
        request: WorkoutIngestRequest,
        db_path: Path = Depends(get_initialized_db_path),
    ) -> IngestResponse:
        upserted = upsert_workout_samples(
            db_path,
            [_workout_sample_to_storage_dict(request.source, sample) for sample in request.samples],
        )
        total_samples = count_samples(db_path, table_name="workouts", source=request.source)
        return IngestResponse(status="accepted", upserted=upserted, total_samples=total_samples)

    @app.post("/ingest/ecg", response_model=IngestResponse)
    def ingest_ecg(
        request: ECGIngestRequest,
        db_path: Path = Depends(get_initialized_db_path),
    ) -> IngestResponse:
        upserted = upsert_ecg_records(
            db_path,
            [_ecg_sample_to_storage_dict(request.source, sample) for sample in request.samples],
        )
        return IngestResponse(
            status="accepted",
            upserted=upserted,
            total_samples=count_ecg_records(db_path, source=request.source),
        )

    @app.get("/ingest/ecg", response_model=ECGListResponse)
    def get_ecg_records(
        db_path: Path = Depends(get_initialized_db_path),
        from_date: Annotated[str | None, Query()] = None,
        to_date: Annotated[str | None, Query()] = None,
        source: Annotated[str | None, Query()] = None,
        source_id: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=ECG_LIST_LIMIT_MAX)] = ECG_LIST_LIMIT_DEFAULT,
    ) -> ECGListResponse:
        """YYYY-MM-DD is a full local day in the configured timezone. Offset ISO datetimes are normalized to UTC."""
        try:
            normalized_from = (
                normalize_ecg_bound(from_date, timezone=active_settings.timezone, end=False)
                if from_date
                else None
            )
            normalized_to = (
                normalize_ecg_bound(to_date, timezone=active_settings.timezone, end=True)
                if to_date
                else None
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        rows, truncated = query_ecg_records(
            db_path,
            from_date=normalized_from,
            to_date=normalized_to,
            source=source,
            source_id=source_id,
            limit=limit,
        )
        return ECGListResponse(
            records=[_row_to_ecg_model(row) for row in rows],
            returned=len(rows),
            limit=limit,
            truncated=truncated,
        )

    @app.get("/ingest/ecg/voltage", response_model=ECGVoltageResponse)
    def get_ecg_voltage(
        source_id: Annotated[str, Query(min_length=1, max_length=128)],
        max_points: Annotated[int, Query(ge=1, le=ECG_VOLTAGE_POINT_CAP)],
        db_path: Path = Depends(get_initialized_db_path),
        source: Annotated[str | None, Query()] = None,
    ) -> ECGVoltageResponse:
        try:
            row = query_ecg_voltage(
                db_path,
                source_id=source_id,
                source=source,
                max_points=max_points,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="ecg record not found; a missing row does not prove absence or a normal classification",
            )
        return ECGVoltageResponse(
            source_id=_require_str(row["source_id"]),
            voltage_status=_require_str(row["voltage_status"]),
            voltage_count=_require_int(row["voltage_count"]),
            returned_points=_require_int(row["returned_points"]),
            truncated=bool(row["truncated"]),
            lead=_require_str(row["lead"]),
            voltage_unit=_optional_str(row["voltage_unit"]),
            sampling_frequency_hz=_optional_float(row["sampling_frequency_hz"]),
            number_of_voltage_measurements=_require_int(row["number_of_voltage_measurements"]),
            voltage=_json_list(row.get("voltage")),
        )

    @app.delete("/ingest/ecg", response_model=DeleteSamplesResponse)
    def delete_ecg(
        source: Annotated[str, Query()],
        db_path: Path = Depends(get_initialized_db_path),
    ) -> DeleteSamplesResponse:
        return DeleteSamplesResponse(deleted=delete_ecg_records(db_path, source))

    @app.get(
        "/ingest/{data_type}",
        response_model=list[
            SleepSampleOut | RecordedMetricSampleOut | ActivitySampleOut | WorkoutSampleOut
        ],
    )
    def get_samples(
        data_type: DataTypeName,
        db_path: Path = Depends(get_initialized_db_path),
        from_date: Annotated[str | None, Query()] = None,
        to_date: Annotated[str | None, Query()] = None,
        source: Annotated[str | None, Query()] = None,
        metric_type: Annotated[str | None, Query()] = None,
    ) -> list[SleepSampleOut | RecordedMetricSampleOut | ActivitySampleOut | WorkoutSampleOut]:
        rows = _query_rows(
            data_type=data_type,
            db_path=db_path,
            from_date=_normalize_from_date(from_date),
            to_date=_normalize_to_date(to_date),
            source=source,
            metric_type=metric_type,
        )
        return _serialize_rows(data_type, rows)

    @app.delete("/ingest/{data_type}", response_model=DeleteSamplesResponse)
    def delete_samples(
        data_type: DataTypeName,
        source: Annotated[str, Query()],
        db_path: Path = Depends(get_initialized_db_path),
    ) -> DeleteSamplesResponse:
        delete_fn = DATA_TYPE_CONFIG[data_type].delete_fn
        if delete_fn is None:
            raise ValueError(f"delete function missing for {data_type}")
        deleted = delete_fn(db_path, source)
        return DeleteSamplesResponse(deleted=deleted)

    app.add_middleware(ECGIngestBodyLimit, max_bytes=ECG_MAX_BODY_BYTES)
    return app


app = create_app()


if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(
        "health_quantification.server:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
    )
