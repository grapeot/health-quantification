from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Annotated, Callable, ClassVar, Literal, TypeAlias, cast

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from health_quantification.config import Settings, load_settings
from health_quantification.storage import (
    delete_activity_samples,
    delete_body_samples,
    delete_lifestyle_samples,
    delete_sleep_samples,
    delete_vitals_samples,
    initialize_database,
    query_activity_samples,
    query_body_samples,
    query_lifestyle_samples,
    query_sleep_samples,
    query_vitals_samples,
    upsert_activity_samples,
    upsert_body_samples,
    upsert_lifestyle_samples,
    upsert_sleep_samples,
    upsert_vitals_samples,
)

API_VERSION = "0.1.0"
StorageRow: TypeAlias = dict[str, object]
DataTypeName = Literal["sleep", "vitals", "body", "lifestyle", "activity"]
VitalsMetricType = Literal[
    "resting_heart_rate",
    "heart_rate_variability_sdnn",
    "respiratory_rate",
    "oxygen_saturation",
]
BodyMetricType = Literal[
    "body_mass",
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


@dataclass(frozen=True)
class DataTypeConfig:
    sleep_query_fn: Callable[[Path, str | None, str | None, str | None], list[StorageRow]] | None = None
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
    query_fn = config.metric_query_fn
    if query_fn is None:
        raise ValueError(f"metric query function missing for {data_type}")
    return query_fn(db_path, from_date, to_date, source, metric_type)


def _serialize_rows(
    data_type: DataTypeName,
    rows: list[StorageRow],
) -> list[SleepSampleOut | RecordedMetricSampleOut | ActivitySampleOut]:
    if data_type == "sleep":
        return [_row_to_sleep_model(row) for row in rows]
    if data_type == "activity":
        return [_row_to_activity_model(row) for row in rows]
    return [_row_to_recorded_metric_model(row) for row in rows]


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or load_settings()

    app = FastAPI(
        title="Health Quantification Ingestion API",
        version=API_VERSION,
        summary="Health ingestion API for the health_quantification toolkit.",
        description=(
            "HTTP ingestion boundary for normalized personal health data. "
            "This server exposes idempotent POST endpoints for sleep, vitals, body, "
            "lifestyle, and activity data, plus generic query and cleanup routes."
        ),
    )

    def get_initialized_db_path() -> Path:
        initialize_database(active_settings.db_path)
        return active_settings.db_path

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
        total_samples = len(query_sleep_samples(db_path=db_path, source=request.source))
        return IngestResponse(status="accepted", upserted=upserted, total_samples=total_samples)

    @app.post("/ingest/vitals", response_model=IngestResponse)
    def ingest_vitals(
        request: VitalsIngestRequest,
        db_path: Path = Depends(get_initialized_db_path),
    ) -> IngestResponse:
        upserted = upsert_vitals_samples(
            db_path,
            [_recorded_metric_sample_to_storage_dict(request.source, sample) for sample in request.samples],
        )
        total_samples = len(query_vitals_samples(db_path=db_path, source=request.source))
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
        total_samples = len(query_body_samples(db_path=db_path, source=request.source))
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
        total_samples = len(query_lifestyle_samples(db_path=db_path, source=request.source))
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
        total_samples = len(query_activity_samples(db_path=db_path, source=request.source))
        return IngestResponse(status="accepted", upserted=upserted, total_samples=total_samples)

    @app.get(
        "/ingest/{data_type}",
        response_model=list[SleepSampleOut | RecordedMetricSampleOut | ActivitySampleOut],
    )
    def get_samples(
        data_type: DataTypeName,
        db_path: Path = Depends(get_initialized_db_path),
        from_date: Annotated[str | None, Query()] = None,
        to_date: Annotated[str | None, Query()] = None,
        source: Annotated[str | None, Query()] = None,
        metric_type: Annotated[str | None, Query()] = None,
    ) -> list[SleepSampleOut | RecordedMetricSampleOut | ActivitySampleOut]:
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
