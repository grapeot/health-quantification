import asyncio
import re

from httpx import ASGITransport, AsyncClient

from health_quantification.server import create_app
from tests.integration.test_server import build_settings, build_vitals_payload


def test_timings_are_opt_in_and_do_not_change_ingest_result(tmp_path):
    async def exercise():
        app = create_app(build_settings(tmp_path / "synthetic.db"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            plain = await client.post("/ingest/vitals", json=build_vitals_payload())
            profiled = await client.post("/ingest/vitals", json=build_vitals_payload(),
                                         headers={"X-Health-Profile": "456EEB81-F801-4F0A-9C3F-9C9AFD9AB123"})
            assert plain.status_code == profiled.status_code == 200
            assert plain.json() == profiled.json()
            assert "Server-Timing" not in plain.headers
            timings = dict(re.findall(r"(\w+);dur=([\d.]+)", profiled.headers["Server-Timing"]))
            assert set(timings) == {"initialize", "convert", "upsert", "count", "total"}
            assert all(float(value) >= 0 for value in timings.values())
            invalid = await client.post("/ingest/vitals", json=build_vitals_payload(), headers={"X-Health-Profile": "bad"})
            assert "Server-Timing" not in invalid.headers
    asyncio.run(exercise())
