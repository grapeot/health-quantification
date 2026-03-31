# Health Quantification Skill

## 元数据

- 类型: Workflow
- 适用场景: 需要读取、整理、汇总或分析 `health_quantification` 项目中的个人健康数据时
- 项目路径: `adhoc_jobs/health_quantification/`

## 目标

用项目内稳定的 library 与 CLI 合同管理个人健康量化数据。重点是把原始 observation、日级 summary 和 artifact 保持一致，让 AI 和人类都能基于同一事实层工作。

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

## CLI 合同

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --date YYYY-MM-DD --format json
python -m health_quantification.cli artifact daily-card --date YYYY-MM-DD --output <path>
```

## 建议工作流

分析睡眠数据时直接用 CLI 读 SQLite，**不需要后端运行**。后端（FastAPI）只在 iOS 同步数据时需要。如果分析结果中今天或昨天没有数据，提醒用户先打开 iOS app 同步。

## 已知限制

- 当前只有睡眠数据，HRV/步数/体重等 Phase 2
- Apple Watch 午睡追踪精度低，通常只有 1 条 `asleep_unspecified`
- 跨午夜数据按用户本地时区归属日期
- bedtime/wake_time 因 cross-midnight split 精度不够，需要 session segmentation 改进
