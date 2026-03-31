import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta


OUTPUT_DIR = Path("/Users/grapeot/co/knowledge_working/adhoc_jobs/health_quantification/docs/assets")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def plot_sleep_overview(sleep: dict, steps_data: dict, rhr_data: dict, hrv_data: dict):
    fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)
    fig.suptitle("30-Day Health Dashboard (Mar 2 - Mar 31, 2026)", fontsize=16, fontweight="bold", y=0.98)

    daily = sleep["daily"]
    dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in daily]
    sleep_hours = [d["total_sleep_hours"] for d in daily]
    deep_hours = [d["deep_sleep_hours"] for d in daily]
    rem_hours = [d["rem_sleep_hours"] for d in daily]
    efficiency = [d["sleep_efficiency"] for d in daily]

    ax1 = axes[0]
    ax1.bar(dates, sleep_hours, color="#4A90D9", alpha=0.8, label="Total Sleep")
    ax1.bar(dates, deep_hours, bottom=sleep_hours, color="#1A3A5C", alpha=0.9, label="Deep Sleep")
    ax1.bar(dates, rem_hours, bottom=[s+d for s,d in zip(sleep_hours, deep_hours)], color="#E8833A", alpha=0.8, label="REM")
    ax1.axhline(y=7, color="green", linestyle="--", alpha=0.5, label="7h target")
    ax1.axhline(y=5.93, color="#4A90D9", linestyle=":", alpha=0.5, label=f"Avg {sleep['avg_sleep_hours']:.1f}h")
    ax1.set_ylabel("Hours")
    ax1.set_title("Sleep Duration & Stages")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.set_ylim(0, 12)

    steps_daily = {d["date"]: d["stats"]["avg"] * d["stats"]["count"] for d in steps_data["daily"]}
    steps_vals = [steps_daily.get(d["date"], 0) for d in daily]
    ax2 = axes[1]
    colors = ["#2ECC71" if s >= 8000 else "#F39C12" if s >= 4000 else "#E74C3C" for s in steps_vals]
    ax2.bar(dates, steps_vals, color=colors, alpha=0.8)
    ax2.axhline(y=8000, color="green", linestyle="--", alpha=0.5, label="8k target")
    ax2.set_ylabel("Steps")
    ax2.set_title("Daily Step Count")
    ax2.legend(loc="upper right", fontsize=8)

    rhr_daily = {d["date"]: d["stats"]["avg"] for d in rhr_data["daily"] if d["stats"]["avg"]}
    rhr_vals = [rhr_daily.get(d["date"]) for d in daily]
    ax3 = axes[2]
    valid_dates = [d for d, v in zip(dates, rhr_vals) if v is not None]
    valid_rhr = [v for v in rhr_vals if v is not None]
    ax3.plot(valid_dates, valid_rhr, "o-", color="#E74C3C", markersize=4, linewidth=1.5, label="Resting HR")
    avg_rhr = statistics.mean(valid_rhr) if valid_rhr else 0
    ax3.axhline(y=avg_rhr, color="#E74C3C", linestyle=":", alpha=0.5, label=f"Avg {avg_rhr:.0f} bpm")
    ax3.set_ylabel("bpm")
    ax3.set_title("Resting Heart Rate")
    ax3.legend(loc="upper right", fontsize=8)

    hrv_daily = {d["date"]: d["stats"]["avg"] for d in hrv_data["daily"] if d["stats"]["avg"]}
    hrv_vals = [hrv_daily.get(d["date"]) for d in daily]
    ax4 = axes[3]
    valid_dates_h = [d for d, v in zip(dates, hrv_vals) if v is not None]
    valid_hrv = [v for v in hrv_vals if v is not None]
    ax4.plot(valid_dates_h, valid_hrv, "o-", color="#27AE60", markersize=4, linewidth=1.5, label="HRV SDNN")
    avg_hrv = statistics.mean(valid_hrv) if valid_hrv else 0
    ax4.axhline(y=avg_hrv, color="#27AE60", linestyle=":", alpha=0.5, label=f"Avg {avg_hrv:.0f} ms")
    ax4.set_ylabel("ms")
    ax4.set_title("Heart Rate Variability (SDNN)")
    ax4.legend(loc="upper right", fontsize=8)
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax4.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    path = OUTPUT_DIR / "health_dashboard_30d.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {path}")
    return str(path)


def plot_sleep_vs_recovery(sleep: dict, rhr_data: dict, hrv_data: dict):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Sleep Quality vs Recovery Markers", fontsize=14, fontweight="bold")

    daily = sleep["daily"]
    rhr_daily = {d["date"]: d["stats"]["avg"] for d in rhr_data["daily"] if d["stats"]["avg"]}
    hrv_daily = {d["date"]: d["stats"]["avg"] for d in hrv_data["daily"] if d["stats"]["avg"]}

    paired = []
    for d in daily:
        rhr = rhr_daily.get(d["date"])
        hrv = hrv_daily.get(d["date"])
        if rhr and hrv:
            paired.append((d["total_sleep_hours"], rhr, hrv, d["date"]))

    if paired:
        sleep_h, rhr_h, hrv_h, _ = zip(*paired)
        ax1.scatter(sleep_h, rhr_h, c="#E74C3C", alpha=0.6, s=50)
        z = np.polyfit(sleep_h, rhr_h, 1)
        p = np.poly1d(z)
        x_line = np.linspace(min(sleep_h), max(sleep_h), 50)
        ax1.plot(x_line, p(x_line), "--", color="#E74C3C", alpha=0.7)
        corr = np.corrcoef(sleep_h, rhr_h)[0, 1]
        ax1.set_xlabel("Sleep Hours")
        ax1.set_ylabel("Resting HR (bpm)")
        ax1.set_title(f"Sleep vs RHR (r={corr:.2f})")
        ax1.invert_yaxis()

        ax2.scatter(sleep_h, hrv_h, c="#27AE60", alpha=0.6, s=50)
        z2 = np.polyfit(sleep_h, hrv_h, 1)
        p2 = np.poly1d(z2)
        ax2.plot(x_line, p2(x_line), "--", color="#27AE60", alpha=0.7)
        corr2 = np.corrcoef(sleep_h, hrv_h)[0, 1]
        ax2.set_xlabel("Sleep Hours")
        ax2.set_ylabel("HRV SDNN (ms)")
        ax2.set_title(f"Sleep vs HRV (r={corr2:.2f})")

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    path = OUTPUT_DIR / "sleep_vs_recovery.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {path}")
    return str(path)


