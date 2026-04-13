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


def _sample_source_name(sample: dict[str, object]) -> str:
    source_name = sample.get("source_name")
    if isinstance(source_name, str) and source_name.strip():
        return source_name.strip()
    source_id = sample.get("source_id")
    if isinstance(source_id, str) and source_id.strip():
        return source_id.strip()
    source = sample.get("source")
    if isinstance(source, str) and source.strip():
        return source.strip()
    return "unknown"


def _is_watch_source(source_name: str) -> bool:
    return "watch" in source_name.lower()


def _build_step_estimate(metric_samples: list[dict[str, object]]) -> dict[str, object] | None:
    if not metric_samples:
        return None

    source_totals: dict[str, float] = defaultdict(float)
    for sample in metric_samples:
        source_totals[_sample_source_name(sample)] += _sample_value(sample)

    ordered_totals = [
        {"source_name": source_name, "steps": round(total, 3)}
        for source_name, total in sorted(source_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    if len(ordered_totals) == 1:
        only_total = ordered_totals[0]
        return {
            "estimated_steps": round(float(only_total["steps"])),
            "unit": "count",
            "method": "single_source_total",
            "explanation": f"Single source day from {only_total['source_name']}; using that source total directly.",
            "source_daily_totals": ordered_totals,
        }

    watch_sources = [item for item in ordered_totals if _is_watch_source(str(item["source_name"]))]
    if len(ordered_totals) == 2 and len(watch_sources) == 1:
        max_total = max(float(item["steps"]) for item in ordered_totals)
        estimated_steps = round(max_total * 1.05)
        watch_name = str(watch_sources[0]["source_name"])
        other_name = next(
            str(item["source_name"]) for item in ordered_totals if str(item["source_name"]) != watch_name
        )
        return {
            "estimated_steps": estimated_steps,
            "unit": "count",
            "method": "overlapping_sources_max_times_1.05",
            "explanation": (
                f"Detected overlapping watch/phone-like sources ({watch_name}, {other_name}); "
                "using max(source totals) * 1.05 per project rule."
            ),
            "source_daily_totals": ordered_totals,
        }

    return {
        "estimated_steps": None,
        "unit": "count",
        "method": "source_resolution_required",
        "explanation": (
            "Multiple sources present but overlap/complement relationship is ambiguous; "
            "returning source totals without a canonical estimate."
        ),
        "source_daily_totals": ordered_totals,
    }


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
                step_estimate=_build_step_estimate(day_samples) if metric_type == "step_count" else None,
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
            step_estimate=_build_step_estimate(metric_samples) if metric_type == "step_count" else None,
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
