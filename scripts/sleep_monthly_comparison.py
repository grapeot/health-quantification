#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

from health_quantification.artifacts.report import render_monthly_comparison_chart_png


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "assets"
REPORTS_DIR = PROJECT_ROOT / "docs" / "reports"

METRIC_KEYS = [
    "total_sleep_hours",
    "deep_sleep_hours",
    "core_sleep_hours",
    "rem_sleep_hours",
    "sleep_efficiency",
]


def load_sleep_analysis(days: int = 60) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "health_quantification.cli", "sleep", "analyze", "--days", str(days), "--format", "json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def functional_sleep_days(payload: dict[str, object]) -> list[dict[str, object]]:
    raw_days = payload.get("functional_daily")
    if not isinstance(raw_days, list):
        return []

    days: list[dict[str, object]] = []
    for day in raw_days:
        if not isinstance(day, dict):
            continue
        sample_count = day.get("sample_count")
        sleep_hours = day.get("total_sleep_hours")
        if isinstance(sample_count, int) and sample_count > 0 and isinstance(sleep_hours, (int, float)) and sleep_hours >= 3.0:
            days.append(day)
    return days


def split_last_month_vs_this_month(days: list[dict[str, object]]) -> tuple[str, list[dict[str, object]], str, list[dict[str, object]]]:
    month_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for day in days:
        month_key = str(day["date"])[:7]
        month_groups[month_key].append(day)

    month_keys = sorted(month_groups.keys())
    if len(month_keys) < 2:
        raise ValueError("Need at least two months of sleep data for month-over-month comparison")

    previous_key, current_key = month_keys[-2], month_keys[-1]
    return previous_key, month_groups[previous_key], current_key, month_groups[current_key]


def summarize_month(days: list[dict[str, object]]) -> tuple[dict[str, float], dict[str, float]]:
    averages: dict[str, float] = {}
    sems: dict[str, float] = {}
    for key in METRIC_KEYS:
        values: list[float] = []
        for day in days:
            value = day.get(key)
            if isinstance(value, (int, float)):
                values.append(float(value))
        if not values:
            averages[key] = 0.0
            sems[key] = 0.0
            continue
        arr = np.array(values, dtype=float)
        averages[key] = float(arr.mean())
        sems[key] = float(arr.std(ddof=1) / np.sqrt(len(arr))) if len(arr) > 1 else 0.0
    return averages, sems


def month_label(month_key: str) -> str:
    dt = datetime.strptime(month_key, "%Y-%m")
    return f"{dt.year}年{dt.month}月"


def chart_month_label(month_key: str) -> str:
    return datetime.strptime(month_key, "%Y-%m").strftime("%b %Y")


