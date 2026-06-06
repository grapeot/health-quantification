#!/usr/bin/env python3
"""Full-range health & work analysis with session-to-sleep interval."""

import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from scipy import stats

PST = timezone(timedelta(hours=-7))
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "assets"
CLAUDE_DIRS = [Path.home() / '.claude' / 'projects']
OPENCODE_DB = Path.home() / '.local' / 'share' / 'opencode' / 'opencode.db'

BG = "#0f172a"
FG = "#e2e8f0"
DIM = "#475569"
SUBTLE = "#94a3b8"
BLUE = "#3b82f6"
RED = "#f87171"
YELLOW = "#fbbf24"
GREEN = "#4ade80"
PURPLE = "#a78bfa"
ORANGE = "#fb923c"
CYAN = "#22d3ee"
FONT_ZH = FontProperties(family=['STHeiti', 'Heiti TC', 'PingFang HK', 'Arial Unicode MS'])


def get_claude_code_data(days_back=40):
    cutoff = (datetime.now(PST) - timedelta(days=days_back)).timestamp()
    daily_total = defaultdict(int)
    daily_evening = defaultdict(int)
    daily_evening20 = defaultdict(int)
    last_msg_ts = {}

    for base_dir in CLAUDE_DIRS:
        if not base_dir.exists():
            continue
        for root, _, files in os.walk(base_dir):
            for fname in files:
                if not fname.endswith('.jsonl'):
                    continue
                fpath = Path(root) / fname
                try:
                    if fpath.stat().st_mtime < cutoff:
                        continue
                except OSError:
                    continue
                with open(fpath, 'r', errors='replace') as f:
                    for line in f:
                        line = line.strip()
                        if not line or '"type":"assistant"' not in line:
                            continue
                        try:
                            d = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if d.get('type') != 'assistant':
                            continue
                        ts = d.get('timestamp')
                        if not ts:
                            continue
                        try:
                            dt = datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(PST)
                        except Exception:
                            continue
                        usage = d.get('message', {}).get('usage', {})
                        total = (usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
                                 + usage.get('cache_creation_input_tokens', 0)
                                 + usage.get('cache_read_input_tokens', 0))
                        if total <= 0:
                            continue
                        day = dt.strftime('%Y-%m-%d')
                        hour = int(dt.strftime('%H'))
                        daily_total[day] += total
                        if hour >= 22:
                            daily_evening[day] += total
                        if hour >= 20:
                            daily_evening20[day] += total
                        if day not in last_msg_ts or dt.timestamp() > last_msg_ts[day]:
                            last_msg_ts[day] = dt.timestamp()
    return daily_total, daily_evening, daily_evening20, last_msg_ts


def get_opencode_data(days_back=40):
    import sqlite3
    conn = sqlite3.connect(str(OPENCODE_DB))
    rows = conn.execute("""
        SELECT date(time_created / 1000, 'unixepoch', 'localtime') as day,
               cast(strftime('%H', time_created / 1000, 'unixepoch', 'localtime') as integer) as hour,
               sum(json_extract(data, '$.tokens.total')) as total_tokens
        FROM message
        WHERE json_extract(data, '$.role') = 'assistant'
          AND json_extract(data, '$.tokens.total') IS NOT NULL
          AND time_created >= (strftime('%s', 'now') - ? * 86400) * 1000
        GROUP BY day, hour
    """, (days_back,)).fetchall()
    last_ts_rows = conn.execute("""
        SELECT date(time_created / 1000, 'unixepoch', 'localtime') as day,
               max(time_created / 1000) as last_ts
        FROM message
        WHERE json_extract(data, '$.role') = 'assistant'
          AND time_created >= (strftime('%s', 'now') - ? * 86400) * 1000
        GROUP BY day
    """, (days_back,)).fetchall()
    conn.close()

    daily_total = defaultdict(int)
    daily_evening = defaultdict(int)
    daily_evening20 = defaultdict(int)
    oc_last_ts = {}
    for day, hour, total in rows:
        if total is None:
            continue
        daily_total[day] += total
        if hour >= 22:
            daily_evening[day] += total
        if hour >= 20:
            daily_evening20[day] += total
    for day, ts in last_ts_rows:
        oc_last_ts[day] = ts / 1000.0
    return daily_total, daily_evening, daily_evening20, oc_last_ts


