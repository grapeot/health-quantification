from __future__ import annotations

import asyncio
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import TypedDict, cast

from httpx import ASGITransport, AsyncClient

from health_quantification.config import Settings
from health_quantification.server import create_app


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


def build_settings(db_path: Path) -> Settings:
    return Settings(
        db_path=db_path,
        export_dir=db_path.parent / "exports",
        timezone="America/Los_Angeles",
        live_tests_enabled=False,
        server_host="127.0.0.1",
        server_port=7980,
    )


def build_payload() -> SleepIngestPayload:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
                "source_id": "sample-1",
                "start_at": "2026-03-30T22:30:00Z",
                "end_at": "2026-03-31T00:30:00Z",
                "stage": "asleep_core",
                "stage_value": 2,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"device": "watch"},
            },
            {
                "source_id": "sample-2",
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


def test_post_valid_sleep_samples_returns_counts(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        response = await client.post("/ingest/sleep", json=build_payload())

        assert response.status_code == 200
        assert response.json() == {"status": "accepted", "upserted": 2, "total_samples": 2}

    run_async_test(tmp_path, assertion)


def test_post_duplicate_sleep_samples_is_idempotent(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        payload = build_payload()

        first = await client.post("/ingest/sleep", json=payload)
        second = await client.post("/ingest/sleep", json=payload)

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json() == {"status": "accepted", "upserted": 2, "total_samples": 2}

    run_async_test(tmp_path, assertion)


def test_get_sleep_samples_supports_date_filters(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        _ = await client.post("/ingest/sleep", json=build_payload())

        response = await client.get(
            "/ingest/sleep",
            params={"from_date": "2026-03-31", "to_date": "2026-03-31", "source": "apple_health_ios"},
        )

        assert response.status_code == 200
        body = cast(list[dict[str, object]], response.json())
        assert len(body) == 1
        assert body[0]["source_id"] == "sample-2"
        assert body[0]["metadata"] == {"device": "watch"}

    run_async_test(tmp_path, assertion)


def test_delete_sleep_samples_with_source_cleans_up_rows(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        _ = await client.post("/ingest/sleep", json=build_payload())

        delete_response = await client.delete("/ingest/sleep", params={"source": "apple_health_ios"})
        get_response = await client.get("/ingest/sleep", params={"source": "apple_health_ios"})

        assert delete_response.status_code == 200
        assert delete_response.json() == {"deleted": 2}
        assert get_response.status_code == 200
        assert get_response.json() == []

    run_async_test(tmp_path, assertion)


def test_health_endpoint_returns_status(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "0.1.0"}

    run_async_test(tmp_path, assertion)


def test_invalid_request_body_returns_422(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        response = await client.post(
            "/ingest/sleep",
            json={
                "source": "apple_health_ios",
                "exported_at": "2026-03-31T02:35:56Z",
                "schema_version": "0.1.0",
                "samples": [{"source_id": "broken-sample"}],
            },
        )

        assert response.status_code == 422

    run_async_test(tmp_path, assertion)
