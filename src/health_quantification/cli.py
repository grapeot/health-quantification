from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime, timedelta

from health_quantification.analysis.metrics import (
    compute_metric_analysis,
    compute_metric_daily_summary,
)
from health_quantification.analysis.sleep import (
    assign_samples_to_days,
    compute_analysis,
    compute_day_metrics,
)
from health_quantification.config import load_settings
from health_quantification.models import MetricAnalysisSummary, MetricDailySummary
from health_quantification.storage import (
    initialize_database,
    query_activity_samples,
    query_body_samples,
    query_lifestyle_samples,
    query_sleep_samples,
    query_vitals_samples,
    record_sample,
)


def _check_data_freshness(days_map: dict[str, list[dict[str, object]]], tz_name: str) -> None:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date().isoformat()
    yesterday = (datetime.now(tz).date() - timedelta(days=1)).isoformat()
    missing: list[str] = []
    if not days_map.get(today):
        missing.append(today)
    if not days_map.get(yesterday):
        missing.append(yesterday)
    if missing:
        print(
            f"[WARNING] No sleep data for {', '.join(missing)}. Open the iOS app and sync for up-to-date analysis.",
            file=sys.stderr,
        )


def _add_metric_commands(command_name: str, subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = subparsers.add_parser(command_name)
    command_sub = command.add_subparsers(dest=f"{command_name}_command", required=True)

    analyze = command_sub.add_parser("analyze")
    analyze.add_argument("--days", type=int, default=30)
    analyze.add_argument("--metric", required=True)
    analyze.add_argument("--format", choices=["json", "text"], default="json")

    daily = command_sub.add_parser("daily")
    daily.add_argument("--date", required=True)
    daily.add_argument("--format", choices=["json", "text"], default="json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="health_quant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    doctor_sub = doctor.add_subparsers(dest="doctor_command", required=True)
    doctor_sub.add_parser("config")

    db = subparsers.add_parser("db")
    db_sub = db.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("init")

    record = subparsers.add_parser("record")
    record.add_argument(
        "data_type", choices=["lifestyle", "body", "vitals", "activity", "sleep"]
    )
    record.add_argument("--metric", required=True)
    record.add_argument("--value", type=float, required=True)
    record.add_argument("--unit", required=True)
    record.add_argument("--time")
    record.add_argument("--source")
    record.add_argument("--note")

    summary = subparsers.add_parser("summary")
    summary_sub = summary.add_subparsers(dest="summary_command", required=True)
    summary_daily = summary_sub.add_parser("daily")
    summary_daily.add_argument("--date", required=True)
    summary_daily.add_argument("--format", choices=["json", "text"], default="json")

    sleep = subparsers.add_parser("sleep")
    sleep_sub = sleep.add_subparsers(dest="sleep_command", required=True)

    sleep_analyze = sleep_sub.add_parser("analyze")
    sleep_analyze.add_argument("--days", type=int, default=30)
    sleep_analyze.add_argument("--format", choices=["json", "text"], default="json")

    sleep_daily = sleep_sub.add_parser("daily")
    sleep_daily.add_argument("--date", required=True)
    sleep_daily.add_argument("--format", choices=["json", "text"], default="json")

    for command_name in ("vitals", "body", "lifestyle", "activity"):
        _add_metric_commands(command_name, subparsers)

    return parser


def _print_metric_analysis_text(summary: MetricAnalysisSummary) -> None:
    print(f"Data type: {summary.data_type} | Metric: {summary.metric_type}")
    print(
        f"Period: {summary.period_days} days | Samples: {summary.total_samples} | Days with data: {summary.days_with_data} | Missing: {summary.days_missing}"
    )
    for day in summary.daily:
        if day.stats.count == 0:
            print(f"  {day.date}: no data")
            continue
        print(
            f"  {day.date}: count={day.stats.count} avg={day.stats.avg} min={day.stats.min} max={day.stats.max} std={day.stats.std} unit={day.unit}"
        )


def _print_metric_daily_text(summary: MetricDailySummary) -> None:
    print(f"Data type: {summary.data_type} | Date: {summary.date} | Samples: {summary.total_samples}")
    for metric in summary.metrics:
        print(
            f"  {metric.metric_type}: count={metric.stats.count} avg={metric.stats.avg} min={metric.stats.min} max={metric.stats.max} std={metric.stats.std} unit={metric.unit}"
        )
    if not summary.metrics:
        print("  no data")


def _run_metric_command(
    *,
    data_type: str,
    command: str,
    query_fn: Callable[..., list[dict[str, object]]],
    args: argparse.Namespace,
    timezone: str,
) -> int:
    samples = query_fn()
    if command == "analyze":
        summary = compute_metric_analysis(
            samples=samples,
            data_type=data_type,
            metric_type=args.metric,
            days=args.days,
            tz_name=timezone,
        )
        if args.format == "json":
            print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
        else:
            _print_metric_analysis_text(summary)
        return 0

    if command == "daily":
        summary = compute_metric_daily_summary(
            samples=samples,
            data_type=data_type,
            date_str=args.date,
            tz_name=timezone,
        )
        if args.format == "json":
            print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
        else:
            _print_metric_daily_text(summary)
        return 0

    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "doctor" and args.doctor_command == "config":
        print(json.dumps(settings.to_public_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "db" and args.db_command == "init":
        initialize_database(settings.db_path)
        print(json.dumps({"status": "initialized", "db_path": str(settings.db_path)}, indent=2))
        return 0

    if args.command == "record":
        initialize_database(settings.db_path)
        metadata: dict[str, object] = {}
        if args.note:
            metadata["note"] = args.note
        sample: dict[str, object] = {
            "source": args.source,
            "metadata": metadata,
        }
        if args.data_type == "sleep":
            sample["start_at"] = args.time
            sample["end_at"] = args.time
            sample["stage"] = args.metric
            sample["stage_value"] = int(args.value)
        elif args.data_type == "activity":
            sample["start_at"] = args.time
            sample["metric_type"] = args.metric
            sample["value"] = args.value
            sample["unit"] = args.unit
        else:
            sample["recorded_at"] = args.time
            sample["metric_type"] = args.metric
            sample["value"] = args.value
            sample["unit"] = args.unit
        result = record_sample(settings.db_path, args.data_type, sample)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "summary" and args.summary_command == "daily":
        from health_quantification.analysis.daily_summary import build_default_daily_summary

        summary = build_default_daily_summary(args.date, settings.timezone)
        if args.format == "json":
            print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
        else:
            print(f"date={summary.date} sleep_hours={summary.sleep_hours} steps={summary.steps}")
        return 0

    initialize_database(settings.db_path)

    if args.command == "sleep" and args.sleep_command == "analyze":
        samples = query_sleep_samples(db_path=settings.db_path)
        days_map = assign_samples_to_days(samples, settings.timezone)
        _check_data_freshness(days_map, settings.timezone)
        analysis = compute_analysis(samples, args.days, settings.timezone)
        if args.format == "json":
            print(json.dumps(analysis.to_dict(), indent=2, default=str))
        else:
            print(f"Period: {analysis.period_days} days | Samples: {analysis.total_samples}")
            print(f"Days with data: {analysis.days_with_data} | Missing: {analysis.days_missing}")
            print(
                f"Avg sleep: {analysis.avg_sleep_hours}h | Deep: {analysis.avg_deep_hours}h | Core: {analysis.avg_core_hours}h | REM: {analysis.avg_rem_hours}h"
            )
            if analysis.avg_bedtime:
                print(f"Avg bedtime: {analysis.avg_bedtime} | Avg wake: {analysis.avg_wake_time}")
            if analysis.avg_efficiency:
                print(f"Avg efficiency: {analysis.avg_efficiency}%")
            for day in analysis.daily:
                if day.sample_count > 0:
                    marker = " (nap)" if day.has_nap else ""
                    print(
                        f"  {day.date}: {day.total_sleep_hours}h sleep, {day.deep_sleep_hours}h deep, {day.rem_sleep_hours}h REM{marker}"
                    )
                else:
                    print(f"  {day.date}: no data")
        return 0

    if args.command == "sleep" and args.sleep_command == "daily":
        samples = query_sleep_samples(db_path=settings.db_path)
        days_map = assign_samples_to_days(samples, settings.timezone)
        _check_data_freshness(days_map, settings.timezone)
        day_samples = days_map.get(args.date, [])
        metrics = compute_day_metrics(day_samples, args.date, settings.timezone)
        if args.format == "json":
            print(json.dumps(metrics.to_dict(), indent=2))
        else:
            print(f"Date: {metrics.date} | Samples: {metrics.sample_count}")
            print(f"Sleep: {metrics.total_sleep_hours}h | In bed: {metrics.total_in_bed_hours}h")
            if metrics.bedtime:
                print(f"Bedtime: {metrics.bedtime} | Wake: {metrics.wake_time}")
            print(
                f"Deep: {metrics.deep_sleep_hours}h | Core: {metrics.core_sleep_hours}h | REM: {metrics.rem_sleep_hours}h | Awake: {metrics.awake_hours}h"
            )
            if metrics.sleep_efficiency:
                print(f"Efficiency: {metrics.sleep_efficiency}%")
            if metrics.has_nap:
                print("(nap)")
        return 0

    metric_queries: dict[str, Callable[..., list[dict[str, object]]]] = {
        "vitals": lambda: query_vitals_samples(db_path=settings.db_path),
        "body": lambda: query_body_samples(db_path=settings.db_path),
        "lifestyle": lambda: query_lifestyle_samples(db_path=settings.db_path),
        "activity": lambda: query_activity_samples(db_path=settings.db_path),
    }
    if args.command in metric_queries:
        return _run_metric_command(
            data_type=args.command,
            command=getattr(args, f"{args.command}_command"),
            query_fn=metric_queries[args.command],
            args=args,
            timezone=settings.timezone,
        )

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
