import asyncio

from httpx import ASGITransport, AsyncClient

from health_quantification.server import create_app
from health_quantification.storage import count_samples
from tests.integration.test_server import build_settings, build_vitals_payload


def test_total_count_preserves_source_scope_and_repeat_upserts(tmp_path):
    async def exercise():
        settings = build_settings(tmp_path / "synthetic.db")
        async with AsyncClient(transport=ASGITransport(app=create_app(settings)), base_url="http://test") as client:
            first = await client.post("/ingest/vitals", json=build_vitals_payload())
            other = {**build_vitals_payload(), "source": "synthetic_other"}
            await client.post("/ingest/vitals", json=other)
            repeat = await client.post("/ingest/vitals", json=build_vitals_payload())
            assert first.json() == repeat.json() == {"status": "accepted", "upserted": 2, "total_samples": 2}
            assert count_samples(settings.db_path, table_name="vitals_samples") == 4
            assert count_samples(settings.db_path, table_name="vitals_samples", source="missing") == 0
    asyncio.run(exercise())