def plot_steps_vs_sleep(sleep: dict, steps_data: dict):
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.suptitle("Step Count vs Sleep Duration", fontsize=14, fontweight="bold")

    daily = sleep["daily"]
    steps_daily = {d["date"]: d["stats"]["avg"] * d["stats"]["count"] for d in steps_data["daily"]}

    paired = []
    for d in daily:
        s = steps_daily.get(d["date"])
        if s and d["total_sleep_hours"] > 2:
            paired.append((s, d["total_sleep_hours"]))

    if paired:
        steps_v, sleep_v = zip(*paired)
        ax.scatter(steps_v, sleep_v, c="#3498DB", alpha=0.6, s=50)
        z = np.polyfit(steps_v, sleep_v, 1)
        p = np.poly1d(z)
        x_line = np.linspace(min(steps_v), max(steps_v), 50)
        ax.plot(x_line, p(x_line), "--", color="#3498DB", alpha=0.7)
        corr = np.corrcoef(steps_v, sleep_v)[0, 1]
        ax.set_xlabel("Daily Steps")
        ax.set_ylabel("Sleep Hours")
        ax.set_title(f"Steps vs Sleep (r={corr:.2f})")
        ax.axhline(y=7, color="green", linestyle=":", alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    path = OUTPUT_DIR / "steps_vs_sleep.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {path}")
    return str(path)


def plot_weekly_comparison(sleep: dict, steps_data: dict, rhr_data: dict, hrv_data: dict):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("Weekly Averages Comparison", fontsize=14, fontweight="bold")

    daily = sleep["daily"]
    weeks = {}
    for d in daily:
        dt = datetime.strptime(d["date"], "%Y-%m-%d")
        week_start = (dt - timedelta(days=dt.weekday())).strftime("%m/%d")
        if week_start not in weeks:
            weeks[week_start] = {"sleep": [], "rhr": [], "hrv": [], "steps": []}
        weeks[week_start]["sleep"].append(d["total_sleep_hours"])

    steps_daily = {d["date"]: d["stats"]["avg"] * d["stats"]["count"] for d in steps_data["daily"]}
    rhr_daily = {d["date"]: d["stats"]["avg"] for d in rhr_data["daily"] if d["stats"]["avg"]}
    hrv_daily = {d["date"]: d["stats"]["avg"] for d in hrv_data["daily"] if d["stats"]["avg"]}

    for d in daily:
        week_start = (datetime.strptime(d["date"], "%Y-%m-%d") - timedelta(days=datetime.strptime(d["date"], "%Y-%m-%d").weekday())).strftime("%m/%d")
        if d["date"] in steps_daily:
            weeks[week_start]["steps"].append(steps_daily[d["date"]])
        if d["date"] in rhr_daily:
            weeks[week_start]["rhr"].append(rhr_daily[d["date"]])
        if d["date"] in hrv_daily:
            weeks[week_start]["hrv"].append(hrv_daily[d["date"]])

    labels = list(weeks.keys())
    sleep_avgs = [statistics.mean(v["sleep"]) for v in weeks.values()]
    steps_avgs = [statistics.mean(v["steps"]) if v["steps"] else 0 for v in weeks.values()]
    rhr_avgs = [statistics.mean(v["rhr"]) if v["rhr"] else 0 for v in weeks.values()]
    hrv_avgs = [statistics.mean(v["hrv"]) if v["hrv"] else 0 for v in weeks.values()]

    colors = ["#4A90D9", "#2ECC71", "#E74C3C", "#9B59B6"]
    titles = ["Avg Sleep (h)", "Avg Steps", "Avg RHR (bpm)", "Avg HRV (ms)"]
    vals = [sleep_avgs, steps_avgs, rhr_avgs, hrv_avgs]

    for ax, label, color, title, val in zip(axes.flat, labels, colors, titles, vals):
        bars = ax.bar(range(len(label)), val, color=color, alpha=0.8)
        ax.set_xticks(range(len(label)))
        ax.set_xticklabels(label, rotation=45, fontsize=8)
        ax.set_title(title)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    path = OUTPUT_DIR / "weekly_comparison.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {path}")
    return str(path)


if __name__ == "__main__":
    sleep = load_json("/tmp/sleep_30d.json")
    rhr = load_json("/tmp/rhr_30d.json")
    hrv = load_json("/tmp/hrv_30d.json")
    steps = load_json("/tmp/steps_30d.json")

    p1 = plot_sleep_overview(sleep, steps, rhr, hrv)
    p2 = plot_sleep_vs_recovery(sleep, rhr, hrv)
    p3 = plot_steps_vs_sleep(sleep, steps)
    p4 = plot_weekly_comparison(sleep, steps, rhr, hrv)

    print(f"\nCharts: {p1}, {p2}, {p3}, {p4}")
