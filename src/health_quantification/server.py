from __future__ import annotations

import json
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Annotated, ClassVar, Literal, TypeAlias, cast

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from health_quantification.config import Settings, load_settings
from health_quantification.storage import (
    delete_sleep_samples,
    initialize_database,
    query_sleep_samples,
    upsert_sleep_samples,
)

API_VERSION = "0.1.0"
StorageRow: TypeAlias = dict[str, object]


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
    """One normalized sleep stage sample from an upstream exporter.

    Each sample represents a single sleep segment or stage interval from a source
    system such as Apple Health. The pair of source and source_id is the idempotent
    identity used by storage. Re-sending the same sample updates the existing row
    instead of creating duplicates.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source_id: str = Field(
        ...,
        description="Stable unique identifier emitted by the upstream source for this sample.",
    )
    start_at: datetime = Field(
        ...,
        description="Inclusive ISO-8601 start timestamp for the sleep interval.",
    )
    end_at: datetime | None = Field(
        ...,
        description="Exclusive or end timestamp for the sleep interval in ISO-8601 format.",
    )
    stage: str = Field(
        ...,
        description="Normalized sleep stage label such as asleep_deep, asleep_core, or awake.",
    )
    stage_value: int = Field(
        ...,
        description="Source-specific numeric stage code preserved for downstream analysis.",
    )
    source_bundle_id: str | None = Field(
        None,
        description="Optional upstream application bundle identifier such as com.apple.health.",
    )
    source_name: str | None = Field(
        None,
        description="Optional human-readable upstream source name such as Health.",
    )
    metadata: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Additional source metadata preserved as JSON for future analysis and debugging.",
    )


class SleepIngestRequest(BaseModel):
    """Batch ingestion envelope for sleep samples.

    The request describes one exporter run. The source identifies the upstream
    adapter, exported_at tells consumers when the snapshot was generated, and
    samples contains the sleep segments to upsert. Ingestion is idempotent per
    sample because storage upserts on the pair of source and source_id.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    source: str = Field(
        ...,
        description="Name of the upstream ingestion source, for example apple_health_ios.",
    )
    exported_at: datetime = Field(
        ...,
        description="ISO-8601 timestamp for when the upstream exporter produced this batch.",
    )
    schema_version: str = Field(
        ...,
        description="Version of the ingestion payload schema used by the exporter.",
    )
    samples: list[SleepSampleIn] = Field(
        ...,
        min_length=1,
        description="Sleep samples included in this batch. Each sample is upserted independently.",
    )


class SleepIngestResponse(BaseModel):
    """Result of a sleep ingestion request.

    accepted means the batch passed validation and was written via upsert.
    upserted is the number of samples processed in this request, and total_samples
    is the current total number of stored rows for the same source after ingestion.
    """

    status: Literal["accepted"] = Field(
        ...,
        description="Fixed status indicating the batch was validated and processed.",
    )
    upserted: int = Field(
        ...,
        description="Number of samples upserted from the current request payload.",
    )
    total_samples: int = Field(
        ...,
        description="Current total number of stored sleep samples for the request source after ingestion.",
    )


class SleepSampleOut(BaseModel):
    """Stored sleep sample record returned by the query endpoint.

    This mirrors the persisted SQLite row, including the database id and audit
    timestamps. metadata_json from storage is decoded into metadata so API clients
    receive structured JSON instead of a raw string.
    """

    id: int = Field(..., description="Autoincrement primary key in the local SQLite database.")
    source: str = Field(..., description="Ingestion source namespace for the sample.")
    source_id: str = Field(..., description="Stable upstream identifier for this sample.")
    start_at: str = Field(..., description="Stored ISO-8601 start timestamp.")
    end_at: str | None = Field(..., description="Stored ISO-8601 end timestamp, if present.")
    stage: str = Field(..., description="Normalized sleep stage label stored for the sample.")
    stage_value: int = Field(..., description="Source-specific numeric stage code stored for the sample.")
    source_bundle_id: str | None = Field(
        ..., description="Optional upstream application bundle identifier."
    )
    source_name: str | None = Field(..., description="Optional human-readable source name.")
    metadata: dict[str, JsonValue] = Field(
        ..., description="Decoded metadata JSON payload associated with the sample."
    )
    created_at: str = Field(..., description="SQLite creation timestamp for this row.")
    updated_at: str = Field(..., description="SQLite update timestamp for this row.")


class DeleteSleepResponse(BaseModel):
    """Deletion result for the sleep ingestion endpoint.

    This endpoint exists mainly for test cleanup and controlled maintenance. The
    server requires a source filter so callers cannot accidentally wipe all sleep
    data through the API.
    """

    deleted: int = Field(..., description="Number of rows deleted for the requested source.")


class HealthResponse(BaseModel):
    """Basic service health response.

    This confirms the FastAPI ingestion service is reachable and returns the API
    version exposed by this backend instance.
    """

    status: Literal["ok"] = Field(..., description="Fixed status indicating the server is healthy.")
    version: str = Field(..., description="Application API version exposed by this backend.")


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _sample_to_storage_dict(source: str, sample: SleepSampleIn) -> dict[str, object]:
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


