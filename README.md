# Health Quantification

## 为什么做这个项目

`health_quantification` 是一个 AI-first 的个人健康量化基础设施项目。它的目标不是做一个面向大众分发的健康 App，而是为你自己的长期健康数据建立一个稳定、可测试、可迭代的入口层：采集 Apple Health 与其他个人健康数据源，归一化落盘，生成适合 AI 消费的快照与摘要，并为后续的自动分析、周报和电子纸展示保留清晰边界。

项目当前采用 Python-first 架构。Python 负责 schema、存储、CLI、分析和产物生成；Apple 平台侧只保留一个尽可能薄的 native adapter 边界，用来解决 HealthKit 权限与原始采集问题。这样可以把 Apple 平台约束隔离在最小范围内，同时让 AI 和人类都共享同一套 library 与 CLI contract。

## Phase 1 范围

- 标准项目骨架与独立 git repo
- Python package + CLI
- SQLite 初始化与基本配置检查
- 日级 summary schema 与最小 artifact 生成能力
- PRD / RFC / test / working 文档
- project-local skill，面向人类与 AI
- 一个可编译的 Apple Health native exporter spike

Phase 1 不承诺真实 HealthKit 读取可用，也不做 GUI，不接 App Store 分发，不做医学解释。

## 快速开始

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .[dev]
.venv/bin/python -m health_quantification.cli doctor config
.venv/bin/python -m health_quantification.cli db init
.venv/bin/python -m health_quantification.cli artifact daily-card --date 2026-03-30 --output docs/assets/daily_card.svg
```

也可以用 wrapper：

```bash
scripts/health_quant doctor config
scripts/health_quant db init
scripts/health_quant artifact daily-card --date 2026-03-30 --output docs/assets/daily_card.svg
scripts/build_native_exporter.sh
scripts/apple_health_exporter doctor
```

## CLI 合同

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli summary daily --date YYYY-MM-DD --format json
python -m health_quantification.cli artifact daily-card --date YYYY-MM-DD --output docs/assets/daily_card.svg
```

当前 CLI 只做参数解析、配置加载、调用 library、输出 JSON 或写入 artifact。所有真实逻辑都在 `src/health_quantification/`。

## Native exporter spike

项目现在包含一个 SwiftPM 形态的 Apple Health exporter spike，位于 `native/apple_health_exporter/`。它当前支持：

- `doctor`
- `export sleep --days N --output <path>`

当前机器上它已经可以编译运行，但 `doctor` 返回 `healthDataAvailable: false`，所以真正的约束已经收敛到 macOS 上 HealthKit 的权限 / 签名 / bundle 运行条件，而不是代码编译问题。

## 当前明确不做的事

- GUI-first 产品
- App Store 分发流程
- 实时告警
- 直接从 Python 访问 HealthKit
- 医疗诊断或治疗建议
- 在 phase 1 里接入所有外部数据源
