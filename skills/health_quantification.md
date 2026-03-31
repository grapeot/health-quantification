# Health Quantification Skill

## 元数据

- 类型: Workflow
- 适用场景: 需要读取、整理、汇总或分析个人睡眠数据时
- 项目路径: `adhoc_jobs/health_quantification/`（从 workspace 根目录调用时自动解析）

## 目标

CLI 只提供结构化数据接口（JSON/text），AI 负责所有分析、可视化和报告生成。AI 基于原始数据自由决定分析角度、报告结构和输出格式。报告以 Markdown 输出到 `docs/reports/`，图表以 PNG 输出到 `docs/assets/`。

## 架构

三层分离：

1. **采集层**：iOS app（`HealthQuantification/HealthQuantificationIOS/`），HealthKit 读取 + POST 到 FastAPI
2. **写入层**：FastAPI server（`src/health_quantification/server.py`），pm2 管理，端口 7996
3. **数据层**：Python CLI（`src/health_quantification/cli.py`），只读查询 SQLite，输出 JSON/text

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
```

`sleep analyze` 输出多日汇总 + 每日明细（JSON）。`sleep daily` 输出单日明细（JSON）。`--format text` 适合人类快速查看。

## 分析与报告

AI 完全控制分析过程。典型工作流：

1. 调用 CLI 获取 JSON 数据：`sleep analyze --days 30 --format json`
2. 基于数据自由分析（趋势、异常、对比、阶段分解等）
3. 生成可视化：使用 matplotlib 或调用 `artifacts/report.py` 中的辅助函数生成 PNG 图表
4. 撰写 Markdown 报告，引用 `../assets/` 下的 PNG 图片
5. 输出到 `docs/reports/`，文件名由 AI 决定

`artifacts/report.py` 提供 `render_bar_chart_png()` 和 `render_comparison_chart_png()` 两个辅助函数，AI 也可以直接用 matplotlib 自行绘制任意图表。

## 从不同目录调用

- **从项目目录** (`adhoc_jobs/health_quantification/`): 直接用 `.venv/bin/python -m health_quantification.cli ...`
- **从 workspace 根目录**: 用 `adhoc_jobs/health_quantification/.venv/bin/python -m health_quantification.cli ...`，或先 `cd` 到项目目录

## 建议工作流

分析睡眠数据时直接用 CLI 读 SQLite，**不需要后端运行**。后端（FastAPI）只在 iOS 同步数据时需要。如果分析结果中今天或昨天没有数据，提醒用户先打开 iOS app 同步。

## 已知限制

- 当前只有睡眠数据，HRV/步数/体重等 Phase 2
- Apple Watch 午睡追踪精度低，通常只有 1 条 `asleep_unspecified`
- 跨午夜数据按用户本地时区归属日期（使用 sample end_at 时间）
- bedtime/wake_time 因 cross-midnight split 精度不够，需要 session segmentation 改进
- `docs/reports/` 在 .gitignore 中，生成的报告不会被提交
