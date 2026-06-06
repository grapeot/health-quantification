#!/usr/bin/env python3
"""Analyze Claude Code JSONL files for hourly/daily token distribution."""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

PST = timezone(timedelta(hours=-7))
CLAUDE_DIRS = [
    Path.home() / '.claude' / 'projects',
    Path.home() / '.config' / 'claude' / 'projects',
]

def parse_ts(ts_str):
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.astimezone(PST)
    except Exception:
        return None

def get_total(usage):
    if not usage:
        return 0
    return (
        usage.get('input_tokens', 0)
        + usage.get('output_tokens', 0)
        + usage.get('cache_creation_input_tokens', 0)
        + usage.get('cache_read_input_tokens', 0)
    )

def main():
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    cutoff = time.time() - days_back * 86400

    daily = defaultdict(int)
    hourly = defaultdict(lambda: defaultdict(int))
    files_scanned = 0
    msgs_found = 0

    for base_dir in CLAUDE_DIRS:
        if not base_dir.exists():
            continue
        for root, dirs, files in os.walk(base_dir):
            for fname in files:
                if not fname.endswith('.jsonl'):
                    continue
                fpath = Path(root) / fname
                try:
                    if fpath.stat().st_mtime < cutoff:
                        continue
                except OSError:
                    continue
                files_scanned += 1
                try:
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
                            dt = parse_ts(d.get('timestamp'))
                            if not dt:
                                continue
                            total = get_total(d.get('message', {}).get('usage'))
                            if total <= 0:
                                continue
                            day = dt.strftime('%Y-%m-%d')
                            hour = dt.strftime('%H')
                            daily[day] += total
                            hourly[day][hour] += total
                            msgs_found += 1
                except Exception:
                    continue

    print(f"Files scanned: {files_scanned}, Messages: {msgs_found}", file=sys.stderr)
    print(f"{'Date':<12} {'Daily':>14} {'20-21':>14} {'22+':>14} {'Night%':>8}")
    print('-' * 66)
    for day in sorted(daily.keys()):
        evening = sum(hourly[day].get(h, 0) for h in ['22', '23'])
        night_20_21 = sum(hourly[day].get(h, 0) for h in ['20', '21'])
        pct = (evening / daily[day] * 100) if daily[day] > 0 else 0
        print(f"{day:<12} {daily[day]:>14,} {night_20_21:>14,} {evening:>14,} {pct:>7.1f}%")

if __name__ == '__main__':
    main()
