from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from health_quantification.analysis.metrics import (
    compute_metric_analysis,
    compute_metric_daily_summary,
)
from health_quantification.analysis.sleep import (
    DaySleepMetrics,
    assign_samples_to_days,
    compute_analysis,
    compute_day_metrics,
)
from health_quantification.config import load_settings
from health_quantification.models import MetricAnalysisSummary, MetricDailySummary
from health_quantification.storage import (
    initialize_database,
    query_illness_episodes,
    query_activity_samples,
    query_body_samples,
    query_lifestyle_samples,
    query_sleep_samples,
    query_vitals_samples,
    query_workout_samples,
    record_illness_episode,
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


def _workout_samples_as_metric_rows(samples: list[dict[str, object]]) -> list[dict[str, object]]:
    metric_rows: list[dict[str, object]] = []
    for sample in samples:
        duration_seconds = sample.get("duration_seconds")
        start_at = sample.get("start_at")
        end_at = sample.get("end_at")
        if not isinstance(duration_seconds, (int, float)):
            continue
        if not isinstance(start_at, str) or not isinstance(end_at, str):
            continue
        metric_rows.append(
            {
                "metric_type": "duration_seconds",
                "value": float(duration_seconds),
                "unit": "seconds",
                "start_at": start_at,
                "end_at": end_at,
            }
        )
    return metric_rows


def _print_illness_text(episodes: list[dict[str, object]]) -> None:
    if not episodes:
        print("No illness episodes found.")
        return

    for episode in episodes:
        print(
            (
                f"[{episode['status']}] {episode['start_at']} -> {episode.get('end_at') or 'ongoing'} "
                f"label={episode['label']} severity={episode['severity']} source={episode['source']}"
            )
        )
        notes_value = episode.get("notes")
        notes = notes_value if isinstance(notes_value, list) else []
        for note in notes:
            print(f"  - {note}")
        metadata_value = episode.get("metadata")
        metadata = metadata_value if isinstance(metadata_value, dict) else {}
        symptoms_value = metadata.get("symptoms")
        symptoms = symptoms_value if isinstance(symptoms_value, list) else []
        if symptoms:
            print(f"  symptoms: {', '.join(str(symptom) for symptom in symptoms)}")


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

    illness = subparsers.add_parser("illness")
    illness_sub = illness.add_subparsers(dest="illness_command", required=True)

    illness_record = illness_sub.add_parser("record")
    illness_record.add_argument("--label", required=True)
    illness_record.add_argument(
        "--severity", choices=["mild", "moderate", "severe", "unknown"], default="unknown"
    )
    illness_record.add_argument("--status", choices=["active", "resolved"], default="active")
    illness_record.add_argument("--start-time", required=True)
    illness_record.add_argument("--end-time")
    illness_record.add_argument("--source")
    illness_record.add_argument("--source-id")
    illness_record.add_argument("--note", action="append", default=[])
    illness_record.add_argument("--symptom", action="append", default=[])
    illness_record.add_argument("--progression", action="append", default=[])

    illness_list = illness_sub.add_parser("list")
    illness_list.add_argument("--from-date")
    illness_list.add_argument("--to-date")
    illness_list.add_argument("--source")
    illness_list.add_argument("--status", choices=["active", "resolved", "all"], default="all")
    illness_list.add_argument("--format", choices=["json", "text"], default="json")

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
    sleep_daily.add_argument("--date")
    sleep_daily.add_argument("--last-night", action="store_true", default=False)
    sleep_daily.add_argument("--format", choices=["json", "text"], default="json")

    for command_name in ("vitals", "body", "lifestyle", "activity"):
        _add_metric_commands(command_name, subparsers)

    workouts = subparsers.add_parser("workouts")
    workouts_sub = workouts.add_subparsers(dest="workouts_command", required=True)

    workouts_analyze = workouts_sub.add_parser("analyze")
    workouts_analyze.add_argument("--days", type=int, default=30)
    workouts_analyze.add_argument("--format", choices=["json", "text"], default="json")

    workouts_daily = workouts_sub.add_parser("daily")
    workouts_daily.add_argument("--date", required=True)
    workouts_daily.add_argument("--format", choices=["json", "text"], default="json")

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
        if day.step_estimate is not None:
            print(
                "    step_estimate: "
                f"estimated_steps={day.step_estimate.get('estimated_steps')} "
                f"method={day.step_estimate.get('method')}"
            )


def _print_metric_daily_text(summary: MetricDailySummary) -> None:
    print(f"Data type: {summary.data_type} | Date: {summary.date} | Samples: {summary.total_samples}")
    for metric in summary.metrics:
        print(
            f"  {metric.metric_type}: count={metric.stats.count} avg={metric.stats.avg} min={metric.stats.min} max={metric.stats.max} std={metric.stats.std} unit={metric.unit}"
        )
        if metric.step_estimate is not None:
            print(
                "    step_estimate: "
                f"estimated_steps={metric.step_estimate.get('estimated_steps')} "
                f"method={metric.step_estimate.get('method')}"
            )
    if not summary.metrics:
        print("  no data")


def _print_sleep_sessions(metrics: DaySleepMetrics) -> None:
    sessions = metrics.sessions or []
    if not sessions:
        return

    print("Sessions:")
    for session in sessions:
        print(
            f"  [{session.session_type}] {session.start_local} -> {session.end_local} "
            f"sleep={session.sleep_hours}h in_bed={session.in_bed_hours}h "
            f"deep={session.deep_sleep_hours}h core={session.core_sleep_hours}h "
            f"rem={session.rem_sleep_hours}h awake={session.awake_hours}h "
            f"unspecified={session.unspecified_hours}h"
        )


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

    if args.command == "illness" and args.illness_command == "record":
        initialize_database(settings.db_path)
        metadata: dict[str, object] = {}
        if args.symptom:
            metadata["symptoms"] = args.symptom
        if args.progression:
            metadata["progression"] = args.progression
        result = record_illness_episode(
            settings.db_path,
            {
                "source": args.source,
                "source_id": args.source_id,
                "label": args.label,
                "severity": args.severity,
                "status": args.status,
                "start_at": args.start_time,
                "end_at": args.end_time,
                "notes": args.note,
                "metadata": metadata,
            },
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "illness" and args.illness_command == "list":
        initialize_database(settings.db_path)
        query_status = None if args.status == "all" else args.status
        episodes = query_illness_episodes(
            settings.db_path,
            from_date=args.from_date,
            to_date=args.to_date,
            source=args.source,
            status=query_status,
        )
        if args.format == "json":
            print(json.dumps({"episodes": episodes, "count": len(episodes)}, indent=2, sort_keys=True))
        else:
            _print_illness_text(episodes)
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
            print(f"Avg lead-in sleep: {analysis.avg_lead_in_sleep_hours}h")
            if analysis.avg_bedtime:
                print(f"Avg bedtime: {analysis.avg_bedtime} | Avg wake: {analysis.avg_wake_time}")
            if analysis.avg_efficiency:
                print(f"Avg efficiency: {analysis.avg_efficiency}%")
            for day in analysis.daily:
                if day.sample_count > 0:
                    print(
                        f"  {day.date}: total={day.total_sleep_hours}h main={day.main_sleep_hours}h nap={day.nap_hours}h additional={day.additional_sleep_hours}h"
                    )
                else:
                    print(f"  {day.date}: no data")
            print("Functional days:")
            for day in analysis.functional_daily:
                if day.lead_in_sleep is not None:
                    print(
                        f"  {day.date}: lead-in={day.lead_in_sleep.sleep_hours}h "
                        f"({day.lead_in_sleep.start_local} -> {day.lead_in_sleep.end_local}) "
                        f"source_session={day.lead_in_sleep.session_type}"
                    )
                else:
                    print(f"  {day.date}: no lead-in sleep")
        return 0

    if args.command == "sleep" and args.sleep_command == "daily":
        samples = query_sleep_samples(db_path=settings.db_path)
        days_map = assign_samples_to_days(samples, settings.timezone)
        _check_data_freshness(days_map, settings.timezone)

        if args.last_night:
            target_date = (datetime.now(ZoneInfo(settings.timezone)) - timedelta(days=1)).date().isoformat()
        elif args.date:
            target_date = args.date
        else:
            target_date = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()

        day_samples = days_map.get(target_date, [])
        metrics = compute_day_metrics(day_samples, target_date, settings.timezone)
        if args.format == "json":
            print(json.dumps(metrics.to_dict(), indent=2))
        else:
            print(f"Date: {metrics.date} | Samples: {metrics.sample_count}")
            print(
                f"Sleep: total={metrics.total_sleep_hours}h | main={metrics.main_sleep_hours}h | "
                f"nap={metrics.nap_hours}h | additional={metrics.additional_sleep_hours}h | "
                f"in_bed={metrics.total_in_bed_hours}h"
            )
            if metrics.bedtime:
                print(f"Bedtime: {metrics.bedtime} | Wake: {metrics.wake_time}")
            print(
                f"Deep: {metrics.deep_sleep_hours}h | Core: {metrics.core_sleep_hours}h | REM: {metrics.rem_sleep_hours}h | Awake: {metrics.awake_hours}h"
            )
            if metrics.sleep_efficiency:
                print(f"Efficiency: {metrics.sleep_efficiency}%")
            if metrics.lead_in_sleep is not None:
                print(
                    f"Lead-in sleep for {metrics.date}: {metrics.lead_in_sleep.sleep_hours}h "
                    f"({metrics.lead_in_sleep.start_local} -> {metrics.lead_in_sleep.end_local})"
                )
            _print_sleep_sessions(metrics)
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

    if args.command == "workouts":
        samples = _workout_samples_as_metric_rows(query_workout_samples(db_path=settings.db_path))
        if args.workouts_command == "analyze":
            summary = compute_metric_analysis(
                samples=samples,
                data_type="workouts",
                metric_type="duration_seconds",
                days=args.days,
                tz_name=settings.timezone,
            )
            if args.format == "json":
                print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
            else:
                _print_metric_analysis_text(summary)
            return 0

        if args.workouts_command == "daily":
            summary = compute_metric_daily_summary(
                samples=samples,
                data_type="workouts",
                date_str=args.date,
                tz_name=settings.timezone,
            )
            if args.format == "json":
                print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
            else:
                _print_metric_daily_text(summary)
            return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
