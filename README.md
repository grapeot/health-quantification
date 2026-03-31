# Health Quantification

## 为什么做这个项目

`health_quantification` 是一个 AI-first 的个人健康量化基础设施项目。采集 Apple Health 睡眠数据，归一化落盘到 SQLite，通过 CLI 和 API 让人和 AI 都能查询和分析。

## 架构

三层分离，各层可独立运行：

```
iPhone (HealthKit) --POST--> Mac (FastAPI:7996) --write--> SQLite
                                                       --read--> CLI
```

- **采集层**：iOS app，HealthKit 读取睡眠数据 POST 到 FastAPI
- **写入层**：FastAPI server，幂等写入 SQLite（pm2 管理，Tailscale 内网通信）
- **分析层**：Python CLI，只读查询 SQLite，生成 summary 和 artifact

## 快速开始

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .[dev]
.venv/bin/python -m health_quantification.cli doctor config
.venv/bin/python -m health_quantification.cli db init
```

启动后端：
```bash
scripts/start_backend.sh
# 或 pm2 start ecosystem.config.cjs
```

## CLI 合同

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --date YYYY-MM-DD --format json
python -m health_quantification.cli artifact daily-card --date YYYY-MM-DD --output <path>
```

## 当前明确不做的事

- GUI-first 产品
- App Store 分发
- 实时告警
- 直接从 Python 访问 HealthKit
- 医疗诊断或治疗建议
- Phase 1 以外的数据源（HRV、步数、体重等）
