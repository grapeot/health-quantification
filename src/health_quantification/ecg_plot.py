from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STRIP_COUNT = 6
STRIP_SECONDS = 5.0
PLOT_WINDOW_SECONDS = STRIP_COUNT * STRIP_SECONDS
MM_PER_S = 25.0
MM_PER_MV_STANDARD = 10.0
MAX_STRIP_H_MM = 150.0
MIN_WINDOW_MV = 1.0
TIME_MAJOR_S = 0.2
TIME_MINOR_S = 0.04
INTERVAL_TOLERANCE_S = 1e-6
DPI = 160
CHECK_NAMES = (
    "point_count",
    "time_strictly_monotonic",
    "sampling_frequency",
    "finite_non_null",
    "plot_window",
    "voltage_unit",
)
MATPLOTLIB_HELP = (
    "matplotlib is not installed. ECG plotting uses an optional dependency and does not "
    "filter or print voltage samples. From the project directory run: "
    "uv pip install --python .venv/bin/python -e '.[plot]'"
)
EXISTS_DETAIL = "output or integrity output already exists; retry with a new output filename"


class EcgPlotError(Exception):
    pass


@dataclass(frozen=True)
class DisplayScale:
    y_lo: float
    y_hi: float
    mm_per_mv: float
    minor_mv: float
    major_mv: float
    scale_reduced: bool
    standard_grid: bool
    scale_note: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _git_ignored(path: Path, root: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", str(path)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise EcgPlotError("could not verify that the output path is private")


def _git_tracked(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative.as_posix()],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise EcgPlotError("could not verify that the output path is private")


def resolve_private_path(path: Path, *, write: bool) -> Path:
    resolved = path.expanduser().resolve()
    root = repo_root()
    if _inside(resolved, root):
        data_root = (root / "data").resolve()
        if not _inside(resolved, data_root):
            raise EcgPlotError("paths inside the repository must be under data/")
        if write and (_git_tracked(resolved, root) or not _git_ignored(resolved, root)):
            raise EcgPlotError("refusing to write a tracked or non-private path")
    if write and resolved.exists() and resolved.is_dir():
        raise EcgPlotError("output path must be a file")
    return resolved


def load_export(path: Path) -> object:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise EcgPlotError("input could not be read") from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise EcgPlotError("input is not valid JSON") from error


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    return None


def snap_step(raw: float) -> float:
    if raw <= 0 or not math.isfinite(raw):
        return 0.1
    exponent = math.floor(math.log10(raw))
    base = 10.0**exponent
    for multiplier in (1, 2, 5, 10):
        step = multiplier * base
        if step + 1e-12 >= raw:
            return float(step)
    return float(10 * base)


def display_scale(values_mv: list[float]) -> DisplayScale:
    if not values_mv:
        raise EcgPlotError("no voltage values to scale")
    vmin = min(values_mv)
    vmax = max(values_mv)
    span = vmax - vmin
    pad = max(0.05, 0.02 * span)
    prelim_lo = vmin - pad
    prelim_hi = vmax + pad
    if prelim_hi - prelim_lo < MIN_WINDOW_MV:
        mid = 0.5 * (vmin + vmax)
        half = 0.5 * MIN_WINDOW_MV
        prelim_lo = min(prelim_lo, mid - half)
        prelim_hi = max(prelim_hi, mid + half)
    plot_span = prelim_hi - prelim_lo
    mm_per_mv = MM_PER_MV_STANDARD
    scale_reduced = plot_span * mm_per_mv > MAX_STRIP_H_MM
    if scale_reduced:
        mm_per_mv = MAX_STRIP_H_MM / plot_span
    standard_grid = (not scale_reduced) and (mm_per_mv * 0.1 >= 0.6) and (plot_span / 0.1 <= 400)
    if standard_grid:
        minor_mv = 0.1
        major_mv = 0.5
    else:
        major_mv = snap_step(max(plot_span / 8.0, 0.8 / mm_per_mv))
        minor_mv = major_mv / 5.0
        if mm_per_mv * minor_mv < 0.45:
            minor_mv = major_mv
        if plot_span / minor_mv > 400:
            minor_mv = snap_step(plot_span / 200.0)
            major_mv = snap_step(max(major_mv, minor_mv * 5.0))
    y_lo = math.floor(prelim_lo / major_mv + 1e-9) * major_mv
    y_hi = math.ceil(prelim_hi / major_mv - 1e-9) * major_mv
    if y_lo > vmin:
        y_lo -= major_mv
    if y_hi < vmax:
        y_hi += major_mv
    y_span = y_hi - y_lo
    if y_span * mm_per_mv > MAX_STRIP_H_MM + 1e-6:
        mm_per_mv = MAX_STRIP_H_MM / y_span
        scale_reduced = True
        standard_grid = False
    if y_lo > vmin or y_hi < vmax:
        raise EcgPlotError("display limits would clip voltage; refusing to plot")
    screen_note = "仅屏幕查看，不保证打印比例。"
    if scale_reduced or not standard_grid:
        scale_note = (
            f"时间轴 25 mm/s。电压显示比例 {mm_per_mv:.4g} mm/mV"
            f"（标准 10 mm/mV 下单条约 {y_span * MM_PER_MV_STANDARD:.0f} mm，已超出屏幕图高上限）。"
            "raw 全范围保留，未裁剪、未滤波、未平滑、未做幅度归一化。"
            f"电压格线为 {minor_mv:g} / {major_mv:g} mV，不是 0.1 / 0.5 mV。"
            + screen_note
        )
    else:
        scale_note = (
            "时间轴 25 mm/s，电压轴 10 mm/mV。主格 0.2 s / 0.5 mV，小格 0.04 s / 0.1 mV。"
            "raw 全范围保留，未裁剪、未滤波、未平滑、未做幅度归一化。"
            + screen_note
        )
    return DisplayScale(
        y_lo=y_lo,
        y_hi=y_hi,
        mm_per_mv=mm_per_mv,
        minor_mv=minor_mv,
        major_mv=major_mv,
        scale_reduced=scale_reduced,
        standard_grid=standard_grid and not scale_reduced,
        scale_note=scale_note,
    )


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _empty_checks() -> dict[str, object]:
    return {
        "point_count": {"pass": False},
        "time_strictly_monotonic": {"pass": False},
        "sampling_frequency": {"pass": False},
        "finite_non_null": {"pass": False},
        "plot_window": {
            "pass": False,
            "window_seconds": PLOT_WINDOW_SECONDS,
            "strips": STRIP_COUNT,
            "strip_seconds": STRIP_SECONDS,
        },
        "voltage_unit": {"pass": False},
    }


def _report(checks: dict[str, object], *, detail: str | None = None) -> dict[str, object]:
    overall = True
    for name in CHECK_NAMES:
        item = checks[name]
        if not isinstance(item, dict) or not item.get("pass"):
            overall = False
            break
    report: dict[str, object] = {
        "not_a_diagnosis": True,
        "physician_diagnosis": False,
        "operations_not_performed": [
            "filter",
            "smooth",
            "amplitude_normalize",
            "crop",
            "clip",
        ],
        "checks": checks,
        "plot": {"written": False, "clipped": False, "filtered": False, "samples_excluded": 0},
        "overall_pass": overall,
    }
    if detail is not None:
        report["detail"] = detail
    return report


def assess_export(payload: object) -> tuple[dict[str, object], list[float], list[float]]:
    checks = _empty_checks()
    if not isinstance(payload, dict):
        return _report(checks, detail="export JSON must be an object"), [], []
    voltage = payload.get("voltage")
    if not isinstance(voltage, list):
        return _report(checks, detail="voltage must be an array"), [], []

    times: list[float] = []
    volts: list[float] = []
    bad_item = 0
    null_time = 0
    null_voltage = 0
    nonfinite_time = 0
    nonfinite_voltage = 0
    for item in voltage:
        if not isinstance(item, dict):
            bad_item += 1
            times.append(math.nan)
            volts.append(math.nan)
            continue
        raw_time = item.get("time_offset_seconds")
        raw_voltage = item.get("voltage_volts")
        if raw_time is None:
            null_time += 1
        if raw_voltage is None:
            null_voltage += 1
        parsed_time = _number(raw_time)
        parsed_voltage = _number(raw_voltage)
        if raw_time is not None and parsed_time is None:
            nonfinite_time += 1
        if raw_voltage is not None and parsed_voltage is None:
            nonfinite_voltage += 1
        times.append(parsed_time if parsed_time is not None else math.nan)
        volts.append(parsed_voltage if parsed_voltage is not None else math.nan)

    count = len(voltage)
    declared_count = payload.get("voltage_count")
    returned = payload.get("returned_points")
    expected = payload.get("number_of_voltage_measurements")
    truncated = payload.get("truncated")
    status = payload.get("voltage_status")
    count_pass = (
        count > 0
        and declared_count == count
        and returned == count
        and expected == count
        and truncated is False
        and status == "complete"
    )
    checks["point_count"] = {
        "actual": count,
        "voltage_count": declared_count,
        "returned_points": returned,
        "number_of_voltage_measurements": expected,
        "truncated": truncated,
        "voltage_status": status,
        "pass": count_pass,
    }

    finite_pass = (
        bad_item == 0
        and null_time == 0
        and null_voltage == 0
        and nonfinite_time == 0
        and nonfinite_voltage == 0
    )
    checks["finite_non_null"] = {
        "bad_item": bad_item,
        "null_time": null_time,
        "null_voltage": null_voltage,
        "nonfinite_time": nonfinite_time,
        "nonfinite_voltage": nonfinite_voltage,
        "pass": finite_pass,
    }

    declared_hz = _number(payload.get("sampling_frequency_hz"))
    monotonic = False
    non_increasing = None
    max_dt_error = None
    interval_pass = False
    if count >= 2 and finite_pass and declared_hz is not None and declared_hz > 0:
        deltas = [times[index + 1] - times[index] for index in range(count - 1)]
        non_increasing = sum(1 for delta in deltas if delta <= 0)
        monotonic = non_increasing == 0
        expected_dt = 1.0 / declared_hz
        errors = [abs(delta - expected_dt) for delta in deltas]
        max_dt_error = max(errors)
        interval_pass = monotonic and max_dt_error <= INTERVAL_TOLERANCE_S
    checks["time_strictly_monotonic"] = {
        "pass": monotonic,
        "non_increasing_steps": non_increasing,
    }
    checks["sampling_frequency"] = {
        "declared_hz": payload.get("sampling_frequency_hz"),
        "expected_interval_seconds": None if declared_hz is None or declared_hz <= 0 else 1.0 / declared_hz,
        "max_abs_error_seconds": max_dt_error,
        "pass": interval_pass and declared_hz is not None and declared_hz > 0,
    }

    outside = 0
    if finite_pass and count:
        outside = sum(1 for sample_time in times if sample_time < -1e-9 or sample_time > PLOT_WINDOW_SECONDS + 1e-9)
    finite_volts = [value for value in volts if math.isfinite(value)]
    checks["plot_window"] = {
        "pass": finite_pass and count > 0 and outside == 0,
        "outside_count": outside,
        "window_seconds": PLOT_WINDOW_SECONDS,
        "strips": STRIP_COUNT,
        "strip_seconds": STRIP_SECONDS,
        "first_seconds": times[0] if finite_pass and times else None,
        "last_seconds": times[-1] if finite_pass and times else None,
    }
    checks["voltage_unit"] = {
        "unit": payload.get("voltage_unit"),
        "pass": payload.get("voltage_unit") == "V",
    }
    report = _report(checks)
    if isinstance(payload, dict):
        report["record"] = {
            "source_id": payload.get("source_id"),
            "start_at": payload.get("start_at"),
            "lead": payload.get("lead"),
            "sampling_frequency_hz": payload.get("sampling_frequency_hz"),
            "voltage_status": payload.get("voltage_status"),
            "truncated": payload.get("truncated"),
        }
    if finite_pass and finite_volts and len(finite_volts) == count:
        median_volts = _median(finite_volts)
        report["voltage_millivolts"] = {
            "min": min(finite_volts) * 1000.0,
            "max": max(finite_volts) * 1000.0,
            "median": None if median_volts is None else median_volts * 1000.0,
        }
    if not finite_pass:
        return report, [], []
    return report, times, volts


def _local_label(payload: dict[str, object]) -> str | None:
    start = payload.get("start_at")
    if not isinstance(start, str):
        return None
    try:
        parsed = datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    timezone = os.environ.get("HEALTH_QUANT_TIMEZONE", "America/Los_Angeles")
    try:
        local = parsed.astimezone(ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None
    return local.strftime("%Y-%m-%d %H:%M:%S %Z")


def _cjk_font() -> str | None:
    candidates = (
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _import_matplotlib() -> tuple[object, object, object, object]:
    try:
        matplotlib = importlib.import_module("matplotlib")
        if "matplotlib.pyplot" not in sys.modules:
            matplotlib.use("Agg")
        font_manager = importlib.import_module("matplotlib.font_manager")
        plt = importlib.import_module("matplotlib.pyplot")
        ticker = importlib.import_module("matplotlib.ticker")
    except ImportError as error:
        raise EcgPlotError(MATPLOTLIB_HELP) from error
    return plt, font_manager, ticker.FuncFormatter, ticker.MultipleLocator


def render_png(
    payload: dict[str, object],
    times: list[float],
    volts: list[float],
    scale: DisplayScale,
    output: Path,
) -> dict[str, object]:
    plt, font_manager, func_formatter, multiple_locator = _import_matplotlib()
    values_mv = [value * 1000.0 for value in volts]
    if scale.y_lo > min(values_mv) or scale.y_hi < max(values_mv):
        raise EcgPlotError("display limits would clip voltage; refusing to plot")
    drawn = [False] * len(times)
    selections: list[tuple[list[float], list[float]]] = []
    for strip in range(STRIP_COUNT):
        start = strip * STRIP_SECONDS
        end = start + STRIP_SECONDS
        selected_t: list[float] = []
        selected_v: list[float] = []
        for index, sample_time in enumerate(times):
            if start - 1e-9 <= sample_time <= end + 1e-9:
                drawn[index] = True
                selected_t.append(sample_time)
                selected_v.append(values_mv[index])
        selections.append((selected_t, selected_v))
    if not all(drawn):
        raise EcgPlotError("refusing to omit samples outside the 6x5s window")

    if not output.name.startswith(_STAGING_PREFIX):
        raise EcgPlotError("refusing to write plot directly to the destination")
    font_path = _cjk_font()
    title_font = font_manager.FontProperties(fname=font_path, size=8) if font_path else None
    small_font = font_manager.FontProperties(fname=font_path, size=7) if font_path else None
    left_mm = 28.0 if max(abs(scale.y_lo), abs(scale.y_hi)) < 100 else 36.0
    right_mm = 12.0
    top_mm = 32.0
    bottom_mm = 16.0
    gap_mm = 7.0
    strip_h_mm = (scale.y_hi - scale.y_lo) * scale.mm_per_mv
    strip_w_mm = STRIP_SECONDS * MM_PER_S
    fig_w_mm = left_mm + strip_w_mm + right_mm
    fig_h_mm = top_mm + STRIP_COUNT * strip_h_mm + (STRIP_COUNT - 1) * gap_mm + bottom_mm
    output.parent.mkdir(parents=True, exist_ok=True)
    fig = None

    def xfmt(value: float, _pos: object) -> str:
        nearest = round(value)
        if abs(value - nearest) < 1e-6:
            return str(int(nearest))
        return ""

    def yfmt(value: float, _pos: object) -> str:
        if abs(value) >= 100:
            return f"{value:.0f}"
        if abs(value) >= 10 or abs(scale.major_mv) >= 0.5:
            return f"{value:.1f}"
        return f"{value:.2f}"

    with plt.rc_context(
        {
            "path.simplify": False,
            "path.simplify_threshold": 0.0,
            "agg.path.chunksize": 0,
            "axes.unicode_minus": False,
        }
    ):
        try:
            fig, axes = plt.subplots(
                STRIP_COUNT,
                1,
                figsize=(fig_w_mm / 25.4, fig_h_mm / 25.4),
                dpi=DPI,
                sharey=True,
            )
            fig.patch.set_facecolor("white")
            fig.subplots_adjust(
                left=left_mm / fig_w_mm,
                right=1.0 - right_mm / fig_w_mm,
                bottom=bottom_mm / fig_h_mm,
                top=1.0 - top_mm / fig_h_mm,
                hspace=gap_mm / strip_h_mm,
            )
            for index, axis in enumerate(axes):
                start = index * STRIP_SECONDS
                end = start + STRIP_SECONDS
                selected_t, selected_v = selections[index]
                axis.set_facecolor("#fffdfd")
                axis.set_xlim(start, end)
                axis.set_ylim(scale.y_lo, scale.y_hi)
                axis.autoscale(False)
                axis.xaxis.set_major_locator(multiple_locator(TIME_MAJOR_S))
                axis.xaxis.set_minor_locator(multiple_locator(TIME_MINOR_S))
                axis.yaxis.set_major_locator(multiple_locator(scale.major_mv))
                axis.yaxis.set_minor_locator(multiple_locator(scale.minor_mv))
                axis.grid(which="minor", color="#f3c7c7", linewidth=0.4, zorder=0)
                axis.grid(which="major", color="#e07a7a", linewidth=0.7, zorder=0)
                axis.set_axisbelow(True)
                if scale.y_lo < 0.0 < scale.y_hi:
                    axis.axhline(0.0, color="#555555", linewidth=0.4, zorder=1)
                axis.plot(
                    selected_t,
                    selected_v,
                    color="#111111",
                    linewidth=0.8,
                    solid_joinstyle="round",
                    solid_capstyle="butt",
                    zorder=3,
                )
                axis.xaxis.set_major_formatter(func_formatter(xfmt))
                axis.yaxis.set_major_formatter(func_formatter(yfmt))
                axis.tick_params(which="major", length=2.5, labelsize=7, labelleft=True, colors="#333333")
                axis.tick_params(which="minor", length=0, labelleft=False)
                axis.set_ylabel("mV", fontsize=7)
                axis.text(
                    0.0,
                    1.02,
                    f"{start:.0f}–{end:.0f} s",
                    transform=axis.transAxes,
                    ha="left",
                    va="bottom",
                    fontsize=7,
                    color="#333333",
                    clip_on=False,
                    zorder=4,
                )
                if index == STRIP_COUNT - 1:
                    axis.set_xlabel("seconds from record start", fontsize=7)
            classification = payload.get("algorithm_classification")
            heart_rate = payload.get("average_heart_rate_bpm")
            local_label = _local_label(payload)
            gain = f"25 mm/s, {scale.mm_per_mv:.4g} mm/mV"
            if scale.scale_reduced or not scale.standard_grid:
                gain += "（电压显示比例已调整，raw 未裁）"
            gain += f". 主格 0.2 s / {scale.major_mv:g} mV, 小格 0.04 s / {scale.minor_mv:g} mV."
            title_lines = []
            if local_label:
                title_lines.append(local_label)
            title_lines.append(f"Apple algorithm: {classification}, mean {heart_rate} bpm. 不是医师诊断。")
            title_lines.append(gain)
            title_lines.append("未滤波、未平滑、未归一化、未裁剪。仅屏幕查看，不保证打印比例。")
            fig.text(
                0.5,
                1.0 - (3.2 / fig_h_mm),
                "\n".join(title_lines),
                ha="center",
                va="top",
                fontproperties=title_font,
                fontsize=8,
                color="#222222",
            )
            fig.savefig(output, dpi=DPI)
        finally:
            if fig is not None:
                plt.close(fig)
    return {
        "written": True,
        "filtered": False,
        "smoothed": False,
        "amplitude_normalized": False,
        "clipped": False,
        "samples_excluded": 0,
        "samples_drawn": len(times),
        "straight_segments_between_samples": True,
        "mm_per_s_intended": MM_PER_S,
        "mm_per_mv_intended": scale.mm_per_mv,
        "standard_10mm_per_mv": (not scale.scale_reduced) and abs(scale.mm_per_mv - MM_PER_MV_STANDARD) < 1e-9,
        "standard_voltage_grid_0.1_0.5": scale.standard_grid and not scale.scale_reduced,
        "voltage_grid_minor_mv": scale.minor_mv,
        "voltage_grid_major_mv": scale.major_mv,
        "time_grid_minor_s": TIME_MINOR_S,
        "time_grid_major_s": TIME_MAJOR_S,
        "y_limits_mv": [scale.y_lo, scale.y_hi],
        "screen_only_print_scale_not_guaranteed": True,
        "scale_note": scale.scale_note,
        "font": font_path,
    }


def _source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


_STAGING_PREFIX = ".ecgplot."


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _same_file(left: Path, right: Path) -> bool:
    if left == right:
        return True
    try:
        return left.exists() and right.exists() and left.samefile(right)
    except OSError:
        return False


def _protect_source(source: Path, *paths: Path) -> None:
    for path in paths:
        if _same_file(path, source):
            raise EcgPlotError("input, output, and integrity output must be different files")


def _occupied(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _discard(path: Path) -> None:
    if not path.name.startswith(_STAGING_PREFIX):
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _link_exclusive(staged: Path, destination: Path) -> None:
    if _occupied(destination):
        raise EcgPlotError(EXISTS_DETAIL)
    try:
        os.link(staged, destination)
    except FileExistsError as error:
        raise EcgPlotError(EXISTS_DETAIL) from error


def _staging_file(directory: Path, suffix: str = ".tmp") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=_STAGING_PREFIX, suffix=suffix, dir=directory)
    os.close(handle)
    return Path(name)


def _unwritten_plot() -> dict[str, object]:
    return {"written": False, "clipped": False, "filtered": False, "samples_excluded": 0}


def _attach_source_identity(report: dict[str, object], source: Path) -> None:
    report["source_sha256"] = _source_sha256(source)
    report["source_bytes"] = source.stat().st_size


def _write_json_atomic(path: Path, payload: dict[str, object], source: Path) -> None:
    _protect_source(source, path)
    if _occupied(path):
        raise EcgPlotError(EXISTS_DETAIL)
    staged = _staging_file(path.parent)
    try:
        _protect_source(source, staged)
        _write_json(staged, payload)
        _link_exclusive(staged, path)
    finally:
        _discard(staged)


def _fail_run(
    destination: Path,
    integrity: Path,
    source: Path,
    report: dict[str, object],
    *,
    detail: object,
    failed: list[str] | None = None,
) -> int:
    wrote = False
    if (
        not _occupied(integrity)
        and not _same_file(integrity, source)
        and not _same_file(integrity, destination)
    ):
        try:
            _write_json_atomic(integrity, report, source)
            wrote = True
        except (EcgPlotError, OSError):
            wrote = False
    body: dict[str, object] = {
        "status": "rejected",
        "detail": detail,
        "overall_pass": False,
    }
    if wrote:
        body["integrity_output"] = str(integrity)
    if failed is not None:
        body["failed_checks"] = failed
    _status(body)
    return 2


def _failed_checks(report: dict[str, object]) -> list[str]:
    checks = report.get("checks")
    if not isinstance(checks, dict):
        return []
    return [
        name
        for name, item in checks.items()
        if isinstance(name, str) and isinstance(item, dict) and not item.get("pass")
    ]


def _publish_pair(
    staged_png: Path,
    destination: Path,
    staged_json: Path,
    integrity: Path,
    source: Path,
) -> None:
    _protect_source(source, staged_png, staged_json, destination, integrity)
    if _same_file(destination, integrity):
        raise EcgPlotError("input, output, and integrity output must be different files")
    _link_exclusive(staged_png, destination)
    _link_exclusive(staged_json, integrity)


def _status(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def plot_export(input_path: Path, output_path: Path, integrity_path: Path) -> int:
    source = resolve_private_path(input_path, write=False)
    destination = resolve_private_path(output_path, write=True)
    integrity = resolve_private_path(integrity_path, write=True)
    if _same_file(source, destination) or _same_file(source, integrity) or _same_file(destination, integrity):
        raise EcgPlotError("input, output, and integrity output must be different files")
    if any(_occupied(path) for path in (output_path, integrity_path, destination, integrity)):
        _status({"status": "rejected", "detail": EXISTS_DETAIL, "overall_pass": False})
        return 2
    if not source.is_file():
        raise EcgPlotError("input not found")
    try:
        payload = load_export(source)
    except EcgPlotError as error:
        report = _report(_empty_checks(), detail=str(error))
        try:
            _attach_source_identity(report, source)
        except OSError:
            pass
        return _fail_run(destination, integrity, source, report, detail=str(error))
    report, times, volts = assess_export(payload)
    _attach_source_identity(report, source)
    if not report["overall_pass"] or not isinstance(payload, dict):
        return _fail_run(
            destination,
            integrity,
            source,
            report,
            detail=report.get("detail") or "integrity checks failed",
            failed=_failed_checks(report),
        )
    staged_png: Path | None = None
    staged_json: Path | None = None
    try:
        staged_png = _staging_file(destination.parent, suffix=".png")
        staged_json = _staging_file(integrity.parent)
        for path in (staged_png, staged_json):
            if _same_file(path, source) or _same_file(path, destination) or _same_file(path, integrity):
                raise EcgPlotError("input, output, and integrity output must be different files")
        scale = display_scale([value * 1000.0 for value in volts])
        plot_meta = render_png(payload, times, volts, scale, staged_png)
        report["plot"] = plot_meta
        _write_json(staged_json, report)
        _publish_pair(staged_png, destination, staged_json, integrity, source)
        _status(
            {
                "status": "plotted",
                "overall_pass": True,
                "output": str(destination),
                "integrity_output": str(integrity),
                "scale_note": scale.scale_note,
                "screen_only_print_scale_not_guaranteed": True,
                "mm_per_s": MM_PER_S,
                "mm_per_mv": scale.mm_per_mv,
                "standard_10mm_per_mv": plot_meta["standard_10mm_per_mv"],
            }
        )
        return 0
    except EcgPlotError as error:
        report["plot"] = _unwritten_plot()
        return _fail_run(destination, integrity, source, report, detail=str(error))
    except OSError:
        report["plot"] = _unwritten_plot()
        return _fail_run(
            destination,
            integrity,
            source,
            report,
            detail="could not write plot outputs",
        )
    finally:
        if staged_png is not None:
            _discard(staged_png)
        if staged_json is not None:
            _discard(staged_json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plot one CLI ECG export JSON as six 5-second strips. "
            "Does not filter, smooth, normalize, or clip. Not a diagnosis."
        )
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--integrity-output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return plot_export(Path(args.input), Path(args.output), Path(args.integrity_output))
    except EcgPlotError as error:
        _status({"status": "rejected", "detail": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
