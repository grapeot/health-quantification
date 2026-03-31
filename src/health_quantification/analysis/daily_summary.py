from __future__ import annotations

from health_quantification.models import DailySummary


def build_default_daily_summary(date: str, timezone: str) -> DailySummary:
    return DailySummary(
        date=date,
        timezone=timezone,
        sleep_hours=None,
        resting_hr_bpm=None,
        hrv_sdnn_ms=None,
        steps=None,
        active_energy_kcal=None,
        notes=[
            "phase_1_placeholder",
            "native_apple_health_ingest_not_implemented",
        ],
    )
