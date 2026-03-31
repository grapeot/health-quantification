# Health Quantification Skill

## 元数据

- 类型: Workflow
- 适用场景: 需要读取、整理、汇总或分析个人睡眠数据时
- 项目路径: `adhoc_jobs/health_quantification/`（从 workspace 根目录调用时自动解析）

## 目标

用项目内稳定的 library 与 CLI 合同管理个人健康量化数据。AI 和人类基于同一事实层工作，报告以 Markdown 输出到 `docs/reports/`，图表以 SVG 输出到 `docs/assets/`。

## 架构

三层分离：

1. **采集层**：iOS app（`HealthQuantification/HealthQuantificationIOS/`），HealthKit 读取 + POST 到 FastAPI
2. **写入层**：FastAPI server（`src/health_quantification/server.py`），pm2 管理，端口 7996
3. **分析层**：Python CLI（`src/health_quantification/cli.py`），只读查询 SQLite

## 关键边界

- 真正逻辑只放在 `src/health_quantification/`
- `scripts/health_quant` 是稳定 wrapper，不写业务逻辑
- iOS 代码只负责 HealthKit 采集和 HTTP POST，不做分析
- 不把真实个人健康数据提交到 git
- `docs/working.md` 记录变更与踩坑结论
- HealthKit 时间戳是 UTC，分析时需转换到用户时区（默认 `America/Los_Angeles`）
- 分析直接读 SQLite，**不需要后端运行**。如果今天或昨天没有数据，提醒用户先打开 iOS app 同步

## CLI 合同

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json|text
python -m health_quantification.cli sleep daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli report analyze --days 30
python -m health_quantification.cli report daily --date YYYY-MM-DD
```

`sleep` 子命令输出到 stdout（JSON 或 text）。`report` 子命令生成 MD 报告到 `docs/reports/`，SVG 图表到 `docs/assets/`。

## 报告生成

AI 决定文件名，输出到 `docs/reports/`：

- `report analyze --days N` → `docs/reports/sleep_analysis_{N}d.md` + `docs/assets/sleep_trend.svg`
- `report daily --date YYYY-MM-DD` → `docs/reports/sleep_{date}.md`

AI 也可以直接调用 `artifacts/report.py` 的函数，自由组合内容和文件名。报告 MD 中引用 `../assets/` 下的 SVG。

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
