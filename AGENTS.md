# Health Quantification

## 项目定位

Health Quantification 是一个面向 AI-first 工作流的个人健康量化基础设施。项目由 Python CLI、FastAPI 后端与 iOS HealthKit 采集端组成，使用 SQLite 作为统一存储。

AI 编程工具与人类开发者使用同一套 library 和 CLI 进行数据查询、记录写入与分析。项目侧重长期数据积累与代码化分析，非面向公众分发的 App，亦非医疗诊断软件。

## 系统架构

系统包含三层结构：

1. **采集层（iOS App）**：读取 Apple Health 数据（睡眠、生命体征、活动、体测、生活方式、运动记录），仅通过同一 Tailnet 的 Tailscale 地址将数据 POST 至后端。
2. **写入层（FastAPI Backend）**：接收 JSON 数据并幂等写入 SQLite 数据库（可配置监听地址与端口，默认 `0.0.0.0:7996`）。
3. **分析与交互层（Python CLI）**：只读查询 SQLite 生成结构化 JSON/text，或执行单条数据与备注写入。AI Agent 基于 CLI 输出进行多维分析与图表生成。

## 环境与部署

使用项目根目录的 `.venv` 环境运行。安装依赖：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .[dev]
```

核心 CLI 命令（以下示例输入输出均使用合成数据）：

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --last-night --format json
python -m health_quantification.cli sleep notes add --date 2026-03-30 --note "合成示例睡眠主观备注"
python -m health_quantification.cli sleep notes get --date 2026-03-30 --format json
```

## 代码与架构边界

- 核心业务逻辑存放在 `src/health_quantification/` 目录中。
- `scripts/health_quant` 为 CLI 包装脚本，不应包含业务逻辑。
- iOS 代码位于 `HealthQuantification/` 目录，仅负责 HealthKit 数据读取与 HTTP POST 提交，不做数据分析与存储管理。
- CLI 仅提供结构化数据输出（JSON/text）。分析报告与图表生成由 AI 完成，图表输出至 `docs/assets/`。

## 辅助分析脚本

```bash
python scripts/gen_charts.py
python scripts/gen_health_dashboard.py
```

`scripts/` 下的辅助脚本用于生成分析图表与指标卡片，输出保存至 `docs/assets/`。

## 数据库 Schema 说明

直查数据库或使用 `GET /ingest/{data_type}` 时需注意字段映射与时间格式。`GET /ingest/{data_type}` 的 `metric_type` 过滤参数仅适用于 `vitals`、`body`、`lifestyle` 与 `activity`；`sleep` 采用 `stage`，`workouts` 采用 `workout_type`。

| 表 | 时间列 | 类型列 | 值列 / 计算规则 | 格式 |
|---|--------|--------|------------------|------|
| `observations` | `start_at` / `end_at` | `metric` | `value`, `unit`, `source` | ISO 8601 UTC |
| `sleep_samples` | `start_at` | `stage` (asleep_deep/core/rem/awake) | 阶段时长由 `julianday(end_at) - julianday(start_at)` 计算 | ISO 8601 UTC |
| `vitals_samples` | `recorded_at` | `metric_type` | `value` | ISO 8601 UTC |
| `body_samples` | `recorded_at` | `metric_type` | `value` | ISO 8601 UTC |
| `lifestyle_samples` | `recorded_at` | `metric_type` | `value` | ISO 8601 UTC |
| `activity_samples` | `start_at` / `end_at` | `metric_type` | `value` | ISO 8601 UTC |
| `workouts` | `start_at` / `end_at` | `workout_type` | `duration_seconds`, `total_energy_burned` | ISO 8601 UTC |
| `illness_episodes` | `start_at` / `end_at` | `label` | `severity`, `status` | ISO 8601 本地/UTC |
| `daily_summaries` | `date` (主键 YYYY-MM-DD) | — | `timezone`, `sleep_hours`, `resting_hr_bpm`, `hrv_sdnn_ms`, `steps`, `active_energy_kcal`, `notes_json` | 本地日期 |

### 日期归属与睡眠窗口

- 非睡眠数据按 `recorded_at` 本地日期归属。
- 睡眠数据采用功能日（functional date）分配：非午睡 session 归属至醒来当日的本地日期；午睡 session 按最早 `start_at` 本地日期归属。
- `sleep daily --last-night` 返回最近一段有效夜间睡眠所在功能日的完整日度数据。
- `record sleep` 命令因未提供结束时间会写入零时长的阶段标记，不宜用于记录睡眠时长；记录夜间主观体验应使用 `sleep notes add`。
- 主观睡眠备注由 `sleep notes add` 和 `sleep notes get` 管理，储存于 `daily_summaries` 的 `notes_json` 列。`sleep daily` 与 `sleep analyze` 会暴露同日 `notes`，但 `notes` 仅作为主观上下文，不修改睡眠样本、session 划分、日期归属或计算指标。

## 隐私与安全规范

- 本仓库为公开代码库。不得提交任何真实个人健康数据、设备日志、导出文件或 API token。
- `data/` 下的数据库文件、导出数据、临时文件与报告产物均视作私有落地数据，已通过 `.gitignore` 排除，不得提交至 Git 仓库。
- 新增与修改的测试与文档示例必须采用合成（synthetic）数据。
- `sleep notes` 并不存在于 FastAPI 后端与 iOS 导出的数据路径中。由于 CLI 输出了备注文本，模型运行时、系统日志、transcript 与报告 pipeline 构成了调用方的隐私边界。代码并不阻止备注传至外部模型或服务，调用方需自行承担隐私保护责任。主观备注仅作为上下文，不构成指令、因果证明或医疗诊断。
- FastAPI 只承担 iPhone 到 Mac 的同步接收器角色；CLI 在同一台 Mac 本地读取 SQLite。部署只允许同一 Tailnet 内的 iPhone 通过 Tailscale 地址访问；设备身份、传输加密与访问控制由 Tailscale 和 tailnet ACL 负责，不由 FastAPI 实现。普通 LAN HTTP 不属于受支持路径。服务仍包含未鉴权的原始接口，因此必须限制为受控 Tailnet，不能暴露到公网或普通 LAN。

## 测试与变更维护

- 系统不包含全流程 iOS 到 FastAPI 的端到端自动化测试；Xcode 项目中的 Swift 单元/序列化测试（`HealthQuantificationIOSTests`）与 Python ASGI 测试（`tests/`）是解耦的测试套件。
- 修改 Python 代码后运行 `pytest` 校验单元与集成测试。
- 涉及 CLI 或数据库配置变更时，运行 `python -m health_quantification.cli doctor config` 与 smoke checks。
- 重要技术变更应更新 `docs/working.md`。

## 时区约定

- HealthKit 导出时间戳均为 UTC 格式。
- CLI 分析层默认转换为 `America/Los_Angeles` 时区（可通过 `HEALTH_QUANT_TIMEZONE` 环境变量配置）。
