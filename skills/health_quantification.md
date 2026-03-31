# Health Quantification Skill

## 元数据

- 类型: Workflow
- 适用场景: 需要读取、整理、汇总或分析个人健康数据时
- 项目路径: `adhoc_jobs/health_quantification/`（从 workspace 根目录调用时自动解析）

## 目标

CLI 只提供结构化数据接口（JSON/text），AI 负责所有分析、可视化和报告生成。AI 基于原始数据自由决定分析角度、报告结构和输出格式。报告以 Markdown 输出到 `docs/reports/`，图表以 PNG 输出到 `docs/assets/`。

## 架构

三层分离：

1. **采集层**：iOS app（`HealthQuantification/HealthQuantificationIOS/`），HealthKit 读取 + POST 到 FastAPI
2. **写入层**：FastAPI server（`src/health_quantification/server.py`），pm2 管理，端口 7996
3. **数据层**：Python CLI（`src/health_quantification/cli.py`），只读查询 SQLite，输出 JSON/text

## 数据类型

| 类别 | CLI 子命令 | Ingest Endpoint | HealthKit 来源 |
|------|-----------|----------------|---------------|
| sleep | `sleep` | `/ingest/sleep` | HKCategoryType.sleepAnalysis |
| vitals | `vitals` | `/ingest/vitals` | restingHeartRate, HRV SDNN, respiratoryRate, oxygenSaturation |
| body | `body` | `/ingest/body` | bodyMass, bloodGlucose, bloodPressure (correlation) |
| lifestyle | `lifestyle` | `/ingest/lifestyle` | dietaryCaffeine, dietaryAlcohol |
| activity | `activity` | `/ingest/activity` | stepCount |

## 关键边界

- 真正逻辑只放在 `src/health_quantification/`
- `scripts/health_quant` 是稳定 wrapper，不写业务逻辑
- iOS 代码只负责 HealthKit 采集和 HTTP POST，不做分析
- 不把真实个人健康数据提交到 git
- `docs/working.md` 记录变更与踩坑结论
- HealthKit 时间戳是 UTC，分析时需转换到用户时区（默认 `America/Los_Angeles`）
- 分析直接读 SQLite，**不需要后端运行**。如果今天或昨天没有数据，提醒用户先打开 iOS app 同步
- CLI 不生成报告。报告内容和格式完全由 AI 决定

## CLI 合同

CLI 只提供数据，不做分析或报告生成：

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json|text
python -m health_quantification.cli sleep daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli vitals analyze --days 30 --format json|text
python -m health_quantification.cli vitals daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli body analyze --days 30 --format json|text
python -m health_quantification.cli body daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli lifestyle analyze --days 30 --format json|text
python -m health_quantification.cli lifestyle daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli activity analyze --days 30 --format json|text
python -m health_quantification.cli activity daily --date YYYY-MM-DD --format json|text
```

每个子命令的 `analyze --days N` 输出多日汇总（JSON）。`daily --date` 输出单日明细（JSON）。`--format text` 适合人类快速查看。Phase 2 的 `analyze` 支持可选的 `--metric TYPE` 过滤特定指标。

## 分析与报告

AI 完全控制分析过程。典型工作流：

1. 调用 CLI 获取 JSON 数据，保存到 `docs/reports/`（如 `sleep_30d.json`）
2. 基于数据自由分析（趋势、异常、对比、交叉关联等）
3. 生成可视化：使用 matplotlib 或调用 `artifacts/report.py` 中的辅助函数生成 PNG 图表，output 到 `docs/assets/`
4. 撰写 Markdown 报告，图片引用使用相对路径（如 `../assets/chart.png`），output 到 `docs/reports/`

文件分布：原始数据 JSON → `docs/reports/`，PNG 图表 → `docs/assets/`，分析报告 MD → `docs/reports/`。

`artifacts/report.py` 提供 `render_bar_chart_png()` 和 `render_comparison_chart_png()` 两个辅助函数，AI 也可以直接用 matplotlib 自行绘制任意图表。

## 分析经验

- **相关性分析比单独看均值更有价值**。步数-睡眠相关性（r=0.476）比 RHR-睡眠（r=0.09）信息量大得多。多维度交叉分析优先于单维度描述性统计。
- **Phase 2 的 `analyze` 需要指定 `--metric`**（如 `--metric resting_heart_rate`），不像 sleep 可以直接 `analyze --days 30`。
- **步数数据的处理**：CLI 返回的是每条记录的值，需要自己按天聚合（avg × count）得到日总步数。
- **HRV 的 Apple Watch 局限**：主要在睡眠中测量，短睡眠日数据可能不准确。分析 HRV 趋势时注意数据缺失天。
- **可视化用 matplotlib 直接画**比 `artifacts/report.py` 更灵活。scatter + trend line + correlation 是交叉分析的标配图。

## 从不同目录调用

- **从项目目录** (`adhoc_jobs/health_quantification/`): 直接用 `.venv/bin/python -m health_quantification.cli ...`
- **从 workspace 根目录**: 用 `adhoc_jobs/health_quantification/.venv/bin/python -m health_quantification.cli ...`，或先 `cd` 到项目目录

## 建议工作流

分析健康数据时直接用 CLI 读 SQLite，**不需要后端运行**。后端（FastAPI）只在 iOS 同步数据时需要。如果分析结果中今天或昨天没有数据，提醒用户先打开 iOS app 同步。

## 已知限制

- Apple Watch 午睡追踪精度低，通常只有 1 条 `asleep_unspecified`
- 跨午夜数据按用户本地时区归属日期（使用 sample end_at 时间）
- bedtime/wake_time 因 cross-midnight split 精度不够，需要 session segmentation 改进
- `docs/reports/` 在 .gitignore 中，生成的报告不会被提交
- `dietaryAlcohol` 用 raw value workaround（`HKQuantityTypeIdentifierDietaryAlcohol`），未经真机验证
- iOS ATS 使用 `NSAllowsArbitraryLoads`（个人项目 + Tailscale 加密内网，可接受）
