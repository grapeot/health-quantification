# Health Quantification

## 这是什么

AI-first 的个人健康量化基础设施。采集 Apple Health 数据（睡眠、生命体征、活动、体测、生活方式），归一化落盘到 SQLite，通过 CLI 提供结构化数据接口。分析和报告完全由 AI 完成。

这个项目的第一用户是 AI agent，不是人类。人类通过 AI 来使用它。打开一个 AI 编程工具（Claude Code、Cursor、OpenCode 等），指向这个仓库，让它读 `AGENTS.md` 和 skill 文件，它会自己搞清楚怎么编译、部署、采集数据、分析、生成报告。

## 架构

三层分离，各层可独立运行：

```
iPhone (HealthKit) --POST--> Mac (FastAPI:7996) --write--> SQLite
                                                        --read--> CLI (JSON) --> AI
```

- **采集层**：iOS app，HealthKit 读取所有数据类型 POST 到 FastAPI
- **写入层**：FastAPI server，幂等写入 SQLite（pm2 管理，Tailscale 内网通信）
- **数据层**：Python CLI，只读查询 SQLite，输出 JSON；AI 负责分析和报告生成

## 数据类型

| 类别 | 数据 | 来源 |
|------|------|------|
| 睡眠 | stages, duration, bedtime, wake time | Apple Watch 自动 |
| 生命体征 | 静息心率, HRV, 呼吸频率, 血氧 | Apple Watch 自动 |
| 活动 | 步数 | Apple Watch / iPhone 自动 |
| 体测 | 体重, 血糖, 血压 | WiFi 秤 / CGM / 蓝牙血压计 |
| 生活方式 | 咖啡因, 酒精 | Siri / Apple Health 手动记录 |
| 运动记录 | 类型、时长、卡路里、距离 | Apple Watch structured workouts |

## 如何使用（通过 AI）

### 前置条件

- macOS + Xcode（编译 iOS app）
- Python 3.11+（CLI 和后端）
- 一台 iPhone + Apple Watch（数据源）
- Apple Developer 账号（HealthKit 真机调试需要）
- Tailscale（让 iPhone 能访问 Mac 上的后端）
- Node.js + pm2（可选：用于长期托管后端；直接运行脚本则不需要）
- 一个 AI 编程工具（Claude Code / Cursor / OpenCode 等）

### 推荐工作流

1. **用 AI 工具打开这个仓库**。Claude Code 直接 `cd` 进来，Cursor 打开项目文件夹，OpenCode 在 workspace 中指向 `adhoc_jobs/health_quantification/`。

2. **让 AI 读 `AGENTS.md`**。这个文件描述了项目架构、代码边界、时区处理等所有 agent 需要知道的上下文。如果 AI 工具支持 skill 系统（如 OpenCode），`rules/skills/health_quantification.md` 提供了更完整的分析工作流指引。

3. **让 AI 完成环境搭建**：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .[dev]
.venv/bin/python -m health_quantification.cli doctor config
.venv/bin/python -m health_quantification.cli db init
```

4. **让 AI 启动后端**（数据采集需要）：

```bash
scripts/start_backend.sh
```

默认监听 `0.0.0.0:7996`。如果你想改端口或 host，先设置 `HEALTH_QUANT_SERVER_PORT` / `HEALTH_QUANT_SERVER_HOST`。

5. **让 AI 用 Xcode 编译 iOS app**。在真机上运行，授权 HealthKit 访问，点击 Export All 同步数据。

第一次在新机器上编译 iOS app 时，让 AI 带你完成这几个动作：

- 打开 `HealthQuantification/HealthQuantification.xcodeproj`
- 在 Xcode 的 Signing & Capabilities 中把 Team 改成你自己的 Apple Developer Team
- 把 app 和 test target 的 Bundle Identifier 改成你自己的命名空间，避免和仓库默认值冲突
- 选择一台真机而不是 Simulator。HealthKit 导出需要真机权限
- 在 iPhone 上确认开发者信任和 Health 权限弹窗

启动后端后，iOS app 里的 Server URL 不要填 `localhost`。请填写你的 Mac 在同一个 Tailscale 网络下的地址，例如 `http://100.x.x.x:7996`。

6. **让 AI 做分析**。告诉它你想要什么（比如"帮我分析过去 30 天的综合健康状况"），它会：
   - 调用 CLI 获取各类型 JSON 数据
   - 自行决定分析角度（趋势、异常、交叉关联等）
   - 用 matplotlib 生成 PNG 图表，输出到 `docs/assets/`
   - 撰写 Markdown 报告，输出到 `docs/reports/`

### CLI 数据接口

AI 通过以下命令获取原始数据，然后自行分析：

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --date 2026-03-30 --format json
python -m health_quantification.cli vitals analyze --days 30 --format json
python -m health_quantification.cli body analyze --days 30 --format json
python -m health_quantification.cli lifestyle analyze --days 30 --format json
python -m health_quantification.cli activity analyze --days 30 --format json
python -m health_quantification.cli vitals analyze --days 30 --metric heart_rate --format json
python -m health_quantification.cli vitals analyze --days 30 --metric active_energy_burned --format json
python -m health_quantification.cli workouts analyze --days 30 --format json
```

CLI 只输出数据。所有分析逻辑、可视化、报告格式由 AI 决定。

### 人类直接使用

如果不想用 AI，也可以手动跑 CLI 看 JSON 输出，或者用 `--format text` 获得人类可读的文本摘要。

## 当前明确不做的事

- GUI-first 产品
- App Store 分发
- 实时告警
- 直接从 Python 访问 HealthKit
- 医疗诊断或治疗建议
- 饮水量、营养日志、详细运动记录
- CLI 内置的报告生成（这是 AI 的活）
