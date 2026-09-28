from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient

from health_quantification.config import Settings
from health_quantification.server import ECG_MAX_BODY_BYTES, create_app


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


def build_workout_payload() -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
                "source_id": "workout-1",
                "workout_type": "HIIT",
                "start_at": "2026-03-31T08:00:00Z",
                "end_at": "2026-03-31T08:30:00Z",
                "duration_seconds": 1800.0,
                "total_energy_burned": 280.0,
                "total_distance_meters": None,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "metadata": {"device": "watch"},
            },
            {
                "source_id": "workout-2",
                "workout_type": "Outdoor Run",
                "start_at": "2026-04-01T08:00:00Z",
                "end_at": "2026-04-01T08:45:00Z",
                "duration_seconds": 2700.0,
                "total_energy_burned": 420.0,
                "total_distance_meters": 5000.0,
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


@pytest.mark.parametrize(
    ("endpoint", "payload_builder", "expected_total"),
    [
        ("sleep", build_sleep_payload, 2),
        ("vitals", build_vitals_payload, 2),
        ("body", build_body_payload, 2),
        ("lifestyle", build_lifestyle_payload, 2),
        ("activity", build_activity_payload, 2),
        ("workouts", build_workout_payload, 2),
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


def test_new_vitals_round_trip_and_upsert(tmp_path: Path) -> None:
    metrics = [
        ("sleeping_breathing_disturbances", "count", 2.0),
        ("sleeping_wrist_temperature", "degC", 35.8),
        ("heart_rate_variability_rmssd", "ms", 48.0),
        ("vo2_max", "ml/(kg*min)", 42.0),
    ]

    async def assertion(client: AsyncClient) -> None:
        payload = build_vitals_payload()
        template = cast(list[dict[str, object]], payload["samples"])[0]
        payload["samples"] = [
            {**template, "source_id": f"synthetic-{i}", "metric_type": metric, "unit": unit, "value": value}
            for i, (metric, unit, value) in enumerate(metrics)
        ]
        first = await client.post("/ingest/vitals", json=payload)
        second = await client.post("/ingest/vitals", json=payload)
        assert first.status_code == second.status_code == 200
        assert first.json()["total_samples"] == second.json()["total_samples"] == 4
        for metric, unit, value in metrics:
            response = await client.get("/ingest/vitals", params={"metric_type": metric})
            assert response.status_code == 200
            sample = response.json()[0]
            assert sample["unit"] == unit
            assert sample["value"] == value

    run_async_test(tmp_path, assertion)


@pytest.mark.parametrize(
    ("endpoint", "payload_builder", "expected_total"),
    [
        ("sleep", build_sleep_payload, 2),
        ("vitals", build_vitals_payload, 2),
        ("body", build_body_payload, 2),
        ("lifestyle", build_lifestyle_payload, 2),
        ("activity", build_activity_payload, 2),
        ("workouts", build_workout_payload, 2),
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
        (
            "workouts",
            build_workout_payload,
            {
                "from_date": "2026-03-31",
                "to_date": "2026-03-31",
                "source": "apple_health_ios",
            },
            "workout-1",
            None,
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
        ("workouts", build_workout_payload, 2),
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
        (
            "workouts",
            {
                "source": "apple_health_ios",
                "exported_at": "2026-03-31T02:35:56Z",
                "schema_version": "0.1.0",
                "samples": [{"source_id": "broken-sample", "workout_type": "HIIT"}],
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


@pytest.mark.parametrize("endpoint", ["sleep", "vitals", "body", "lifestyle", "activity", "workouts"])
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


@pytest.mark.parametrize("endpoint", ["sleep", "vitals", "body", "lifestyle", "activity", "workouts"])
def test_unknown_endpoint_returns_422(tmp_path: Path, endpoint: str) -> None:
    async def assertion(client: AsyncClient) -> None:
        response = await client.get("/ingest/nonexistent_type")
        assert response.status_code == 422

    run_async_test(tmp_path, assertion)


def build_ecg_payload() -> dict[str, object]:
    return {
        "source": "apple_health_ios",
        "exported_at": "2026-03-31T02:35:56Z",
        "schema_version": "0.1.0",
        "samples": [
            {
                "source_id": "ecg-synthetic-1",
                "start_at": "2026-03-31T02:00:00Z",
                "end_at": "2026-03-31T02:00:30Z",
                "algorithm_classification": "sinus_rhythm",
                "algorithm_classification_value": 1,
                "symptoms_status": "present",
                "symptoms_status_value": 2,
                "average_heart_rate_bpm": 72.0,
                "sampling_frequency_hz": 512.0,
                "number_of_voltage_measurements": 3,
                "voltage_count": 3,
                "voltage_unit": "V",
                "lead": "apple_watch_similar_to_lead_i",
                "voltage_status": "complete",
                "algorithm_version": 2,
                "source_bundle_id": "com.apple.health",
                "source_name": "Health",
                "symptoms": [
                    {
                        "symptom_type": "dizziness",
                        "severity": "mild",
                        "severity_value": 2,
                        "source_id": "symptom-synthetic-1",
                    }
                ],
                "symptoms_read_status": "complete",
                "metadata": {"apple_ecg_algorithm_version": "2"},
                "voltage": [
                    {"time_offset_seconds": 0.0, "voltage_volts": 0.00011},
                    {"time_offset_seconds": 0.001953125, "voltage_volts": -0.00022},
                    {"time_offset_seconds": 0.00390625, "voltage_volts": 0.00033},
                ],
            }
        ],
    }


def test_ecg_ingest_is_idempotent_and_list_omits_voltage(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        payload = build_ecg_payload()
        first = await client.post("/ingest/ecg", json=payload)
        second = await client.post("/ingest/ecg", json=payload)
        assert first.status_code == second.status_code == 200
        assert second.json()["total_samples"] == 1
        listed = await client.get("/ingest/ecg")
        assert listed.status_code == 200
        body = listed.json()
        assert body["not_a_diagnosis"] is True
        assert body["empty_result_does_not_prove_absence_or_normal"] is True
        assert body["records"][0]["algorithm_classification"] == "sinus_rhythm"
        assert body["records"][0]["classification_kind"] == "apple_watch_ecg_algorithm"
        assert "voltage" not in body["records"][0]
        assert "0.00011" not in listed.text

    run_async_test(tmp_path, assertion)


def test_ecg_voltage_export_requires_cap_and_does_not_affect_sleep(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        sleep = await client.post("/ingest/sleep", json=build_sleep_payload())
        assert sleep.status_code == 200
        created = await client.post("/ingest/ecg", json=build_ecg_payload())
        assert created.status_code == 200
        missing_cap = await client.get("/ingest/ecg/voltage", params={"source_id": "ecg-synthetic-1"})
        assert missing_cap.status_code == 422
        capped = await client.get(
            "/ingest/ecg/voltage",
            params={"source_id": "ecg-synthetic-1", "max_points": 1},
        )
        assert capped.status_code == 200
        voltage = capped.json()
        assert voltage["truncated"] is True
        assert voltage["returned_points"] == 1
        assert len(voltage["voltage"]) == 1
        assert voltage["not_a_diagnosis"] is True
        invalid = build_ecg_payload()
        sample = cast(list[dict[str, object]], invalid["samples"])[0]
        sample["source_id"] = "ecg-bad"
        sample["voltage_status"] = "complete"
        sample["voltage"] = []
        sample["voltage_count"] = 0
        rejected = await client.post("/ingest/ecg", json=invalid)
        assert rejected.status_code == 422
        sleep_rows = await client.get("/ingest/sleep")
        assert sleep_rows.status_code == 200
        assert len(sleep_rows.json()) == 2
        ecg_rows = await client.get("/ingest/ecg")
        assert [row["source_id"] for row in ecg_rows.json()["records"]] == ["ecg-synthetic-1"]

    run_async_test(tmp_path, assertion)


def test_ecg_partial_voltage_is_stored_and_empty_list_is_not_a_normal_result(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        empty = await client.get("/ingest/ecg")
        assert empty.status_code == 200
        assert empty.json()["records"] == []
        assert empty.json()["empty_result_does_not_prove_absence_or_normal"] is True
        payload = build_ecg_payload()
        sample = cast(list[dict[str, object]], payload["samples"])[0]
        sample["voltage_status"] = "partial"
        sample["voltage_error_code"] = "lead_voltage_missing"
        sample["voltage"] = [
            {"time_offset_seconds": 0.0, "voltage_volts": 0.00011},
            {"time_offset_seconds": 0.001953125, "voltage_volts": None},
        ]
        sample["voltage_count"] = 2
        sample["number_of_voltage_measurements"] = 3
        created = await client.post("/ingest/ecg", json=payload)
        assert created.status_code == 200
        listed = await client.get("/ingest/ecg")
        assert listed.json()["records"][0]["voltage_status"] == "partial"
        assert listed.json()["records"][0]["voltage_error_code"] == "lead_voltage_missing"

    run_async_test(tmp_path, assertion)


def test_failed_reexport_keeps_stored_complete_waveform(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        created = await client.post("/ingest/ecg", json=build_ecg_payload())
        assert created.status_code == 200
        degraded = build_ecg_payload()
        sample = cast(list[dict[str, object]], degraded["samples"])[0]
        sample["voltage_status"] = "query_failed"
        sample["voltage_error_code"] = "voltage_query_failed"
        sample["voltage"] = []
        sample["voltage_count"] = 0
        sample["number_of_voltage_measurements"] = 3
        replay = await client.post("/ingest/ecg", json=degraded)
        assert replay.status_code == 200
        listed = await client.get("/ingest/ecg", params={"source_id": "ecg-synthetic-1"})
        assert listed.status_code == 200
        record = listed.json()["records"][0]
        assert record["voltage_status"] == "complete"
        assert "voltage" not in record
        exported = await client.get(
            "/ingest/ecg/voltage",
            params={"source_id": "ecg-synthetic-1", "max_points": 3},
        )
        assert exported.status_code == 200
        assert exported.json()["truncated"] is False
        assert exported.json()["voltage"][0]["voltage_volts"] == 0.00011

    run_async_test(tmp_path, assertion)


def _ecg_http_sample(source_id: str, start_at: str) -> dict[str, object]:
    payload = build_ecg_payload()
    sample = cast(list[dict[str, object]], payload["samples"])[0]
    sample["source_id"] = source_id
    sample["start_at"] = start_at
    sample["end_at"] = start_at
    return payload


async def _asgi_post(
    app: object,
    path: str,
    chunks: list[bytes],
    headers: list[tuple[bytes, bytes]] | None = None,
) -> tuple[int, bytes]:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers or [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1234),
        "server": ("127.0.0.1", 80),
    }
    index = 0

    async def receive() -> dict[str, object]:
        nonlocal index
        if index >= len(chunks):
            return {"type": "http.request", "body": b"", "more_body": False}
        chunk = chunks[index]
        index += 1
        return {"type": "http.request", "body": chunk, "more_body": index < len(chunks)}

    status = 0
    body = bytearray()

    async def send(message: dict[str, object]) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = int(cast(int, message["status"]))
        elif message["type"] == "http.response.body":
            part = message.get("body", b"")
            if isinstance(part, bytes):
                body.extend(part)

    await cast(Callable[[dict[str, object], Callable[[], Awaitable[dict[str, object]]], Callable[[dict[str, object]], Awaitable[None]]], Awaitable[None]], app)(
        scope, receive, send
    )
    return status, bytes(body)


def test_ecg_http_dates_match_cli_local_day(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        created = await client.post(
            "/ingest/ecg",
            json={
                "source": "apple_health_ios",
                "exported_at": "2026-03-31T02:35:56Z",
                "schema_version": "0.1.0",
                "samples": [
                    cast(list[dict[str, object]], _ecg_http_sample("local-prev", "2026-03-31T06:00:00Z")["samples"])[0],
                    cast(list[dict[str, object]], _ecg_http_sample("local-end", "2026-04-01T06:30:00Z")["samples"])[0],
                    cast(list[dict[str, object]], _ecg_http_sample("local-next", "2026-04-01T07:30:00Z")["samples"])[0],
                ],
            },
        )
        assert created.status_code == 200
        listed = await client.get("/ingest/ecg", params={"from_date": "2026-03-31", "to_date": "2026-03-31"})
        assert listed.status_code == 200
        assert {row["source_id"] for row in listed.json()["records"]} == {"local-end"}
        offset = await client.get("/ingest/ecg", params={"from_date": "2026-03-31T23:45:00-07:00"})
        assert {row["source_id"] for row in offset.json()["records"]} == {"local-next"}
        rejected = await client.get("/ingest/ecg", params={"from_date": "2026-03-31T12:00:00"})
        assert rejected.status_code == 422
        assert "timezone offset" in rejected.text
        assert "2026-03-31T12:00:00" not in rejected.text

    run_async_test(tmp_path, assertion)


def test_ecg_http_date_includes_local_last_second(tmp_path: Path) -> None:
    async def assertion(client: AsyncClient) -> None:
        created = await client.post(
            "/ingest/ecg",
            json={
                "source": "apple_health_ios",
                "exported_at": "2026-03-31T02:35:56Z",
                "schema_version": "0.1.0",
                "samples": [
                    cast(list[dict[str, object]], _ecg_http_sample("last-second", "2026-04-01T06:59:59Z")["samples"])[0],
                    cast(list[dict[str, object]], _ecg_http_sample("next-midnight", "2026-04-01T07:00:00Z")["samples"])[0],
                    cast(list[dict[str, object]], _ecg_http_sample("same-second-later", "2026-04-01T06:59:59.200000Z")["samples"])[0],
                ],
            },
        )
        assert created.status_code == 200
        listed = await client.get("/ingest/ecg", params={"to_date": "2026-03-31"})
        ids = {row["source_id"] for row in listed.json()["records"]}
        assert "last-second" in ids
        assert "next-midnight" not in ids
        started = await client.get(
            "/ingest/ecg",
            params={"from_date": "2026-03-31T23:59:59.123456-07:00"},
        )
        start_ids = {row["source_id"] for row in started.json()["records"]}
        assert "last-second" not in start_ids
        assert "same-second-later" in start_ids

    run_async_test(tmp_path, assertion)


def test_ecg_validation_error_does_not_echo_values(tmp_path: Path) -> None:
    marker = "SYNTHETIC-PRIVATE-NOTE-0.000987654"

    async def assertion(client: AsyncClient) -> None:
        payload = build_ecg_payload()
        sample = cast(list[dict[str, object]], payload["samples"])[0]
        sample["voltage"] = [{"time_offset_seconds": 0.0, "voltage_volts": marker}]
        sample["voltage_count"] = 1
        rejected = await client.post("/ingest/ecg", json=payload)
        assert rejected.status_code == 422
        assert marker not in rejected.text
        assert "0.000987654" not in rejected.text
        assert "voltage_volts" in rejected.text

        sleep = build_sleep_payload()
        cast(list[dict[str, object]], sleep["samples"])[0]["unexpected_private"] = "SLEEP-EXTRA"
        sleep_rejected = await client.post("/ingest/sleep", json=sleep)
        assert sleep_rejected.status_code == 422
        assert "unexpected_private" in sleep_rejected.text

    run_async_test(tmp_path, assertion)


def test_ecg_body_limit_counts_bytes_without_content_length(tmp_path: Path) -> None:
    app = create_app(build_settings(tmp_path / "test_server.db"))
    marker = b"SYNTHETIC-VOLT-0.009876"

    async def assertion() -> None:
        oversized = marker + b"x" * (ECG_MAX_BODY_BYTES - len(marker) + 1)
        status, body = await _asgi_post(
            app,
            "/ingest/ecg",
            [oversized[:1000], oversized[1000:4000], oversized[4000:]],
        )
        assert status == 413
        assert marker not in body
        assert b"0.009876" not in body

        lying = [(b"content-type", b"application/json"), (b"content-length", b"12")]
        status, body = await _asgi_post(app, "/ingest/ecg", [oversized[:3], oversized[3:]], lying)
        assert status == 413
        assert marker not in body

        declared = [
            (b"content-type", b"application/json"),
            (b"content-length", str(ECG_MAX_BODY_BYTES + 1).encode("ascii")),
        ]
        status, body = await _asgi_post(app, "/ingest/ecg", [marker], declared)
        assert status == 413
        assert marker not in body

        sleep_status, _sleep_body = await _asgi_post(
            app,
            "/ingest/sleep",
            [b'{"samples":[]}'],
            [(b"content-type", b"application/json")],
        )
        assert sleep_status != 413

    asyncio.run(assertion())
