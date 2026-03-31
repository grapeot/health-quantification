from __future__ import annotations

from pathlib import Path

from health_quantification.analysis.sleep import DaySleepMetrics, SleepAnalysisSummary


def render_bar_chart_png(
    analysis: SleepAnalysisSummary,
    output_path: Path,
    *,
    figsize=(14, 6),
    dpi=150,
    target_hours: float = 7.5,
) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    BG = "#0f172a"
    FG = "#e2e8f0"
    DIM = "#475569"
    SUBTLE = "#94a3b8"
    BLUE = "#3b82f6"
    RED = "#f87171"
    YELLOW = "#fbbf24"
    GREEN = "#4ade80"

    daily = [d for d in analysis.daily if d.sample_count > 0 and not d.has_nap]
    if not daily:
        return output_path

    dates = [d.date[5:] for d in daily]
    hours = [d.total_sleep_hours for d in daily]
    colors = [RED if h < 5 else YELLOW if h < 6 else BLUE if h < 8 else GREEN for h in hours]

    fig_h = max(5, len(daily) * 0.22)
    fig, ax = plt.subplots(figsize=(figsize[0], fig_h), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_title("Sleep Duration (overnight only)", color=FG, fontsize=16, fontweight="bold", pad=16)
    bars = ax.barh(dates, hours, color=colors, height=0.7, edgecolor="none", alpha=0.8)
    ax.axvline(x=target_hours, color=YELLOW, linestyle="--", alpha=0.4, label=f"{target_hours}h target")
    ax.axvline(x=6.0, color=RED, linestyle="--", alpha=0.3, label="6h minimum")
    ax.set_xlabel("Hours", color=DIM, fontsize=11)
    ax.invert_yaxis()
    ax.tick_params(colors=DIM, labelsize=10)
    for spine in ax.spines.values():
        spine.set_color("#1e293b")
    ax.legend(loc="lower right", fontsize=9, facecolor=BG, edgecolor="#1e293b", labelcolor=DIM)
    for bar, h in zip(bars, hours):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{h:.1f}h", va="center", fontsize=9, color=SUBTLE)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=2)
    fig.savefig(output_path, dpi=dpi, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return output_path


def render_comparison_chart_png(
    before_avg: dict[str, float],
    after_avg: dict[str, float],
    split_date: str,
    output_path: Path,
    *,
    figsize=(12, 5),
    dpi=150,
) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    BG = "#0f172a"
    FG = "#e2e8f0"
    DIM = "#475569"
    SUBTLE = "#94a3b8"
    BLUE = "#3b82f6"
    PURPLE = "#8b5cf6"
    GREEN = "#4ade80"
    RED = "#f87171"

    metrics = [
        ("Total Sleep", "h", "total_sleep_hours"),
        ("Deep", "h", "deep_sleep_hours"),
        ("Core", "h", "core_sleep_hours"),
        ("REM", "h", "rem_sleep_hours"),
        ("Efficiency", "%", "sleep_efficiency"),
    ]

    fig, ax = plt.subplots(figsize=figsize, facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_title(f"Before vs After (split: {split_date})", color=FG, fontsize=16, fontweight="bold", pad=16)

    x = np.arange(len(metrics))
    width = 0.35
    before_vals = [before_avg.get(k, 0) for _, _, k in metrics]
    after_vals = [after_avg.get(k, 0) for _, _, k in metrics]

    bars_b = ax.bar(x - width / 2, before_vals, width, label="Before", color=BLUE, alpha=0.8)
    bars_a = ax.bar(x + width / 2, after_vals, width, label="After", color=PURPLE, alpha=0.8)

    for i, (_, unit, _) in enumerate(metrics):
        diff = after_vals[i] - before_vals[i]
        diff_str = f"+{diff:.1f}{unit}" if diff >= 0 else f"{diff:.1f}{unit}"
        color = GREEN if diff >= 0 else RED
        y = max(before_vals[i], after_vals[i]) + 0.2
        ax.text(i, y, diff_str, ha="center", fontsize=10, color=color, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([name for name, _, _ in metrics], color=FG, fontsize=11)
    ax.legend(loc="upper right", fontsize=9, facecolor=BG, edgecolor="#1e293b", labelcolor=DIM)
    ax.tick_params(colors=DIM)
    for spine in ax.spines.values():
        spine.set_color("#1e293b")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=2)
    fig.savefig(output_path, dpi=dpi, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return output_path
