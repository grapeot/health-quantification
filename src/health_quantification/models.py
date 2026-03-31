from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(slots=True)
class Observation:
    metric: str
    value: float
    unit: str
    start_at: str
    end_at: str | None = None
    source: str = "unknown"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class DailySummary:
    date: str
    timezone: str
    sleep_hours: float | None
    resting_hr_bpm: float | None
    hrv_sdnn_ms: float | None
    steps: int | None
    active_energy_kcal: float | None
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
