from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import sqrt

from zoneinfo import ZoneInfo

from health_quantification.models import (
    BasicStats,
    DailyMetricStats,
    MetricAnalysisSummary,
    MetricDailySummary,
)


def _timezone(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def _parse_timestamp(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _to_local_date(timestamp: str, tz_name: str) -> str:
    return _parse_timestamp(timestamp).astimezone(_timezone(tz_name)).date().isoformat()


def _sample_timestamp(sample: dict[str, object]) -> str:
    end_at = sample.get("end_at")
    if isinstance(end_at, str):
        return end_at
    start_at = sample.get("start_at")
    if isinstance(start_at, str):
        return start_at
    recorded_at = sample.get("recorded_at")
    if isinstance(recorded_at, str):
        return recorded_at
    raise ValueError("sample does not contain a supported timestamp field")


def _sample_unit(samples: list[dict[str, object]]) -> str | None:
    for sample in samples:
        unit = sample.get("unit")
        if isinstance(unit, str):
            return unit
    return None


def _sample_value(sample: dict[str, object]) -> float:
    value = sample.get("value")
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError("sample value must be numeric")


def compute_basic_stats(values: list[float]) -> BasicStats:
    if not values:
        return BasicStats(count=0, avg=None, min=None, max=None, std=None)

    count = len(values)
    average = sum(values) / count
    variance = sum((value - average) ** 2 for value in values) / count
    return BasicStats(
        count=count,
        avg=round(average, 3),
        min=round(min(values), 3),
        max=round(max(values), 3),
        std=round(sqrt(variance), 3),
    )


def compute_metric_analysis(
    *,
    samples: list[dict[str, object]],
    data_type: str,
    metric_type: str,
    days: int,
    tz_name: str,
) -> MetricAnalysisSummary:
    matching_samples = [sample for sample in samples if sample.get("metric_type") == metric_type]
    buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    for sample in matching_samples:
        buckets[_to_local_date(_sample_timestamp(sample), tz_name)].append(sample)

    end_date = datetime.now(_timezone(tz_name)).date()
    start_date = end_date - timedelta(days=days - 1)
    all_dates = [(start_date + timedelta(days=offset)).isoformat() for offset in range(days)]

    daily: list[DailyMetricStats] = []
    for date_str in all_dates:
        day_samples = buckets.get(date_str, [])
        values = [_sample_value(sample) for sample in day_samples]
        daily.append(
            DailyMetricStats(
                date=date_str,
                timezone=tz_name,
                metric_type=metric_type,
                unit=_sample_unit(day_samples),
                stats=compute_basic_stats(values),
            )
        )

    days_with_data = sum(1 for item in daily if item.stats.count > 0)
    return MetricAnalysisSummary(
        data_type=data_type,
        metric_type=metric_type,
        period_days=days,
        total_samples=len(matching_samples),
        days_with_data=days_with_data,
        days_missing=days - days_with_data,
        daily=daily,
    )


def compute_metric_daily_summary(
    *,
    samples: list[dict[str, object]],
    data_type: str,
    date_str: str,
    tz_name: str,
) -> MetricDailySummary:
    day_samples = [
        sample for sample in samples if _to_local_date(_sample_timestamp(sample), tz_name) == date_str
    ]
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for sample in day_samples:
        metric_type = str(sample["metric_type"])
        grouped[metric_type].append(sample)

    metrics = [
        DailyMetricStats(
            date=date_str,
            timezone=tz_name,
            metric_type=metric_type,
            unit=_sample_unit(metric_samples),
            stats=compute_basic_stats([_sample_value(sample) for sample in metric_samples]),
        )
        for metric_type, metric_samples in sorted(grouped.items())
    ]
    return MetricDailySummary(
        data_type=data_type,
        date=date_str,
        timezone=tz_name,
        total_samples=len(day_samples),
        metrics=metrics,
    )
