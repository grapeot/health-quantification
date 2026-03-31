from __future__ import annotations

from pathlib import Path

from health_quantification.models import DailySummary


def render_daily_card_svg(summary: DailySummary, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metric_lines = [
        f"Sleep: {format_value(summary.sleep_hours, 'h')}",
        f"RHR: {format_value(summary.resting_hr_bpm, 'bpm')}",
        f"HRV: {format_value(summary.hrv_sdnn_ms, 'ms')}",
        f"Steps: {format_value(summary.steps, '')}",
        f"Active Energy: {format_value(summary.active_energy_kcal, 'kcal')}",
    ]
    notes = " | ".join(summary.notes)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
  <rect width="960" height="540" fill="#0f172a"/>
  <text x="48" y="72" fill="#e2e8f0" font-size="36" font-family="Menlo, monospace">Health Quantification</text>
  <text x="48" y="118" fill="#94a3b8" font-size="24" font-family="Menlo, monospace">Date: {summary.date} | TZ: {summary.timezone}</text>
  <rect x="48" y="150" width="864" height="260" rx="24" fill="#111827" stroke="#334155"/>
  <text x="80" y="205" fill="#f8fafc" font-size="26" font-family="Menlo, monospace">{metric_lines[0]}</text>
  <text x="80" y="250" fill="#f8fafc" font-size="26" font-family="Menlo, monospace">{metric_lines[1]}</text>
  <text x="80" y="295" fill="#f8fafc" font-size="26" font-family="Menlo, monospace">{metric_lines[2]}</text>
  <text x="80" y="340" fill="#f8fafc" font-size="26" font-family="Menlo, monospace">{metric_lines[3]}</text>
  <text x="80" y="385" fill="#f8fafc" font-size="26" font-family="Menlo, monospace">{metric_lines[4]}</text>
  <rect x="48" y="438" width="864" height="58" rx="16" fill="#1e293b"/>
  <text x="80" y="474" fill="#cbd5e1" font-size="20" font-family="Menlo, monospace">Notes: {notes}</text>
</svg>
'''
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def format_value(value: float | int | None, suffix: str) -> str:
    if value is None:
        return "n/a"
    return f"{value}{suffix}" if suffix else str(value)
