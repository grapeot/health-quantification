#!/usr/bin/env python3
"""Generate PNG charts from sleep analysis JSON for comprehensive reporting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

DATA: list[dict] = []

BG = "#0f172a"
FG = "#e2e8f0"
GRID = "#1e293b"
DIM = "#475569"
SUBTLE = "#94a3b8"
BLUE = "#3b82f6"
RED = "#f87171"
YELLOW = "#fbbf24"
GREEN = "#4ade80"
PURPLE = "#8b5cf6"
INDIGO = "#6366f1"


def load_data(json_path: Path | None = None) -> None:
    global DATA
    if json_path and json_path.exists():
        raw = json.loads(json_path.read_text())
    else:
        raw = json.loads(sys.stdin.read())
    DATA = raw.get("daily", raw) if isinstance(raw, dict) else raw


def _is_overnight(d: dict) -> bool:
    return d["sample_count"] > 0 and not d["has_nap"] and d["total_sleep_hours"] >= 3.0


def _overnight_days() -> list[dict]:
    return [d for d in DATA if _is_overnight(d)]


def _setup_fig(figsize=(12, 5), title=""):
    fig, ax = plt.subplots(figsize=figsize, facecolor=BG)
    ax.set_facecolor(BG)
    if title:
        ax.set_title(title, color=FG, fontsize=16, fontweight="bold", pad=16)
    ax.tick_params(colors=DIM, labelsize=10)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    return fig, ax


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=2)
    fig.savefig(path, dpi=150, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path


def render_sleep_duration_trend(output_path: Path) -> Path:
    days = _overnight_days()
    if not days:
        return output_path

    dates = [d["date"][5:] for d in days]
    hours = [d["total_sleep_hours"] for d in days]
    colors = [RED if h < 5 else YELLOW if h < 6 else BLUE if h < 8 else GREEN for h in hours]

    fig_h = max(5, len(days) * 0.22)
    fig, ax = _setup_fig((14, fig_h), "Sleep Duration (overnight only)")
    bars = ax.barh(dates, hours, color=colors, height=0.7, edgecolor="none", alpha=0.8)
    ax.axvline(x=7.5, color=YELLOW, linestyle="--", alpha=0.4, label="7.5h target")
    ax.axvline(x=6.0, color=RED, linestyle="--", alpha=0.3, label="6h minimum")
    ax.set_xlabel("Hours", color=DIM, fontsize=11)
    ax.invert_yaxis()
    ax.legend(loc="lower right", fontsize=9, facecolor=BG, edgecolor=GRID, labelcolor=DIM)

    for bar, h in zip(bars, hours):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{h:.1f}h", va="center", fontsize=9, color=SUBTLE)

    return _save(fig, output_path)


def render_stage_composition(output_path: Path) -> Path:
    days = _overnight_days()
    if not days:
        return output_path

    total_deep = sum(d["deep_sleep_hours"] for d in days)
    total_core = sum(d["core_sleep_hours"] for d in days)
    total_rem = sum(d["rem_sleep_hours"] for d in days)
    total_awake = sum(d["awake_hours"] for d in days)
    total_unspec = sum(d["unspecified_hours"] for d in days)
    total = total_deep + total_core + total_rem + total_awake + total_unspec

    if total == 0:
        return output_path

    fig, (ax_pie, ax_bar) = plt.subplots(1, 2, figsize=(14, 5.5), facecolor=BG)

    labels = ["Deep", "Core", "REM", "Awake", "Unspecified"]
    values = [total_deep, total_core, total_rem, total_awake, total_unspec]
    colors = [INDIGO, BLUE, PURPLE, RED, "#475569"]
    avgs = [v / len(days) for v in values]

    mask = [v > 0 for v in values]
    filtered_labels = [l for l, m in zip(labels, mask) if m]
    filtered_values = [v for v, m in zip(values, mask) if m]
    filtered_colors = [c for c, m in zip(colors, mask) if m]

    wedges, texts, autotexts = ax_pie.pie(
        filtered_values, labels=None, colors=filtered_colors,
        autopct="%1.1f%%", pctdistance=0.75, startangle=90,
        wedgeprops=dict(width=0.4, edgecolor=BG, linewidth=2),
    )
    for t in autotexts:
        t.set_color(FG)
        t.set_fontsize(10)
    ax_pie.set_title("Stage Distribution", color=FG, fontsize=14, fontweight="bold")
    ax_pie.set_facecolor(BG)

    ax_bar.set_facecolor(BG)
    y_pos = np.arange(len(labels))
    bars = ax_bar.barh(y_pos, avgs, color=colors, height=0.6, alpha=0.8)
    ax_bar.set_yticks(y_pos)
    ax_bar.set_yticklabels(labels, color=FG, fontsize=11)
    ax_bar.set_xlabel("Hours per night (avg)", color=DIM, fontsize=11)
    ax_bar.set_title("Average per Night", color=FG, fontsize=14, fontweight="bold")
    for spine in ax_bar.spines.values():
        spine.set_color(GRID)
    ax_bar.tick_params(colors=DIM)

    for bar, avg, v in zip(bars, avgs, values):
        pct = v / total * 100
        ax_bar.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                     f"{avg:.2f}h ({pct:.0f}%)", va="center", fontsize=10, color=SUBTLE)

    return _save(fig, output_path)


def render_efficiency_trend(output_path: Path) -> Path:
    days = _overnight_days()
    if not days:
        return output_path

    effs = [d["sleep_efficiency"] for d in days if d["sleep_efficiency"] is not None]
    if not effs:
        return output_path

    dates = [d["date"][5:] for d in days if d["sleep_efficiency"] is not None]
    avg_eff = np.mean(effs)

    fig, ax = _setup_fig((14, 5), "Sleep Efficiency Trend")
    colors = [RED if e < 75 else YELLOW if e < 85 else GREEN for e in effs]
    ax.plot(dates, effs, color=BLUE, linewidth=1.5, alpha=0.4)
    ax.scatter(dates, effs, c=colors, s=50, zorder=5, edgecolors="none")
    ax.axhline(y=avg_eff, color=YELLOW, linestyle="--", alpha=0.5, linewidth=1)
    ax.text(len(dates) - 1, avg_eff + 1.5, f"avg {avg_eff:.1f}%", fontsize=10, color=YELLOW, ha="right")
    ax.set_ylim(55, 105)
    ax.set_ylabel("Efficiency %", color=DIM, fontsize=11)

    for spine in ax.spines.values():
        spine.set_color(GRID)

    n = len(dates)
    step = max(1, n // 15)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([dates[i] for i in range(0, n, step)], rotation=45, ha="right")

    return _save(fig, output_path)


def render_bedtime_waketime(output_path: Path) -> Path:
    days = _overnight_days()
    if not days:
        return output_path

    def to_hours(t: str) -> float:
        h, m = t.split(":")
        return int(h) + int(m) / 60

    bt = [to_hours(d["bedtime"]) for d in days if d["bedtime"] is not None and d["wake_time"] is not None]
    wt = [to_hours(d["wake_time"]) for d in days if d["bedtime"] is not None and d["wake_time"] is not None]
    dates = [d["date"][5:] for d in days if d["bedtime"] is not None and d["wake_time"] is not None]

    if not dates:
        return output_path

    fig, ax = _setup_fig((14, 5), "Bedtime & Wake Time")

    ax.scatter(dates, bt, c=PURPLE, s=40, zorder=5, alpha=0.8, label="Bedtime")
    ax.scatter(dates, wt, c=BLUE, s=40, zorder=5, alpha=0.8, label="Wake time")

    for i in range(len(dates)):
        b, w = bt[i], wt[i]
        dur = (w - b) % 24
        if dur < 24:
            alpha = 0.15 if dur >= 5 else 0.35
            ax.plot([i, i], [b, w], color=GREEN if dur >= 7 else YELLOW if dur >= 5 else RED,
                    alpha=alpha, linewidth=6, solid_capstyle="round")

    avg_bt = np.mean(bt)
    avg_wt = np.mean(wt)
    ax.axhline(y=avg_bt, color=PURPLE, linestyle="--", alpha=0.3)
    ax.axhline(y=avg_wt, color=BLUE, linestyle="--", alpha=0.3)

    ax.set_ylabel("Hour of day", color=DIM, fontsize=11)
    ax.set_ylim(0, 24)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(2))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):02d}:00"))
    ax.legend(loc="upper right", fontsize=9, facecolor=BG, edgecolor=GRID, labelcolor=DIM)

    n = len(dates)
    step = max(1, n // 15)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([dates[i] for i in range(0, n, step)], rotation=45, ha="right")

    return _save(fig, output_path)


def render_weekly_comparison(output_path: Path) -> Path:
    days = _overnight_days()
    if not days:
        return output_path

    from datetime import datetime

    weeks: dict[str, list[dict]] = {}
    for d in days:
        dt = datetime.strptime(d["date"], "%Y-%m-%d")
        iso = dt.isocalendar()
        wk = f"W{iso[1]}"
        weeks.setdefault(wk, []).append(d)

    sorted_wks = sorted(weeks.keys())
    wk_labels = [f"{wk}\n({len(weeks[wk])}n)" for wk in sorted_wks]

    metrics = {
        "Sleep": [np.mean([d["total_sleep_hours"] for d in weeks[wk]]) for wk in sorted_wks],
        "Deep": [np.mean([d["deep_sleep_hours"] for d in weeks[wk]]) for wk in sorted_wks],
        "REM": [np.mean([d["rem_sleep_hours"] for d in weeks[wk]]) for wk in sorted_wks],
    }
    effs = [np.mean([d["sleep_efficiency"] for d in weeks[wk] if d["sleep_efficiency"] is not None]) for wk in sorted_wks]

    fig, (ax_bar, ax_eff) = plt.subplots(2, 1, figsize=(14, 7), facecolor=BG, height_ratios=[3, 1])

    x = np.arange(len(sorted_wks))
    width = 0.25
    colors_list = [BLUE, INDIGO, PURPLE]

    for i, (name, vals) in enumerate(metrics.items()):
        bars = ax_bar.bar(x + i * width, vals, width, label=name, color=colors_list[i], alpha=0.8)
        for bar, v in zip(bars, vals):
            ax_bar.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                        f"{v:.1f}", ha="center", fontsize=8, color=SUBTLE)

    ax_bar.set_facecolor(BG)
    ax_bar.set_title("Weekly Sleep Metrics", color=FG, fontsize=14, fontweight="bold")
    ax_bar.set_xticks(x + width)
    ax_bar.set_xticklabels(wk_labels, color=DIM, fontsize=9)
    ax_bar.set_ylabel("Hours", color=DIM, fontsize=11)
    ax_bar.legend(loc="upper right", fontsize=9, facecolor=BG, edgecolor=GRID, labelcolor=DIM)
    ax_bar.tick_params(colors=DIM)
    for spine in ax_bar.spines.values():
        spine.set_color(GRID)

    ax_eff.set_facecolor(BG)
    eff_colors = [RED if e < 75 else YELLOW if e < 85 else GREEN for e in effs]
    ax_eff.bar(x, effs, color=eff_colors, alpha=0.8, width=0.5)
    ax_eff.set_ylabel("Efficiency %", color=DIM, fontsize=11)
    ax_eff.set_xticks(x)
    ax_eff.set_xticklabels(wk_labels, color=DIM, fontsize=9)
    ax_eff.set_ylim(50, 105)
    ax_eff.tick_params(colors=DIM)
    for spine in ax_eff.spines.values():
        spine.set_color(GRID)

    for i, e in enumerate(effs):
        ax_eff.text(i, e + 0.5, f"{e:.0f}%", ha="center", fontsize=8, color=SUBTLE)

    return _save(fig, output_path)


def render_sleep_debt(output_path: Path) -> Path:
    days = _overnight_days()
    if not days:
        return output_path

    TARGET = 7.5
    daily_diff = [d["total_sleep_hours"] - TARGET for d in days]
    cumulative = np.cumsum(daily_diff)

    fig, (ax_daily, ax_cum) = plt.subplots(
        2, 1, figsize=(14, 7), facecolor=BG, height_ratios=[1, 1.5], sharex=True,
    )

    dates = [d["date"][5:] for d in days]
    daily_colors = [GREEN if d >= 0 else RED for d in daily_diff]
    ax_daily.bar(dates, daily_diff, color=daily_colors, alpha=0.8, width=0.7)
    ax_daily.axhline(y=0, color=DIM, linewidth=0.5)
    ax_daily.set_ylabel("vs target (h)", color=DIM, fontsize=10)
    ax_daily.set_title(f"Daily Sleep vs {TARGET}h Target", color=FG, fontsize=14, fontweight="bold")
    ax_daily.set_facecolor(BG)
    ax_daily.tick_params(colors=DIM)
    for spine in ax_daily.spines.values():
        spine.set_color(GRID)

    ax_cum.fill_between(range(len(cumulative)), cumulative, 0,
                         where=cumulative >= 0, color=GREEN, alpha=0.15)
    ax_cum.fill_between(range(len(cumulative)), cumulative, 0,
                         where=cumulative < 0, color=RED, alpha=0.15)
    ax_cum.plot(range(len(cumulative)), cumulative, color=YELLOW, linewidth=2, alpha=0.8)
    ax_cum.axhline(y=0, color=DIM, linewidth=0.5, linestyle="--")
    ax_cum.set_ylabel("Cumulative (h)", color=DIM, fontsize=10)
    ax_cum.set_title("Cumulative Sleep Debt", color=FG, fontsize=14, fontweight="bold")
    ax_cum.set_facecolor(BG)
    ax_cum.tick_params(colors=DIM)
    for spine in ax_cum.spines.values():
        spine.set_color(GRID)

    final = cumulative[-1]
    label = "surplus" if final >= 0 else "deficit"
    color = GREEN if final >= 0 else RED
    ax_cum.text(len(cumulative) - 1, final + (1 if final >= 0 else -1.5),
                f"{final:+.1f}h ({label})", fontsize=11, color=color, ha="right", fontweight="bold")

    n = len(dates)
    step = max(1, n // 15)
    ax_cum.set_xticks(range(0, n, step))
    ax_cum.set_xticklabels([dates[i] for i in range(0, n, step)], rotation=45, ha="right")

    return _save(fig, output_path)


def render_stage_stacked(output_path: Path) -> Path:
    days = _overnight_days()
    if not days:
        return output_path

    dates = [d["date"][5:] for d in days]
    deep = [d["deep_sleep_hours"] for d in days]
    core = [d["core_sleep_hours"] for d in days]
    rem = [d["rem_sleep_hours"] for d in days]
    awake = [d["awake_hours"] for d in days]
    unspec = [d["unspecified_hours"] for d in days]

    fig, ax = _setup_fig((14, 5), "Sleep Stage Breakdown per Night")

    ax.bar(dates, deep, label="Deep", color=INDIGO, alpha=0.85, width=0.7)
    ax.bar(dates, core, bottom=deep, label="Core", color=BLUE, alpha=0.85, width=0.7)
    bottom_rem = [d + c for d, c in zip(deep, core)]
    ax.bar(dates, rem, bottom=bottom_rem, label="REM", color=PURPLE, alpha=0.85, width=0.7)
    bottom_awake = [r + b for r, b in zip(rem, bottom_rem)]
    ax.bar(dates, awake, bottom=bottom_awake, label="Awake", color=RED, alpha=0.6, width=0.7)
    bottom_unspec = [a + b for a, b in zip(awake, bottom_awake)]
    ax.bar(dates, unspec, bottom=bottom_unspec, label="Unspecified", color="#475569", alpha=0.5, width=0.7)

    ax.set_ylabel("Hours", color=DIM, fontsize=11)
    ax.legend(loc="upper right", fontsize=9, facecolor=BG, edgecolor=GRID, labelcolor=DIM, ncol=5)

    n = len(dates)
    step = max(1, n // 15)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([dates[i] for i in range(0, n, step)], rotation=45, ha="right")

    return _save(fig, output_path)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Generate sleep analysis PNG charts")
    parser.add_argument("--input", type=Path, help="Path to sleep analysis JSON (or stdin)")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for PNGs")
    args = parser.parse_args()

    load_data(args.input)

    out_dir = args.output_dir or Path("docs/assets")
    out_dir.mkdir(parents=True, exist_ok=True)

    render_sleep_duration_trend(out_dir / "chart_sleep_duration.png")
    render_stage_composition(out_dir / "chart_stage_composition.png")
    render_efficiency_trend(out_dir / "chart_efficiency_trend.png")
    render_bedtime_waketime(out_dir / "chart_bedtime_waketime.png")
    render_weekly_comparison(out_dir / "chart_weekly_comparison.png")
    render_sleep_debt(out_dir / "chart_sleep_debt.png")
    render_stage_stacked(out_dir / "chart_stage_stacked.png")

    print(json.dumps({"charts": [f.name for f in sorted(out_dir.glob("chart_*.png"))]}))


if __name__ == "__main__":
    main()
