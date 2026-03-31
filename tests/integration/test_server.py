from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient

from health_quantification.config import Settings
from health_quantification.server import create_app


def build_settings(db_path: Path) -> Settings:
    return Settings(
        db_path=db_path,
        export_dir=db_path.parent / "exports",
        timezone="America/Los_Angeles",
        live_tests_enabled=False,
        server_host="127.0.0.1",
        server_port=7980,
    )


def build_sleep_payload() -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
                "source_id": "sleep-1",
                "start_at": "2026-03-30T22:30:00Z",
                "end_at": "2026-03-31T00:30:00Z",
                "stage": "asleep_core",
                "stage_value": 2,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"device": "watch"},
            },
            {
                "source_id": "sleep-2",
                "start_at": "2026-03-31T00:30:00Z",
                "end_at": "2026-03-31T06:30:00Z",
                "stage": "asleep_deep",
                "stage_value": 3,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"device": "watch"},
            },
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
                "recorded_at": "2026-03-30T23:30:00Z",
                "metric_type": "resting_heart_rate",
                "value": 62.0,
                "unit": "count/min",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"device": "watch"},
            },
            {
                "source_id": "vitals-2",
                "recorded_at": "2026-03-31T23:30:00Z",
                "metric_type": "resting_heart_rate",
                "value": 58.0,
                "unit": "count/min",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"device": "watch"},
            },
        ],
    }


def build_body_payload() -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
                "source_id": "bp-1",
                "recorded_at": "2026-03-31T07:00:00Z",
                "metric_type": "blood_pressure_systolic",
                "value": 121.0,
                "unit": "mmHg",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"device": "cuff"},
            },
            {
                "source_id": "bp-1",
                "recorded_at": "2026-03-31T07:00:00Z",
                "metric_type": "blood_pressure_diastolic",
                "value": 79.0,
                "unit": "mmHg",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"device": "cuff"},
            },
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
                "metadata": {"beverage": "latte"},
            },
            {
                "source_id": "life-2",
                "recorded_at": "2026-04-01T03:00:00Z",
                "metric_type": "dietary_caffeine",
                "value": 90.0,
                "unit": "mg",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"beverage": "tea"},
            },
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
                "metadata": {"segment": "morning"},
            },
            {
                "source_id": "activity-2",
                "start_at": "2026-04-01T08:00:00Z",
                "end_at": "2026-04-01T09:00:00Z",
                "metric_type": "step_count",
                "value": 9200,
                "unit": "count",
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"segment": "evening"},
            },
        ],
    }


def run_async_test(
    tmp_path: Path,
    assertion_coro: Callable[[AsyncClient], Awaitable[None]],
) -> None:
    app = create_app(build_settings(tmp_path / "test_server.db"))

    async def runner() -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await assertion_coro(client)

    asyncio.run(runner())


@pytest.mark.parametrize(
    ("endpoint", "payload_builder", "expected_total"),
    [
        ("sleep", build_sleep_payload, 2),
        ("vitals", build_vitals_payload, 2),
        ("body", build_body_payload, 2),
        ("lifestyle", build_lifestyle_payload, 2),
        ("activity", build_activity_payload, 2),
    ],
)
def test_post_endpoint_returns_counts(
    tmp_path: Path,
    endpoint: str,
    payload_builder: Callable[[], dict[str, object]],
    expected_total: int,
) -> None:
    async def assertion(client: AsyncClient) -> None:
        response = await client.post(f"/ingest/{endpoint}", json=payload_builder())
        assert response.status_code == 200
        assert response.json() == {
            "status": "accepted",
            "upserted": expected_total,
            "total_samples": expected_total,
        }

    run_async_test(tmp_path, assertion)


@pytest.mark.parametrize(
    ("endpoint", "payload_builder", "expected_total"),
    [
        ("sleep", build_sleep_payload, 2),
        ("vitals", build_vitals_payload, 2),
        ("body", build_body_payload, 2),
        ("lifestyle", build_lifestyle_payload, 2),
        ("activity", build_activity_payload, 2),
    ],
)
def test_post_endpoint_is_idempotent(
    tmp_path: Path,
    endpoint: str,
    payload_builder: Callable[[], dict[str, object]],
    expected_total: int,
) -> None:
    async def assertion(client: AsyncClient) -> None:
        payload = payload_builder()
        first = await client.post(f"/ingest/{endpoint}", json=payload)
        second = await client.post(f"/ingest/{endpoint}", json=payload)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json() == {
            "status": "accepted",
            "upserted": expected_total,
            "total_samples": expected_total,
        }

    run_async_test(tmp_path, assertion)


