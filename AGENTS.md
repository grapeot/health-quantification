# Health Quantification

## 这个仓库是做什么的

这是一个 AI-first 的个人健康量化项目。目标是让人和 AI 用同一套 library 与 CLI，持续采集、整理和分析个人健康数据，优先服务长期自我实验、趋势判断和 AI 驱动的洞察生成。

它不是面向公众的健康 App，不是 GUI-first 产品，也不是医疗设备软件。

## 架构

三层分离：

1. **采集层（iOS app）**：通过 HealthKit 读取 Apple Health 睡眠数据，POST 到 FastAPI
2. **写入层（FastAPI server）**：接收 JSON，幂等写入 SQLite（pm2 管理，端口 7996）
3. **分析层（Python CLI）**：只读访问 SQLite，生成 summary、artifact 和 JSON 输出

## 工作环境

优先通过项目根目录的 `.venv` 运行。安装依赖时使用 `uv`：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .[dev]
```

常用命令：

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --date 2026-03-30 --format json
```

CLI 只提供结构化数据（JSON/text）。分析、可视化和报告生成由 AI 完成。AI 可调用 `artifacts/report.py` 中的辅助函数生成 PNG 图表，图表输出到 `docs/assets/`。

## 代码边界

`src/health_quantification/` 是唯一真实逻辑层。配置、schema、存储、分析、artifact 生成都应放在包内。CLI 只负责参数解析、环境装配、调用 library、输出 JSON 或写文件。`scripts/health_quant` 是稳定 wrapper，不要把业务逻辑写回脚本层。

iOS 代码在 `HealthQuantification/` 目录下，只负责 HealthKit 采集和 HTTP POST。不要把分析、存储或 AI 逻辑塞到 iOS 端。

## 安全与隐私

这个项目处理高度敏感的个人健康数据。不要把真实健康数据、导出文件或 token 提交到 git。`data/raw/` 和 `data/exports/` 默认视为私有落地区。文档与测试使用伪造 fixture，不引用真实个人记录。

## 测试与文档维护

修改 library 或 CLI 后，至少运行默认 `pytest`。改动配置、CLI 合同或数据库初始化时，再跑 `doctor config` 和相关 smoke check。重要改动同步更新 `docs/working.md`，记录变更、验证结果与新发现的约束。

## 时区注意

HealthKit 导出的时间戳全部是 UTC。CLI 分析时默认转换到 `America/Los_Angeles`（可通过 `HEALTH_QUANT_TIMEZONE` 环境变量覆盖）。跨午夜的数据需要按用户本地时间归属到正确的日期。
