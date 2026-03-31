# Health Quantification

## 这个仓库是做什么的

这是一个 AI-first 的个人健康量化项目。目标是让人和 AI 用同一套 library 与 CLI，持续采集、整理和分析个人健康数据，优先服务长期自我实验、趋势判断和 AI 驱动的洞察生成。

它不是面向公众的健康 App，不是 GUI-first 产品，也不是医疗设备软件。Phase 1 只做标准项目骨架、Python 主体、最小 CLI、文档和 Apple Health native adapter 边界。

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
python -m health_quantification.cli summary daily --date 2026-03-30 --format json
python -m health_quantification.cli artifact daily-card --date 2026-03-30 --output docs/assets/daily_card.svg
```

## 代码边界

`src/health_quantification/` 是唯一真实逻辑层。配置、schema、存储、分析、artifact 生成都应放在包内。CLI 只负责参数解析、环境装配、调用 library、输出 JSON 或写文件。`scripts/health_quant` 是稳定 wrapper，不要把业务逻辑写回脚本层。

`native/apple_health_exporter/` 是未来 Apple Health adapter 的边界。native 代码只负责权限申请、HealthKit 读取、输出标准化快照。不要把分析、存储或 AI 逻辑塞到 native adapter 里。

## 安全与隐私

这个项目处理高度敏感的个人健康数据。不要把真实健康数据、导出文件或 token 提交到 git。`data/raw/` 和 `data/exports/` 默认视为私有落地区。文档与测试使用伪造 fixture，不引用真实个人记录。

## 测试与文档维护

修改 library 或 CLI 后，至少运行默认 `pytest`。改动配置、CLI 合同或数据库初始化时，再跑 `doctor config` 和相关 smoke check。重要改动同步更新 `docs/working.md`，记录变更、验证结果与新发现的约束。
