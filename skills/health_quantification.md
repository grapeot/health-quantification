# Health Quantification Skill

## 元数据

- 类型: Workflow
- 适用场景: 需要读取、整理、汇总或分析 `health_quantification` 项目中的个人健康数据时
- 项目路径: `adhoc_jobs/health_quantification/`

## 目标

用项目内稳定的 library 与 CLI 合同管理个人健康量化数据。重点是把原始 observation、日级 summary 和 artifact 保持一致，让 AI 和人类都能基于同一事实层工作。

## 验收标准

- 使用者可以通过 `python -m health_quantification.cli doctor config` 确认配置状态
- 使用者可以通过 `db init` 初始化本地数据库
- 使用者可以通过 `summary daily` 获取稳定 JSON
- 使用者可以通过 `artifact daily-card` 产出一张日级卡片
- 任何新增数据源都必须落在既有模块边界内，不把分析逻辑写进 adapter 或 shell

## 关键边界

- 真正逻辑只放在 `src/health_quantification/`
- `scripts/health_quant` 是稳定 wrapper，不写业务逻辑
- `native/apple_health_exporter/` 只负责未来 Apple Health 原始采集，不负责分析
- 不把真实个人健康数据提交到 git
- `docs/working.md` 记录变更与踩坑结论

## 建议工作流

优先顺序应当是：先确认配置和本地数据库，再看 summary contract，最后看 artifact。需要新接一个数据源时，先修改 schema / ingestion 边界，再决定是否需要新的 CLI 子命令。

## 已知限制

- 当前 phase 1 没有真实 Apple Health ingest 能力
- 当前 artifact 只是一张最小 SVG 卡片，不代表最终 UI 方向
- live integration tests 还只是保留位，真实接入后再补
