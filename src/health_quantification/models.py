from __future__ import annotations

from dataclasses import asdict, dataclass


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


@dataclass(slots=True)
class BasicStats:
    count: int
    avg: float | None
    min: float | None
    max: float | None
    std: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class DailyMetricStats:
    date: str
    timezone: str
    metric_type: str
    unit: str | None
    stats: BasicStats

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class MetricAnalysisSummary:
    data_type: str
    metric_type: str
    period_days: int
    total_samples: int
    days_with_data: int
    days_missing: int
    daily: list[DailyMetricStats]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class MetricDailySummary:
    data_type: str
    date: str
    timezone: str
    total_samples: int
    metrics: list[DailyMetricStats]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