@pytest.mark.parametrize(
    ("endpoint", "payload_builder", "params", "expected_source_id", "expected_metric_type"),
    [
        (
            "sleep",
            build_sleep_payload,
            {"from_date": "2026-03-31", "to_date": "2026-03-31", "source": "apple_health_ios"},
            "sleep-2",
            None,
        ),
        (
            "vitals",
            build_vitals_payload,
            {
                "from_date": "2026-03-31",
                "to_date": "2026-03-31",
                "source": "apple_health_ios",
                "metric_type": "resting_heart_rate",
            },
            "vitals-2",
            "resting_heart_rate",
        ),
        (
            "body",
            build_body_payload,
            {
                "from_date": "2026-03-31",
                "to_date": "2026-03-31",
                "source": "apple_health_ios",
                "metric_type": "blood_pressure_diastolic",
            },
            "bp-1",
            "blood_pressure_diastolic",
        ),
        (
            "lifestyle",
            build_lifestyle_payload,
            {
                "from_date": "2026-03-31",
                "to_date": "2026-03-31",
                "source": "apple_health_ios",
                "metric_type": "dietary_caffeine",
            },
            "life-1",
            "dietary_caffeine",
        ),
        (
            "activity",
            build_activity_payload,
            {
                "from_date": "2026-03-31",
                "to_date": "2026-03-31",
                "source": "apple_health_ios",
                "metric_type": "step_count",
            },
            "activity-1",
            "step_count",
        ),
    ],
)
def test_get_endpoint_supports_filters(
    tmp_path: Path,
    endpoint: str,
    payload_builder: Callable[[], dict[str, object]],
    params: dict[str, str],
    expected_source_id: str,
    expected_metric_type: str | None,
) -> None:
    async def assertion(client: AsyncClient) -> None:
        _ = await client.post(f"/ingest/{endpoint}", json=payload_builder())
        response = await client.get(f"/ingest/{endpoint}", params=params)
        assert response.status_code == 200
        body = cast(list[dict[str, object]], response.json())
        assert len(body) == 1
        assert body[0]["source_id"] == expected_source_id
        if expected_metric_type is not None:
            assert body[0]["metric_type"] == expected_metric_type

    run_async_test(tmp_path, assertion)


@pytest.mark.parametrize(
    ("endpoint", "payload_builder", "expected_deleted"),
    [
        ("sleep", build_sleep_payload, 2),
        ("vitals", build_vitals_payload, 2),
        ("body", build_body_payload, 2),
        ("lifestyle", build_lifestyle_payload, 2),
        ("activity", build_activity_payload, 2),
    ],
)
def test_delete_endpoint_cleans_up_rows(
    tmp_path: Path,
    endpoint: str,
    payload_builder: Callable[[], dict[str, object]],
    expected_deleted: int,
) -> None:
    async def assertion(client: AsyncClient) -> None:
        _ = await client.post(f"/ingest/{endpoint}", json=payload_builder())
        delete_response = await client.delete(
            f"/ingest/{endpoint}", params={"source": "apple_health_ios"}
        )
        get_response = await client.get(
            f"/ingest/{endpoint}", params={"source": "apple_health_ios"}
        )
        assert delete_response.status_code == 200
        assert delete_response.json() == {"deleted": expected_deleted}
        assert get_response.status_code == 200
        assert get_response.json() == []

    run_async_test(tmp_path, assertion)


def test_health_endpoint_returns_status(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "0.1.0"}

    run_async_test(tmp_path, assertion)


@pytest.mark.parametrize(
    ("endpoint", "invalid_payload"),
    [
        (
            "sleep",
            {
                "source": "apple_health_ios",
                "exported_at": "2026-03-31T02:35:56Z",
                "schema_version": "0.1.0",
                "samples": [{"source_id": "broken-sample"}],
            },
        ),
        (
            "vitals",
            {
                "source": "apple_health_ios",
                "exported_at": "2026-03-31T02:35:56Z",
                "schema_version": "0.1.0",
                "samples": [{"source_id": "broken-sample", "metric_type": "vo2_max"}],
            },
        ),
        (
            "body",
            {
                "source": "apple_health_ios",
                "exported_at": "2026-03-31T02:35:56Z",
                "schema_version": "0.1.0",
                "samples": [{"source_id": "broken-sample", "metric_type": "body_fat_percentage"}],
            },
        ),
        (
            "lifestyle",
            {
                "source": "apple_health_ios",
                "exported_at": "2026-03-31T02:35:56Z",
                "schema_version": "0.1.0",
                "samples": [{"source_id": "broken-sample", "metric_type": "water_intake"}],
            },
        ),
        (
            "activity",
            {
                "source": "apple_health_ios",
                "exported_at": "2026-03-31T02:35:56Z",
                "schema_version": "0.1.0",
                "samples": [{"source_id": "broken-sample", "metric_type": "distance_walking_running"}],
            },
        ),
    ],
)
def test_invalid_request_body_returns_422(
    tmp_path: Path,
    endpoint: str,
    invalid_payload: dict[str, object],
) -> None:
    async def assertion(client: AsyncClient) -> None:
        response = await client.post(f"/ingest/{endpoint}", json=invalid_payload)
        assert response.status_code == 422

    run_async_test(tmp_path, assertion)


@pytest.mark.parametrize("endpoint", ["sleep", "vitals", "body", "lifestyle", "activity"])
def test_empty_samples_list_returns_422(tmp_path: Path, endpoint: str) -> None:
    async def assertion(client: AsyncClient) -> None:
        payload = {
            "source": "apple_health_ios",
            "exported_at": "2026-03-31T02:35:56Z",
            "schema_version": "0.1.0",
            "samples": [],
        }
        response = await client.post(f"/ingest/{endpoint}", json=payload)
        assert response.status_code == 422

    run_async_test(tmp_path, assertion)


@pytest.mark.parametrize("endpoint", ["sleep", "vitals", "body", "lifestyle", "activity"])
def test_unknown_endpoint_returns_422(tmp_path: Path, endpoint: str) -> None:
    async def assertion(client: AsyncClient) -> None:
        response = await client.get("/ingest/nonexistent_type")
        assert response.status_code == 422

    run_async_test(tmp_path, assertion)