def _require_int(value: object) -> int:
    if isinstance(value, int):
        return value
    raise TypeError(f"Expected int value, got {type(value).__name__}")


def _require_str(value: object) -> str:
    if isinstance(value, str):
        return value
    raise TypeError(f"Expected str value, got {type(value).__name__}")


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


def _row_to_api_model(row: StorageRow) -> SleepSampleOut:
    metadata = _decode_metadata(row.get("metadata_json"))
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
        metadata=metadata,
        created_at=_require_str(row["created_at"]),
        updated_at=_require_str(row["updated_at"]),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or load_settings()

    app = FastAPI(
        title="Health Quantification Ingestion API",
        version=API_VERSION,
        summary="Sleep ingestion API for the health_quantification toolkit.",
        description=(
            "HTTP ingestion boundary for normalized personal health data. "
            "This server currently exposes an idempotent sleep ingestion batch endpoint, "
            "sleep querying and cleanup routes, and a basic health probe."
        ),
    )

    def get_initialized_db_path() -> Path:
        initialize_database(active_settings.db_path)
        return active_settings.db_path

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Check backend health",
        description=(
            "Return a minimal liveness payload so operators, scripts, and AI clients can confirm "
            "that the ingestion backend is reachable and identify the API version."
        ),
    )
    def health() -> HealthResponse:
        """Return backend liveness status and API version.

        This endpoint is side-effect free and can be polled safely.
        """

        return HealthResponse(status="ok", version=API_VERSION)

    @app.post(
        "/ingest/sleep",
        response_model=SleepIngestResponse,
        summary="Ingest or update sleep samples",
        description=(
            "Validate and upsert a batch of normalized sleep samples into SQLite. "
            "Idempotency is guaranteed by storage on the pair of source and source_id, "
            "so re-sending the same exporter batch updates existing rows instead of creating duplicates."
        ),
    )
    def ingest_sleep(
        request: SleepIngestRequest,
        db_path: Path = Depends(get_initialized_db_path),
    ) -> SleepIngestResponse:
        """Upsert a batch of sleep stage samples.

        The request body represents one exporter snapshot. Each sample is translated to the
        storage contract and written with ON CONFLICT(source, source_id) DO UPDATE behavior.
        The response reports how many samples were processed and the current total row count
        for the same source after ingestion completes.
        """

        upserted = upsert_sleep_samples(
            db_path,
            [_sample_to_storage_dict(request.source, sample) for sample in request.samples],
        )
        total_samples = len(query_sleep_samples(db_path=db_path, source=request.source))
        return SleepIngestResponse(
            status="accepted",
            upserted=upserted,
            total_samples=total_samples,
        )

    @app.get(
        "/ingest/sleep",
        response_model=list[SleepSampleOut],
        summary="Query stored sleep samples",
        description=(
            "Return sleep samples from local storage, optionally filtered by source and by start time. "
            "from_date accepts either YYYY-MM-DD or an ISO-8601 timestamp. to_date accepts the same "
            "formats, and a plain date is expanded to the end of that UTC day so whole-day queries behave as expected."
        ),
    )
    def get_sleep_samples(
        db_path: Path = Depends(get_initialized_db_path),
        from_date: Annotated[
            str | None,
            Query(description="Optional lower bound for start_at. Accepts YYYY-MM-DD or ISO-8601."),
        ] = None,
        to_date: Annotated[
            str | None,
            Query(description="Optional upper bound for start_at. Accepts YYYY-MM-DD or ISO-8601."),
        ] = None,
        source: Annotated[
            str | None,
            Query(description="Optional exact source filter such as apple_health_ios."),
        ] = None,
    ) -> list[SleepSampleOut]:
        """Query persisted sleep samples with optional source and date filters.

        The filter is applied against the stored start_at timestamp. Clients can use either a
        date-only form for whole-day queries or a full ISO timestamp for precise range scans.
        """

        rows = query_sleep_samples(
            db_path=db_path,
            from_date=_normalize_from_date(from_date),
            to_date=_normalize_to_date(to_date),
            source=source,
        )
        return [_row_to_api_model(row) for row in rows]

    @app.delete(
        "/ingest/sleep",
        response_model=DeleteSleepResponse,
        summary="Delete stored sleep samples for one source",
        description=(
            "Delete stored sleep samples for a specific source. The source query parameter is required "
            "for safety so this maintenance endpoint cannot wipe every source accidentally. This route "
            "is intended mainly for integration-test cleanup and controlled local maintenance."
        ),
    )
    def delete_sleep(
        source: Annotated[
            str,
            Query(description="Required exact source namespace to delete, for example apple_health_ios."),
        ],
        db_path: Path = Depends(get_initialized_db_path),
    ) -> DeleteSleepResponse:
        """Delete all stored sleep samples for one source.

        This endpoint intentionally requires the source query parameter so deletion is scoped and safe.
        """

        deleted = delete_sleep_samples(db_path=db_path, source=source)
        return DeleteSleepResponse(deleted=deleted)

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
