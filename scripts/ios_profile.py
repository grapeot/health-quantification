"""Build/install, trigger and retrieve live HealthKit export profiles from a paired iPhone.

This command uploads the normal 30-day export to the app's existing backend.
All device artifacts stay under ignored tmp/ios_device_qa/profiles.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import statistics
import subprocess
import time
import uuid
from pathlib import Path

try:
    from scripts.ios_probe import BUNDLE_ID, PROJECT, ROOT, SCRATCH, run
except ModuleNotFoundError:
    from ios_probe import BUNDLE_ID, PROJECT, ROOT, SCRATCH, run


def validate_profile(payload: dict, run_id: str) -> dict:
    if (payload.get("schema_version") != 1 or payload.get("run_id") != run_id
            or payload.get("status") not in ("running", "success", "partial", "failed", "busy")):
        raise ValueError("profile does not match this run or schema")
    if type(payload.get("total_ms")) not in (int, float) or not math.isfinite(payload["total_ms"]) or payload["total_ms"] < 0:
        raise ValueError("invalid total duration")
    events = payload.get("events")
    if not isinstance(events, list) or (not events and payload["status"] in ("running", "success")):
        raise ValueError("missing profile events")
    for event in events:
        if (not isinstance(event, dict) or not isinstance(event.get("phase"), str)
                or type(event.get("duration_ms")) not in (int, float)
                or not math.isfinite(event["duration_ms"]) or event["duration_ms"] < 0):
            raise ValueError("invalid profile event")
        for key in ("count", "bytes"):
            if key in event and (type(event[key]) is not int or event[key] < 0):
                raise ValueError("invalid profile count or size")
    if payload["status"] == "success":
        phases = {event["phase"] for event in events}
        if any(f"{category}.fetch" not in phases for category in
               ("sleep", "vitals", "body", "lifestyle", "activity", "workouts", "ecg")):
            raise ValueError("successful profile is missing a category")
        if payload.get("failed_categories") != []:
            raise ValueError("successful profile contains failures")
        for category in ("sleep", "vitals", "body", "lifestyle", "activity", "workouts", "ecg"):
            sent = sum(event.get("count", 0) for event in events if event["phase"] == f"{category}.encode")
            accepted = sum(event.get("count", 0) for event in events if event["phase"] == f"{category}.ingested")
            if sent != accepted:
                raise ValueError(f"{category} accepted count does not match sent count")
    return payload


def summarize(profiles: list[dict]) -> dict:
    def quantiles(values: list[float]) -> dict:
        ordered = sorted(values)
        return {"p50_ms": statistics.median(ordered), "p90_ms": ordered[math.ceil(len(ordered) * .9) - 1]}
    phases = sorted({event["phase"] for profile in profiles for event in profile["events"]})
    return {
        "runs": len(profiles), "total": quantiles([profile["total_ms"] for profile in profiles]),
        "phases": {phase: quantiles([
            sum(event["duration_ms"] for event in profile["events"] if event["phase"] == phase)
            for profile in profiles
        ]) for phase in phases},
        "sample_counts": [{event["phase"]: event["count"] for event in profile["events"]
                           if event.get("count") is not None} for profile in profiles],
    }


def compare_summaries(baseline: dict, candidate: dict) -> dict:
    if any(baseline.get(key) != candidate.get(key) for key in ("configuration", "cold", "warmup")):
        raise ValueError("comparison requires matching build configuration, warm/cold mode and warmup count")
    before, after = baseline["total"]["p50_ms"], candidate["total"]["p50_ms"]
    if before <= 0 or after <= 0:
        raise ValueError("comparison requires positive total durations")
    baseline_counts = baseline["sample_counts"]
    candidate_counts = candidate["sample_counts"]
    keys = {key for counts in baseline_counts + candidate_counts for key in counts if key.endswith(".encode")}
    drift = max((
        abs(statistics.median([counts.get(key, 0) for counts in candidate_counts])
            - statistics.median([counts.get(key, 0) for counts in baseline_counts]))
        / max(1, statistics.median([counts.get(key, 0) for counts in baseline_counts]))
        for key in keys
    ), default=0)
    return {"baseline_p50_ms": before, "candidate_p50_ms": after,
            "speedup": before / after, "time_reduction_percent": (1 - after / before) * 100,
            "maximum_relative_sample_count_drift": drift}


def collect(device: str, directory: Path, timeout: int, cold: bool, configuration: str) -> dict:
    run_id = directory.name
    url = f"healthquantification://profile-export?run_id={run_id}"
    if cold:
        command = ["xcrun", "devicectl", "device", "process", "launch", "--device", device,
                   "--terminate-existing", "--payload-url", url, BUNDLE_ID]
    else:
        command = ["xcrun", "devicectl", "device", "process", "openURL", "--device", device, url]
    run(command, directory / "trigger.log", timeout=30)
    deadline = time.monotonic() + timeout
    previous = 0
    while time.monotonic() < deadline:
        result = subprocess.run([
            "xcrun", "devicectl", "device", "copy", "from", "--device", device,
            "--domain-type", "appDataContainer", "--domain-identifier", BUNDLE_ID,
            "--source", f"Library/Caches/ExportProfiles/{run_id}.json",
            "--destination", str(directory / "result.json"),
        ], cwd=ROOT, capture_output=True, text=True, timeout=min(30, max(1, deadline - time.monotonic())))
        if result.returncode == 0:
            payload = validate_profile(json.loads((directory / "result.json").read_text()), run_id)
            if payload.get("build_configuration") != configuration:
                raise ValueError("installed build configuration differs from requested benchmark configuration")
            if len(payload["events"]) > previous:
                previous = len(payload["events"])
                event = payload["events"][-1]
                print(f"{run_id}: {payload['status']} {event['phase']} {event['duration_ms']:.1f} ms", flush=True)
            if payload["status"] != "running":
                if payload["status"] != "success":
                    raise RuntimeError(f"export ended {payload['status']}; see {directory / 'result.json'}")
                return payload
        else:
            (directory / "copy_last_error.log").write_text(result.stdout + result.stderr)
        time.sleep(1)
    raise RuntimeError(f"profile timed out; inspect {directory} and device permission/lock state")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--configuration", choices=("Debug", "Release"), default="Release")
    parser.add_argument("--skip-build-install", action="store_true")
    parser.add_argument("--cold", action="store_true", help="restart the app for each run")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--compare-summary", type=Path, help="compare with an earlier run's summary.json")
    args = parser.parse_args()
    if args.runs < 1 or args.warmup < 0 or args.timeout < 1:
        parser.error("runs/timeout must be positive; warmup must be nonnegative")
    session = SCRATCH / "profiles" / str(uuid.uuid4()).upper()
    session.mkdir(parents=True)
    try:
        with (SCRATCH / "probe.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not args.skip_build_install:
                derived = SCRATCH / "ProfileDerivedData"
                run(["xcodebuild", "-quiet", "-project", str(PROJECT), "-scheme", "HealthQuantificationIOS",
                     "-configuration", args.configuration, "-destination", f"platform=iOS,name={args.device}",
                     "-derivedDataPath", str(derived), "build"], session / "build.log", timeout=600)
                run(["xcrun", "devicectl", "device", "install", "app", "--device", args.device,
                     str(derived / f"Build/Products/{args.configuration}-iphoneos/HealthQuantificationIOS.app")],
                    session / "install.log", timeout=120)
            run(["xcrun", "devicectl", "device", "info", "apps", "--device", args.device,
                 "--bundle-id", BUNDLE_ID, "--require-container-access"], session / "container.log", timeout=30)
            profiles = []
            for index in range(args.warmup + args.runs):
                directory = session / str(uuid.uuid4()).upper()
                directory.mkdir()
                payload = collect(args.device, directory, args.timeout, args.cold, args.configuration)
                print(f"{'warmup' if index < args.warmup else 'measured'} total={payload['total_ms']:.1f} ms", flush=True)
                if index >= args.warmup:
                    profiles.append(payload)
            summary = {"configuration": args.configuration, "cold": args.cold, "warmup": args.warmup,
                       "artifact_dir": str(session), **summarize(profiles)}
            if args.compare_summary:
                summary["comparison"] = compare_summaries(json.loads(args.compare_summary.read_text()), summary)
            (session / "summary.json").write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"profile failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
