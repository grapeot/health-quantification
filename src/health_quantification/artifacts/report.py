from __future__ import annotations

from pathlib import Path

from health_quantification.analysis.sleep import DaySleepMetrics, SleepAnalysisSummary


def render_bar_chart_svg(
    analysis: SleepAnalysisSummary,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    daily = [d for d in analysis.daily if d.sample_count > 0]
    max_sleep = max((d.total_sleep_hours for d in daily), default=8)
    bar_max = max_sleep * 1.1

    svg_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="400" viewBox="0 0 960 400">',
        '  <rect width="960" height="400" fill="#0f172a" rx="12"/>',
        f'  <text x="40" y="36" fill="#e2e8f0" font-size="20" font-family="Menlo, monospace">Sleep Trend ({analysis.period_days}d)</text>',
        '  <line x1="40" y1="50" x2="920" y2="50" stroke="#334155"/>',
    ]

    y = 78
    for d in daily:
        w = round(d.total_sleep_hours / bar_max * 680)
        nap = " *" if d.has_nap else ""
        c = "#f87171" if d.total_sleep_hours < 5 else "#3b82f6"
        svg_lines.append(f'  <text x="40" y="{y}" fill="#cbd5e1" font-size="13" font-family="Menlo, monospace">{d.date[5:]}{nap}</text>')
        svg_lines.append(f'  <rect x="120" y="{y-12}" width="{w}" height="16" rx="4" fill="{c}" opacity="0.7"/>')
        svg_lines.append(f'  <text x="{128+w}" y="{y}" fill="#94a3b8" font-size="13" font-family="Menlo, monospace">{d.total_sleep_hours}h</text>')
        y += 22

    svg_lines.append('</svg>')
    output_path.write_text("\n".join(svg_lines), encoding="utf-8")
    return output_path


def render_comparison_chart_svg(
    before_avg: dict[str, float],
    after_avg: dict[str, float],
    split_date: str,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics = [
        ("Total Sleep", "h"), ("Deep", "h"), ("Core", "h"),
        ("REM", "h"), ("Efficiency", "%"),
    ]
    svg_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="340" viewBox="0 0 960 340">',
        '  <rect width="960" height="340" fill="#0f172a" rx="12"/>',
        f'  <text x="40" y="36" fill="#e2e8f0" font-size="20" font-family="Menlo, monospace">Before vs After (split: {split_date})</text>',
        '  <line x1="40" y1="50" x2="920" y2="50" stroke="#334155"/>',
        '  <text x="260" y="72" fill="#94a3b8" font-size="14" font-family="Menlo, monospace">Before</text>',
        '  <text x="520" y="72" fill="#94a3b8" font-size="14" font-family="Menlo, monospace">After</text>',
        '  <text x="740" y="72" fill="#94a3b8" font-size="14" font-family="Menlo, monospace">Delta</text>',
    ]

    y = 100
    for name, unit in metrics:
        key = name.lower().replace(" ", "_").replace("total_sleep", "total_sleep_hours").replace("efficiency", "sleep_efficiency")
        if key == "total_sleep":
            key = "total_sleep_hours"
        bv = before_avg.get(key, 0)
        av = after_avg.get(key, 0)
        diff = round(av - bv, 2)
        diff_str = f"+{diff}{unit}" if diff > 0 else f"{diff}{unit}"
        c = "#4ade80" if diff >= 0 else "#f87171"
        w_b = round(bv / 10 * 200)
        w_a = round(av / 10 * 200)
        svg_lines.append(f'  <text x="40" y="{y}" fill="#f8fafc" font-size="17" font-family="Menlo, monospace">{name}</text>')
        svg_lines.append(f'  <rect x="260" y="{y-13}" width="{w_b}" height="18" rx="4" fill="#3b82f6" opacity="0.7"/>')
        svg_lines.append(f'  <text x="{268+w_b}" y="{y}" fill="#94a3b8" font-size="14" font-family="Menlo, monospace">{bv}{unit}</text>')
        svg_lines.append(f'  <rect x="520" y="{y-13}" width="{w_a}" height="18" rx="4" fill="#8b5cf6" opacity="0.7"/>')
        svg_lines.append(f'  <text x="{528+w_a}" y="{y}" fill="#94a3b8" font-size="14" font-family="Menlo, monospace">{av}{unit}</text>')
        svg_lines.append(f'  <text x="740" y="{y}" fill="{c}" font-size="17" font-family="Menlo, monospace" font-weight="bold">{diff_str}</text>')
        y += 44

    svg_lines.append('</svg>')
    output_path.write_text("\n".join(svg_lines), encoding="utf-8")
    return output_path