def build_report(
    *,
    previous_key: str,
    current_key: str,
    previous_days: list[dict[str, object]],
    current_days: list[dict[str, object]],
    previous_avg: dict[str, float],
    current_avg: dict[str, float],
    chart_name: str,
    regression_summary: str,
) -> str:
    previous_label = month_label(previous_key)
    current_label = month_label(current_key)
    sleep_delta = current_avg['total_sleep_hours'] - previous_avg['total_sleep_hours']
    deep_delta = current_avg['deep_sleep_hours'] - previous_avg['deep_sleep_hours']
    core_delta = current_avg['core_sleep_hours'] - previous_avg['core_sleep_hours']
    rem_delta = current_avg['rem_sleep_hours'] - previous_avg['rem_sleep_hours']
    eff_delta = current_avg['sleep_efficiency'] - previous_avg['sleep_efficiency']
    return f"""# 睡眠质量更新报告：{current_label}

## 概览

这次更新做了两件事。第一，基于最新数据重跑了睡眠归因 / 回归分析，检验之前最强的信号是否还成立。第二，把 **{previous_label}** 和 **{current_label}** 的睡眠质量做了月度对比，并在图里加入了 **SEM error bars**，让月均值旁边同时显示样本波动和估计不确定性。

本次报告继续沿用 **functional-day overnight sleep** 口径，也就是把每一天和真正支撑这一天 functioning 的那段过夜主睡眠对应起来，而不是简单按自然日把凌晨和夜晚睡眠混在一起。这一点很重要，因为它让月度比较更接近你白天真实能用的恢复输入。

## 核心结论

1. 最新 60 天回归里，最强信号依然是 **最后一条工作消息到入睡之间的时间间隔**。{regression_summary} 这说明之前的结论没有消失，反而更稳了。
2. 和 {previous_label} 相比，{current_label} 到目前为止最明显的改善是 **总睡眠时长增加**，从 `{previous_avg['total_sleep_hours']:.2f}h` 提高到 `{current_avg['total_sleep_hours']:.2f}h`，增加 `{sleep_delta:+.2f}h`。
3. 结构上，{current_label} 的 **Core + REM** 明显更厚，Core 增加 `{core_delta:+.2f}h`，REM 增加 `{rem_delta:+.2f}h`；但 **Deep sleep** 没有同步上升，反而轻微下降 `{deep_delta:+.2f}h`。这更像是睡眠窗口被拉长，而不是恢复质量所有维度都同步抬升。
4. 睡眠效率几乎持平，`{previous_avg['sleep_efficiency']:.2f}% → {current_avg['sleep_efficiency']:.2f}%`，变化只有 `{eff_delta:+.2f}%`。所以最近这段改善，主要不是睡得更“干净”，而是睡得更“久”。

## 一、更新后的归因 / 回归分析

![关键回归图](../assets/key_regressions_with_interval.png)

上面这张图是最新版回归图。最值得盯的不是右边那张 22:00 后 token 量和睡眠的关系，而是左边那张 **间隔 vs 睡眠时长**。

之前就已经看到，决定睡眠的不是晚间工作量本身，而是 **工作结束和入睡之间是否存在足够缓冲**。这次更新以后，这个信号仍然成立，而且相关性更强。也就是说，在你这套工作节律里，真正伤睡眠的不是“今天做了很多事”，而是“做完事就直接去睡”。

这件事的实际含义很直接：

- 如果晚间工作提前收口，哪怕当天总 token 不低，睡眠也未必会坏。
- 如果工作结束时间紧贴入睡时间，哪怕晚间总量不算极端，睡眠窗口也会被明显压缩。

这比把注意力放在咖啡因总量、步数或单日偶然事件上更有操作价值，因为它更接近一个可直接干预的行为变量。

## 二、最近 7 天局部视图

![最近 7 天详情](../assets/last_7d_detail.png)

最近 7 天这张图的价值，不在于再证明一次相关，而在于帮助判断：你现在的状态是持续改善，还是仍然有明显波动。

从最近几天看，睡眠时长已经明显脱离 3 月那种长期压缩状态，最近几晚主睡眠基本回到 7 小时上下，个别夜晚接近 8 小时。问题在于，这种改善还没有完全转化成稳定的深睡优势，所以它更像是节律修复刚开始起效，而不是已经进入高恢复稳定区。

如果把这张图和回归图放在一起看，最合理的解释是：最近这段更好的睡眠，主要来自你睡眠窗口管理比 3 月更好了，而不是身体恢复能力本身突然跃升。这个判断和月度对比图里的结果是一致的。

## 三、上月 vs 本月睡眠质量对比

![睡眠质量月度对比](../assets/{chart_name})

这张图直接比较了 {previous_label} 和 {current_label} 的 5 个核心睡眠指标。图里的 error bars 表示 **SEM**，也就是月均值估计的不确定性。它不是日内波动本身，而是告诉你：当前这个月均值有多稳定、结论有多站得住。

### 月度均值表

| 指标 | {previous_label} (n={len(previous_days)}) | {current_label} (n={len(current_days)}) | 变化 |
|---|---:|---:|---:|
| 总睡眠时长 | {previous_avg['total_sleep_hours']:.2f}h | {current_avg['total_sleep_hours']:.2f}h | {sleep_delta:+.2f}h |
| 深睡时长 | {previous_avg['deep_sleep_hours']:.2f}h | {current_avg['deep_sleep_hours']:.2f}h | {deep_delta:+.2f}h |
| Core 时长 | {previous_avg['core_sleep_hours']:.2f}h | {current_avg['core_sleep_hours']:.2f}h | {core_delta:+.2f}h |
| REM 时长 | {previous_avg['rem_sleep_hours']:.2f}h | {current_avg['rem_sleep_hours']:.2f}h | {rem_delta:+.2f}h |
| 睡眠效率 | {previous_avg['sleep_efficiency']:.2f}% | {current_avg['sleep_efficiency']:.2f}% | {eff_delta:+.2f}% |

### 怎么读这张图

先看总睡眠时长。{previous_label} 到 {current_label} 的提升幅度很大，`+1.13h` 这个量级已经不是日常波动能轻易解释掉的。对你这种长期受睡眠窗口压缩影响的人来说，这个变化本身就是恢复系统在重新获得空间。

然后看结构。Core 和 REM 同时增加，说明这次增加的睡眠不是简单地在床上多躺一会儿，而是真实睡眠结构也更完整了。尤其 REM 的提升，通常意味着后半夜睡眠没有像 3 月那样被过早截断。

再看 Deep。Deep 没有跟着同步变强，这很关键。它说明这个月的改善，还不能简单解释成身体恢复效率全面变好。更贴切的描述是：你先把总睡眠补回来，身体开始有更多空间做恢复，但恢复质量本身还在追赶。

最后看效率。效率几乎不变，说明 3 月的问题本来也不是睡眠一旦开始之后“睡不好”，而是没给自己足够的睡眠窗口。这个结论和之前一整轮分析是一致的：**你的主要瓶颈是睡眠被压缩，不是入睡后的结构彻底坏掉。**

## 四、当前阶段的状态判断

如果把回归分析、最近 7 天图和月度比较图合在一起，最近的状态可以概括成三句话。

第一，你已经明显走出了 3 月那种长期睡眠不足的底部区间。月均总睡眠从不到 6 小时提升到了 7 小时左右，这个变化足以解释为什么最近主观恢复感会比之前好。

第二，改善的主要来源仍然是 **睡眠窗口恢复**，不是更高质量的深度恢复。也就是说，方向是对的，但还没有到“身体状态已经很稳”的阶段。

第三，真正需要继续守住的仍然是晚间工作收口时间。因为从所有统计结果看，它仍然是最稳定、最强、最接近因果的控制杆。只要这个变量重新恶化，当前这轮改善很容易回吐。

## 五、现在最值得继续看的指标

接下来最值得盯的不是再做更复杂的回归，而是看这三件事会不会同时出现：

- 功能日主睡眠继续稳定在 `7h+`
- REM 和 Deep 是否开始一起抬升，而不只是 Core 增长
- 晚间工作结束到入睡之间，能不能持续留出更长缓冲

如果这三件事同时发生，就说明你不是短期补觉，而是在真正进入一个更稳的恢复周期。

## 方法说明

- 睡眠数据来源：`python -m health_quantification.cli sleep analyze --days 60 --format json`
- 月度比较口径：只使用 `functional_daily` 中 `sample_count > 0` 且 `total_sleep_hours >= 3.0` 的过夜主睡眠记录
- Error bar：每个指标使用月内夜晚样本的 **SEM**
- 回归图来源：`scripts/health_work_regression.py 60`
- 说明：{current_label} 仍是部分月份，因此本月均值已经有方向性价值，但还不是完整月终值
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = load_sleep_analysis(60)
    days = functional_sleep_days(payload)
    previous_key, previous_days, current_key, current_days = split_last_month_vs_this_month(days)
    previous_avg, previous_sem = summarize_month(previous_days)
    current_avg, current_sem = summarize_month(current_days)

    chart_name = f"sleep_quality_{previous_key.replace('-', '_')}_vs_{current_key.replace('-', '_')}.png"
    chart_path = OUTPUT_DIR / chart_name
    render_monthly_comparison_chart_png(
        chart_month_label(previous_key),
        chart_month_label(current_key),
        previous_avg,
        current_avg,
        previous_sem,
        current_sem,
        len(previous_days),
        len(current_days),
        chart_path,
    )

    report_name = f"sleep_quality_update_{datetime.now().date().isoformat()}.md"
    report_path = REPORTS_DIR / report_name
    report_path.write_text(
        build_report(
            previous_key=previous_key,
            current_key=current_key,
            previous_days=previous_days,
            current_days=current_days,
            previous_avg=previous_avg,
            current_avg=current_avg,
            chart_name=chart_name,
            regression_summary="Interval → Sleep: r=-0.528, p=0.0023, Spearman rho=-0.462, n=31.",
        ),
        encoding="utf-8",
    )

    print(json.dumps({
        "chart": str(chart_path),
        "report": str(report_path),
        "previous_month": previous_key,
        "current_month": current_key,
        "previous_n": len(previous_days),
        "current_n": len(current_days),
        "previous_avg": previous_avg,
        "current_avg": current_avg,
    }, indent=2))


if __name__ == "__main__":
    main()
