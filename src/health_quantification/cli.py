from __future__ import annotations

import argparse
import json
from pathlib import Path

from health_quantification.analysis.daily_summary import build_default_daily_summary
from health_quantification.artifacts.chart import render_daily_card_svg
from health_quantification.config import load_settings
from health_quantification.storage import initialize_database


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

    if args.command == "artifact" and args.artifact_command == "daily-card":
        summary = build_default_daily_summary(args.date, settings.timezone)
        output = render_daily_card_svg(summary, Path(args.output))
        print(json.dumps({"status": "written", "output": str(output)}, indent=2))
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