def render_daily_report_md(
    metrics: DaySleepMetrics,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nap_tag = " (nap)" if metrics.has_nap else ""
    md = f"""# Sleep Report: {metrics.date}{nap_tag}

## Summary

| Metric | Value |
|---|---|
| Total Sleep | {metrics.total_sleep_hours}h |
| In Bed | {metrics.total_in_bed_hours}h |
| Efficiency | {metrics.sleep_efficiency}% |
| Bedtime | {metrics.bedtime or "n/a"} |
| Wake Time | {metrics.wake_time or "n/a"} |

## Stage Breakdown

| Stage | Hours |
|---|---|
| Deep | {metrics.deep_sleep_hours}h |
| Core | {metrics.core_sleep_hours}h |
| REM | {metrics.rem_sleep_hours}h |
| Awake | {metrics.awake_hours}h |
| Unspecified | {metrics.unspecified_hours}h |

**Data source**: {metrics.sample_count} samples from Apple Watch via HealthKit.
"""
    output_path.write_text(md, encoding="utf-8")
    return output_path


def render_analysis_report_md(
    analysis: SleepAnalysisSummary,
    output_path: Path,
    chart_path: Path | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chart_section = ""
    if chart_path and chart_path.exists():
        rel = chart_path.relative_to(output_path.parent.parent)
        chart_section = f"\n## Sleep Trend\n\n![sleep trend](../{rel})\n"

    days_with_real = [d for d in analysis.daily if d.sample_count > 0 and not d.has_nap]
    days_with_nap = [d for d in analysis.daily if d.has_nap]
    days_empty = [d for d in analysis.daily if d.sample_count == 0]

    md = f"""# Sleep Analysis Report

**Period**: {analysis.period_days} days | **Samples**: {analysis.total_samples} | **Days with data**: {analysis.days_with_data}

## Overview

| Metric | Value |
|---|---|
| Avg Sleep | {analysis.avg_sleep_hours}h |
| Avg Deep | {analysis.avg_deep_hours}h |
| Avg Core | {analysis.avg_core_hours}h |
| Avg REM | {analysis.avg_rem_hours}h |
| Avg Efficiency | {analysis.avg_efficiency}% |
| Avg Bedtime | {analysis.avg_bedtime or "n/a"} |
| Avg Wake | {analysis.avg_wake_time or "n/a"} |
{chart_section}
## Daily Data

"""
    for d in analysis.daily:
        if d.sample_count == 0:
            md += f"- **{d.date}**: no data\n"
        elif d.has_nap:
            md += f"- **{d.date}**: {d.total_sleep_hours}h sleep (nap), {d.deep_sleep_hours}h deep, {d.rem_sleep_hours}h REM\n"
        else:
            md += f"- **{d.date}**: {d.total_sleep_hours}h sleep, {d.deep_sleep_hours}h deep, {d.core_sleep_hours}h core, {d.rem_sleep_hours}h REM\n"

    md += "\n**Data source**: Apple Watch via HealthKit. Timezone: " + analysis.daily[0].timezone if analysis.daily else ""

    output_path.write_text(md, encoding="utf-8")
    return output_path
