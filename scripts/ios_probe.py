"""Run a bounded, read-only HealthKit diagnostic on an Xcode-installed iPhone."""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ID = "com.yage.HealthQuantificationIOS"
PROJECT = ROOT / "HealthQuantification" / "HealthQuantification.xcodeproj"
SCRATCH = ROOT / "tmp" / "ios_device_qa"


def validate_artifact(payload: dict[str, object], run_id: str, days: int) -> dict[str, object]:
    if (
        payload.get("schema_version") != 1
        or payload.get("run_id") != run_id
        or payload.get("kind") != "physical-effort"
        or payload.get("days") != days
        or payload.get("status") not in ("completed", "no_data", "error")
    ):
        raise ValueError("diagnostic artifact does not match the requested run")
    if payload["status"] == "completed":
        count = payload.get("sample_count")
        values = [payload.get(key) for key in ("minimum", "median", "p90", "maximum")]
        if (
            type(count) is not int or count <= 0 or payload.get("unit") != "MET"
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in values)
            or values != sorted(values)
        ):
            raise ValueError("completed diagnostic is missing a valid MET summary")
    if payload["status"] == "no_data" and (
        payload.get("sample_count") != 0 or payload.get("unit") != "MET"
    ):
        raise ValueError("no-data diagnostic has an invalid sample count or unit")
    return payload


def run(command: list[str], log_path: Path, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        log_path.write_text(f"command timed out after {timeout} seconds\n", encoding="utf-8")
        raise RuntimeError(f"command timed out; see {log_path}") from exc
    log_path.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log_path}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="paired iPhone name or UDID")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--skip-build-install", action="store_true", help="use the already installed build")
    parser.add_argument("--timeout", type=int, default=90, help="seconds to wait for the artifact")
    args = parser.parse_args()
    if not 1 <= args.days <= 30 or args.timeout < 1:
        parser.error("days must be 1..30 and timeout must be positive")

    run_id = str(uuid.uuid4()).upper()
    session_dir = SCRATCH / "diagnostics" / run_id
    session_dir.mkdir(parents=True, exist_ok=False)
    SCRATCH.mkdir(parents=True, exist_ok=True)

    try:
        with (SCRATCH / "probe.lock").open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("another device build/probe is running") from exc

            if not args.skip_build_install:
                derived_data = SCRATCH / "DerivedData"
                run(
                    [
                        "xcodebuild", "-quiet", "-project", str(PROJECT),
                        "-scheme", "HealthQuantificationIOS", "-configuration", "Debug",
                        "-destination", f"platform=iOS,name={args.device}",
                        "-derivedDataPath", str(derived_data), "build",
                    ],
                    session_dir / "build.log", timeout=600,
                )
                run(
                    [
                        "xcrun", "devicectl", "device", "install", "app",
                        "--device", args.device,
                        str(derived_data / "Build/Products/Debug-iphoneos/HealthQuantificationIOS.app"),
                    ],
                    session_dir / "install.log", timeout=120,
                )

            run(
                [
                    "xcrun", "devicectl", "device", "info", "apps",
                    "--device", args.device, "--bundle-id", BUNDLE_ID,
                    "--require-container-access",
                ],
                session_dir / "container.log", timeout=30,
            )
            url = f"healthquantification://diagnostics?kind=physical-effort&run_id={run_id}&days={args.days}"
            run(
                [
                    "xcrun", "devicectl", "device", "process", "openURL",
                    "--device", args.device, "--json-output", str(session_dir / "open.json"), url,
                ],
                session_dir / "open.log", timeout=30,
            )

            artifact = session_dir / "result.json"
            source = f"Library/Caches/Diagnostics/{run_id}.json"
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                try:
                    result = subprocess.run(
                        [
                            "xcrun", "devicectl", "device", "copy", "from",
                            "--device", args.device, "--domain-type", "appDataContainer",
                            "--domain-identifier", BUNDLE_ID, "--source", source,
                            "--destination", str(artifact),
                        ],
                        cwd=ROOT, text=True, capture_output=True, timeout=30, check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("device copy timed out before the artifact was retrieved") from exc
                if result.returncode == 0:
                    break
                (session_dir / "copy_last_error.log").write_text(
                    result.stdout + "\n" + result.stderr, encoding="utf-8"
                )
                time.sleep(1)
            else:
                raise RuntimeError(
                    "artifact not available before timeout; check the phone for HealthKit consent "
                    f"and inspect {session_dir / 'copy_last_error.log'}"
                )

            payload = validate_artifact(json.loads(artifact.read_text(encoding="utf-8")), run_id, args.days)
            print(json.dumps({"artifact": str(artifact), **payload}, sort_keys=True))
            return 0 if payload["status"] in ("completed", "no_data") else 1
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"probe failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
