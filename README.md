# Health Quantification

## 这是什么

AI-first 的个人健康量化基础设施。采集 Apple Health 睡眠数据，归一化落盘到 SQLite，通过 CLI 提供结构化数据接口。分析和报告完全由 AI 完成。

这个项目的第一用户是 AI agent，不是人类。人类通过 AI 来使用它。打开一个 AI 编程工具（Claude Code、Cursor、OpenCode 等），指向这个仓库，让它读 `AGENTS.md` 和 skill 文件，它会自己搞清楚怎么编译、部署、采集数据、分析、生成报告。

## 架构

三层分离，各层可独立运行：

```
iPhone (HealthKit) --POST--> Mac (FastAPI:7996) --write--> SQLite
                                                       --read--> CLI (JSON) --> AI
```

- **采集层**：iOS app，HealthKit 读取睡眠数据 POST 到 FastAPI
- **写入层**：FastAPI server，幂等写入 SQLite（pm2 管理，Tailscale 内网通信）
- **数据层**：Python CLI，只读查询 SQLite，输出 JSON；AI 负责分析和报告生成

## 如何使用（通过 AI）

### 前置条件

- macOS + Xcode（编译 iOS app）
- Python 3.11+（CLI 和后端）
- 一台 iPhone + Apple Watch（数据源）
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

5. **让 AI 用 Xcode 编译 iOS app**。它会读 `AGENTS.md` 中的 iOS 相关说明，处理 build settings、entitlements、ATS exception 等配置。在真机上运行，授权 HealthKit 访问，点击 Export Sleep 同步数据。

6. **让 AI 做分析**。告诉它你想要什么（比如"帮我分析过去 30 天的睡眠质量"），它会：
   - 调用 CLI 获取 JSON 数据
   - 自行决定分析角度（趋势、异常、对比、阶段分解等）
   - 用 matplotlib 生成 PNG 图表，输出到 `docs/assets/`
   - 撰写 Markdown 报告，输出到 `docs/reports/`

### CLI 数据接口

AI 通过以下命令获取原始数据，然后自行分析：

```bash
python -m health_quantification.cli doctor config          # 查看当前配置
python -m health_quantification.cli db init                # 初始化数据库
python -m health_quantification.cli sleep analyze --days 30 --format json   # 多日汇总
python -m health_quantification.cli sleep daily --date 2026-03-30 --format json  # 单日明细
```

CLI 只输出数据。所有分析逻辑、可视化、报告格式由 AI 决定。`src/health_quantification/artifacts/report.py` 提供两个 PNG 图表辅助函数（`render_bar_chart_png`、`render_comparison_chart_png`），AI 可以调用也可以自己用 matplotlib 画。

### 人类直接使用

如果不想用 AI，也可以手动跑 CLI 看 JSON 输出，或者用 `--format text` 获得人类可读的文本摘要。但完整的分析和报告生成能力只在 AI 工作流中可用。

## 当前明确不做的事

- GUI-first 产品
- App Store 分发
- 实时告警
- 直接从 Python 访问 HealthKit
- 医疗诊断或治疗建议
- Phase 1 以外的数据源（HRV、步数、体重等）
- CLI 内置的报告生成（这是 AI 的活）