def get_sleep_data(days_back=40):
    result = subprocess.run(
        [sys.executable, '-m', 'health_quantification.cli', 'sleep', 'analyze',
         '--days', str(days_back), '--format', 'json'],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent)
    )
    data = json.loads(result.stdout)
    sleep = {}
    for d in data.get('daily', []):
        s = d.get('total_sleep_hours') or 0
        if s < 0.5:
            continue
        bt = d.get('bedtime', '')
        bt_hour = None
        if bt:
            parts = bt.split(':')
            bt_hour = int(parts[0]) + int(parts[1]) / 60.0
        sleep[d['date']] = {
            'sleep_hours': s,
            'efficiency': d.get('sleep_efficiency') or 0,
            'deep': d.get('deep_sleep_hours') or 0,
            'rem': d.get('rem_sleep_hours') or 0,
            'core': d.get('core_sleep_hours') or 0,
            'bedtime_hour': bt_hour,
            'bedtime_str': bt,
        }
    return sleep


def compute_interval(last_msg_ts, bedtime_hour):
    interval = {}
    for day, bt_h in bedtime_hour.items():
        if bt_h is None:
            continue
        ts = last_msg_ts.get(day)
        if ts is None:
            interval[day] = None
            continue
        msg_dt = datetime.fromtimestamp(ts, tz=PST)
        bt_minute = int(bt_h * 60)
        sleep_date = datetime.strptime(day, '%Y-%m-%d').replace(tzinfo=PST)
        bt_dt = sleep_date.replace(hour=bt_minute // 60, minute=bt_minute % 60)
        diff_min = (bt_dt - msg_dt).total_seconds() / 60.0
        interval[day] = diff_min
    return interval


def main():
    days_back = 40
    print("Collecting Claude Code data...")
    cc_total, cc_e22, cc_e20, cc_last_ts = get_claude_code_data(days_back)
    print("Collecting OpenCode data...")
    oc_total, oc_e22, oc_e20, oc_last_ts = get_opencode_data(days_back)
    print("Collecting sleep data...")
    sleep = get_sleep_data(days_back)

    merged_last_ts = {}
    for day in set(list(cc_last_ts.keys()) + list(oc_last_ts.keys())):
        c = cc_last_ts.get(day)
        o = oc_last_ts.get(day)
        merged_last_ts[day] = max(c or 0, o or 0)

    bt_hours = {d: v['bedtime_hour'] for d, v in sleep.items() if v.get('bedtime_hour')}
    interval = compute_interval(merged_last_ts, bt_hours)

    all_days = sorted(set(list(sleep.keys()) + list(cc_total.keys()) + list(oc_total.keys())))
    records = []
    for day in all_days:
        rec = {'day': day}
        cc_t = cc_total.get(day, 0)
        oc_t = oc_total.get(day, 0)
        rec['total_tokens'] = (cc_t + oc_t) / 1e6
        rec['cc_total'] = cc_t / 1e6
        rec['evening_22plus'] = (cc_e22.get(day, 0) + oc_e22.get(day, 0)) / 1e6
        rec['evening_20plus'] = (cc_e20.get(day, 0) + oc_e20.get(day, 0)) / 1e6
        if day in interval:
            rec['last_to_bed_min'] = interval[day]
        if day in sleep:
            rec.update(sleep[day])
        records.append(rec)

    valid = [r for r in records if r.get('sleep_hours', 0) >= 3.0]
    print(f"Days with valid sleep: {len(valid)}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def safe_reg(x_key, y_key, data=None, drop_zero_x=False):
        if data is None:
            data = valid
        pairs = [(r[x_key], r[y_key]) for r in data
                  if x_key in r and y_key in r and r[x_key] is not None and r[y_key] is not None]
        if drop_zero_x:
            pairs = [(x, y) for x, y in pairs if x > 0]
        if len(pairs) < 4:
            return None
        x = np.array([p[0] for p in pairs])
        y = np.array([p[1] for p in pairs])
        slope, intercept, r_val, p_val, std_err = stats.linregress(x, y)
        rho, rho_p = stats.spearmanr(x, y)
        return {'n': len(pairs), 'slope': slope, 'intercept': intercept,
                'r': r_val, 'r2': r_val**2, 'p': p_val, 'rho': rho, 'rho_p': rho_p,
                'x': x, 'y': y}

    # --- Figure 1: 40-day timeline ---
    fig1, axes1 = plt.subplots(5, 1, figsize=(18, 16), facecolor=BG, sharex=True,
                               gridspec_kw={'height_ratios': [3, 1.5, 1.5, 2, 2]})
    fig1.suptitle("40-Day Health & Work Timeline", color=FG, fontsize=16, fontweight='bold', y=0.99)

    sleep_days = [r['day'][5:] for r in valid]
    x_sl = range(len(valid))

    ax = axes1[0]
    ax.set_facecolor(BG)
    deep = [r.get('deep', 0) for r in valid]
    core = [r.get('core', 0) for r in valid]
    rem = [r.get('rem', 0) for r in valid]
    ax.bar(x_sl, deep, color=BLUE, alpha=0.8, label='Deep', width=0.7)
    ax.bar(x_sl, core, bottom=deep, color=PURPLE, alpha=0.7, label='Core', width=0.7)
    ax.bar(x_sl, rem, bottom=[d+c for d,c in zip(deep, core)], color=GREEN, alpha=0.7, label='REM', width=0.7)
    ax.axhline(y=7.5, color=YELLOW, linestyle='--', alpha=0.3, label='7.5h')
    ax.set_ylabel('Hours', color=DIM)
    ax.legend(loc='upper right', fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=DIM)
    ax.tick_params(colors=DIM)
    for s in ax.spines.values():
        s.set_color("#1e293b")

    ax = axes1[1]
    ax.set_facecolor(BG)
    bt_hours = [r.get('bedtime_hour') for r in valid]
    valid_bt = [(i, h) for i, h in enumerate(bt_hours) if h is not None]
    if valid_bt:
        ax.scatter([v[0] for v in valid_bt], [v[1] for v in valid_bt],
                   color=ORANGE, alpha=0.7, s=40, zorder=3)
        ax.axhline(y=23, color=RED, linestyle='--', alpha=0.3, label='23:00')
    ax.set_ylabel('Bedtime', color=DIM)
    ax.set_ylim(20, 26)
    ax.legend(loc='upper right', fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=DIM)
    ax.tick_params(colors=DIM)
    for s in ax.spines.values():
        s.set_color("#1e293b")

    ax = axes1[2]
    ax.set_facecolor(BG)
    eff = [r.get('efficiency', 0) for r in valid]
    valid_eff = [(i, e) for i, e in enumerate(eff) if e > 0]
    if valid_eff:
        colors_e = [GREEN if e >= 95 else YELLOW if e >= 85 else RED for e in [v[1] for v in valid_eff]]
        ax.bar([v[0] for v in valid_eff], [v[1] for v in valid_eff], color=colors_e, alpha=0.7, width=0.7)
    ax.axhline(y=95, color=GREEN, linestyle='--', alpha=0.2)
    ax.set_ylabel('Efficiency %', color=DIM)
    ax.set_ylim(60, 105)
    ax.tick_params(colors=DIM)
    for s in ax.spines.values():
        s.set_color("#1e293b")

    ax = axes1[3]
    ax.set_facecolor(BG)
    e22 = [r.get('evening_22plus', 0) for r in valid]
    ax.bar(x_sl, e22, color=RED, alpha=0.7, label='Evening 22:00+ (M)', width=0.6)
    ax_r = ax.twinx()
    total_t = [r.get('total_tokens', 0) for r in valid]
    ax_r.plot(x_sl, total_t, 'o-', color=BLUE, alpha=0.6, label='Daily Total (M)', markersize=4, linewidth=1)
    ax.set_ylabel('Evening 22+ (M)', color=RED, fontsize=9)
    ax_r.set_ylabel('Daily Total (M)', color=BLUE, fontsize=9)
    ax.legend(loc='upper left', fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=DIM)
    ax_r.legend(loc='upper right', fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=DIM)
    ax.tick_params(colors=DIM)
    ax_r.tick_params(colors=DIM)
    for s in ax.spines.values():
        s.set_color("#1e293b")
    for s in ax_r.spines.values():
        s.set_color("#1e293b")

    ax = axes1[4]
    ax.set_facecolor(BG)
    intervals = [r.get('last_to_bed_min') for r in valid]
    valid_iv = [(i, v) for i, v in enumerate(intervals) if v is not None and v >= -120 and v <= 180]
    if valid_iv:
        colors_iv = [GREEN if v >= 60 else YELLOW if v >= 15 else RED for v in [d[1] for d in valid_iv]]
        ax.bar([v[0] for v in valid_iv], [v[1] for v in valid_iv], color=colors_iv, alpha=0.7, width=0.7)
    ax.axhline(y=60, color=GREEN, linestyle='--', alpha=0.3, label='60 min')
    ax.axhline(y=15, color=YELLOW, linestyle='--', alpha=0.3, label='15 min')
    ax.axhline(y=0, color=DIM, linestyle='-', alpha=0.2)
    ax.set_ylabel('Last msg → Bedtime (min)', color=DIM, fontsize=9)
    ax.set_xlabel('Date', color=DIM, fontsize=9)
    ax.legend(loc='upper right', fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=DIM)
    ax.tick_params(colors=DIM)
    for s in ax.spines.values():
        s.set_color("#1e293b")

    axes1[4].set_xticks(x_sl)
    axes1[4].set_xticklabels(sleep_days, rotation=45, ha='right', fontsize=7)
    fig1.tight_layout(rect=[0, 0, 1, 0.98])
    out1 = OUTPUT_DIR / "timeline_40d.png"
    fig1.savefig(out1, dpi=150, facecolor=BG, bbox_inches='tight')
    plt.close(fig1)
    print(f"Saved: {out1}")

    # --- Figure 2: Key regressions with interval ---
    fig2, axes2 = plt.subplots(1, 3, figsize=(18, 5.5), facecolor=BG)
    fig2.suptitle("Key Relationships (40 days)", color=FG, fontsize=14, fontweight='bold', y=1.01)

    regressions = [
        ('last_to_bed_min', 'sleep_hours', 'Last msg → Bedtime (min)', 'Sleep Hours',
         'Interval → Sleep', CYAN, False),
        ('evening_22plus', 'sleep_hours', 'Evening 22:00+ (M)', 'Sleep Hours',
         'Evening Tokens → Sleep', RED, True),
        ('last_to_bed_min', 'efficiency', 'Last msg → Bedtime (min)', 'Efficiency %',
         'Interval → Efficiency', CYAN, False),
    ]

    results_text = []
    for i, (xk, yk, xl, yl, title, color, dz) in enumerate(regressions):
        ax = axes2[i]
        reg = safe_reg(xk, yk, drop_zero_x=dz)
        if reg is None:
            ax.set_facecolor(BG)
            ax.text(0.5, 0.5, f"Insufficient data", transform=ax.transAxes,
                    ha='center', va='center', color=DIM, fontsize=12)
            ax.set_title(title, color=FG, fontsize=12, fontweight='bold')
            for sp in ax.spines.values():
                sp.set_color("#1e293b")
            continue
        ax.set_facecolor(BG)
        ax.scatter(reg['x'], reg['y'], color=color, alpha=0.7, s=50, zorder=3)
        x_line = np.linspace(reg['x'].min(), reg['x'].max(), 50)
        y_line = reg['slope'] * x_line + reg['intercept']
        ax.plot(x_line, y_line, color=color, alpha=0.4, linewidth=2, zorder=2)
        sig = "***" if reg['p'] < 0.001 else "**" if reg['p'] < 0.01 else "*" if reg['p'] < 0.05 else "ns"
        label = (f"r={reg['r']:.2f}, p={reg['p']:.3f} {sig}\n"
                 f"rho={reg['rho']:.2f}, p={reg['rho_p']:.3f}\n"
                 f"n={reg['n']}")
        ax.text(0.05, 0.95, label, transform=ax.transAxes, fontsize=9,
                color=FG, va='top', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=BG, edgecolor=DIM, alpha=0.9))
        ax.set_xlabel(xl, color=DIM, fontsize=9)
        ax.set_ylabel(yl, color=DIM, fontsize=9)
        ax.set_title(title, color=FG, fontsize=12, fontweight='bold', pad=8)
        ax.tick_params(colors=DIM, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#1e293b")
        results_text.append(f"  {title}: beta={reg['slope']:.4f}, r={reg['r']:.3f} (p={reg['p']:.4f}), "
                            f"Spearman rho={reg['rho']:.3f} (p={reg['rho_p']:.4f}), n={reg['n']}")

    fig2.tight_layout(rect=[0, 0, 1, 0.96])
    out2 = OUTPUT_DIR / "key_regressions_with_interval.png"
    fig2.savefig(out2, dpi=150, facecolor=BG, bbox_inches='tight')
    plt.close(fig2)
    print(f"Saved: {out2}")

    # --- Figure 3: Last 7 days detail ---
    last7 = valid[-7:]
    if len(last7) >= 3:
        fig3, axes3 = plt.subplots(2, 2, figsize=(16, 10), facecolor=BG)
        fig3.suptitle("Last 7 Days Detail", color=FG, fontsize=14, fontweight='bold', y=0.98)

        days7 = [r['day'][5:] for r in last7]
        x7 = range(len(last7))

        ax = axes3[0][0]
        ax.set_facecolor(BG)
        s7 = [r.get('sleep_hours', 0) for r in last7]
        d7 = [r.get('deep', 0) for r in last7]
        c7 = [r.get('core', 0) for r in last7]
        r7 = [r.get('rem', 0) for r in last7]
        ax.bar(x7, d7, color=BLUE, alpha=0.8, label='Deep')
        ax.bar(x7, c7, bottom=d7, color=PURPLE, alpha=0.7, label='Core')
        ax.bar(x7, r7, bottom=[a+b for a,b in zip(d7, c7)], color=GREEN, alpha=0.7, label='REM')
        ax.axhline(y=7.5, color=YELLOW, linestyle='--', alpha=0.3)
        ax.set_ylabel('Hours', color=DIM)
        ax.set_title('Sleep Stages', color=FG, fontsize=11, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=DIM)
        ax.set_xticks(x7)
        ax.set_xticklabels(days7, rotation=30, ha='right', fontsize=9)
        ax.tick_params(colors=DIM)
        for sp in ax.spines.values():
            sp.set_color("#1e293b")

        ax = axes3[0][1]
        ax.set_facecolor(BG)
        e22_7 = [r.get('evening_22plus', 0) for r in last7]
        ax.bar(x7, e22_7, color=RED, alpha=0.7, width=0.6, label='Evening 22+ (M)')
        ax.set_ylabel('Tokens (M)', color=DIM)
        ax.set_title('Evening Work', color=FG, fontsize=11, fontweight='bold')
        ax.set_xticks(x7)
        ax.set_xticklabels(days7, rotation=30, ha='right', fontsize=9)
        ax.tick_params(colors=DIM)
        for sp in ax.spines.values():
            sp.set_color("#1e293b")

        ax = axes3[1][0]
        ax.set_facecolor(BG)
        iv7 = [r.get('last_to_bed_min') for r in last7]
        valid_iv7 = [(i, v) for i, v in enumerate(iv7) if v is not None]
        if valid_iv7:
            colors_iv7 = [GREEN if v >= 60 else YELLOW if v >= 15 else RED for v in [d[1] for d in valid_iv7]]
            ax.bar([v[0] for v in valid_iv7], [v[1] for v in valid_iv7], color=colors_iv7, alpha=0.8, width=0.6)
        ax.axhline(y=60, color=GREEN, linestyle='--', alpha=0.3, label='60 min ideal')
        ax.axhline(y=15, color=YELLOW, linestyle='--', alpha=0.3, label='15 min min')
        ax.axhline(y=0, color=DIM, linestyle='-', alpha=0.2)
        ax.set_ylabel('Minutes', color=DIM)
        ax.set_title('Last Message → Bedtime Interval', color=FG, fontsize=11, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=DIM)
        ax.set_xticks(x7)
        ax.set_xticklabels(days7, rotation=30, ha='right', fontsize=9)
        ax.tick_params(colors=DIM)
        for sp in ax.spines.values():
            sp.set_color("#1e293b")

        ax = axes3[1][1]
        ax.set_facecolor(BG)
        eff7 = [r.get('efficiency', 0) for r in last7]
        valid_eff7 = [(i, e) for i, e in enumerate(eff7) if e > 0]
        if valid_eff7:
            colors_e7 = [GREEN if e >= 95 else YELLOW if e >= 85 else RED for e in [v[1] for v in valid_eff7]]
            ax.bar([v[0] for v in valid_eff7], [v[1] for v in valid_eff7], color=colors_e7, alpha=0.8, width=0.6)
        ax.axhline(y=95, color=GREEN, linestyle='--', alpha=0.2)
        ax.set_ylabel('Efficiency %', color=DIM)
        ax.set_title('Sleep Efficiency', color=FG, fontsize=11, fontweight='bold')
        ax.set_ylim(60, 105)
        ax.set_xticks(x7)
        ax.set_xticklabels(days7, rotation=30, ha='right', fontsize=9)
        ax.tick_params(colors=DIM)
        for sp in ax.spines.values():
            sp.set_color("#1e293b")

        fig3.tight_layout(rect=[0, 0, 1, 0.96])
        out3 = OUTPUT_DIR / "last_7d_detail.png"
        fig3.savefig(out3, dpi=150, facecolor=BG, bbox_inches='tight')
        plt.close(fig3)
        print(f"Saved: {out3}")

    print("\n" + "=" * 70)
    print("REGRESSION RESULTS (40 days)")
    print("=" * 70)
    for line in results_text:
        print(line)

    if valid_iv:
        iv_vals = [r.get('last_to_bed_min') for r in valid if r.get('last_to_bed_min') is not None]
        sleep_iv = [r['sleep_hours'] for r in valid if r.get('last_to_bed_min') is not None]
        if len(iv_vals) >= 4:
            iv_arr = np.array(iv_vals)
            sl_arr = np.array(sleep_iv)
            pos_mask = iv_arr >= 0
            neg_mask = iv_arr < 0
            if pos_mask.sum() >= 3:
                mean_pos = sl_arr[pos_mask].mean()
            else:
                mean_pos = None
            if neg_mask.sum() >= 3:
                mean_neg = sl_arr[neg_mask].mean()
            else:
                mean_neg = None
            zero_mask = iv_arr >= 60
            if zero_mask.sum() >= 3:
                mean_good = sl_arr[zero_mask].mean()
            else:
                mean_good = None
            print(f"\nINTERVAL EFFECT SUMMARY:")
            print(f"  Positive interval (msg before bed): mean sleep = {mean_pos:.2f}h" if mean_pos else "  (insufficient data)")
            print(f"  Negative interval (msg after bed): mean sleep = {mean_neg:.2f}h" if mean_neg else "  (insufficient data)")
            print(f"  Interval >= 60min: mean sleep = {mean_good:.2f}h" if mean_good else "  (insufficient data)")


if __name__ == '__main__':
    main()
