from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from health_quantification.analysis.daily_summary import build_default_daily_summary
from health_quantification.analysis.sleep import (
    DaySleepMetrics,
    assign_samples_to_days,
    compute_analysis,
    compute_day_metrics,
)
from health_quantification.artifacts.chart import render_daily_card_svg
from health_quantification.config import load_settings
from health_quantification.storage import initialize_database, query_sleep_samples


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
        print(f"[WARNING] No sleep data for {', '.join(missing)}. Open the iOS app and sync for up-to-date analysis.", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="health_quant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    doctor_sub = doctor.add_subparsers(dest="doctor_command", required=True)
    doctor_sub.add_parser("config")

    db = subparsers.add_parser("db")
    db_sub = db.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("init")

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

    artifact = subparsers.add_parser("artifact")
    artifact_sub = artifact.add_subparsers(dest="artifact_command", required=True)
    daily_card = artifact_sub.add_parser("daily-card")
    daily_card.add_argument("--date", required=True)
    daily_card.add_argument("--output", required=True)

    return parser


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

    if args.command == "summary" and args.summary_command == "daily":
        summary = build_default_daily_summary(args.date, settings.timezone)
        if args.format == "json":
            print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
        else:
            print(f"date={summary.date} sleep_hours={summary.sleep_hours} steps={summary.steps}")
        return 0

    if args.command == "sleep" and args.sleep_command == "analyze":
        initialize_database(settings.db_path)
        samples = query_sleep_samples(db_path=settings.db_path)
        days_map = assign_samples_to_days(samples, settings.timezone)
        _check_data_freshness(days_map, settings.timezone)
        analysis = compute_analysis(samples, args.days, settings.timezone)
        if args.format == "json":
            print(json.dumps(analysis.to_dict(), indent=2, default=str))
        else:
            print(f"Period: {analysis.period_days} days | Samples: {analysis.total_samples}")
            print(f"Days with data: {analysis.days_with_data} | Missing: {analysis.days_missing}")
            print(f"Avg sleep: {analysis.avg_sleep_hours}h | Deep: {analysis.avg_deep_hours}h | Core: {analysis.avg_core_hours}h | REM: {analysis.avg_rem_hours}h")
            if analysis.avg_bedtime:
                print(f"Avg bedtime: {analysis.avg_bedtime} | Avg wake: {analysis.avg_wake_time}")
            if analysis.avg_efficiency:
                print(f"Avg efficiency: {analysis.avg_efficiency}%")
            for d in analysis.daily:
                if d.sample_count > 0:
                    marker = " (nap)" if d.has_nap else ""
                    print(f"  {d.date}: {d.total_sleep_hours}h sleep, {d.deep_sleep_hours}h deep, {d.rem_sleep_hours}h REM{marker}")
                else:
                    print(f"  {d.date}: no data")
        return 0

    if args.command == "sleep" and args.sleep_command == "daily":
        initialize_database(settings.db_path)
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
            print(f"Deep: {metrics.deep_sleep_hours}h | Core: {metrics.core_sleep_hours}h | REM: {metrics.rem_sleep_hours}h | Awake: {metrics.awake_hours}h")
            if metrics.sleep_efficiency:
                print(f"Efficiency: {metrics.sleep_efficiency}%")
            if metrics.has_nap:
                print("(nap)")
        return 0

    if args.command == "artifact" and args.artifact_command == "daily-card":
        initialize_database(settings.db_path)
        samples = query_sleep_samples(db_path=settings.db_path)
        metrics = compute_day_metrics(samples, args.date, settings.timezone)
        summary = build_default_daily_summary(args.date, settings.timezone)
        summary.sleep_hours = metrics.total_sleep_hours
        output = render_daily_card_svg(summary, Path(args.output))
        print(json.dumps({"status": "written", "output": str(output)}, indent=2))
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
