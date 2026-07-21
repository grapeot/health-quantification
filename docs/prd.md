# Health Quantification PRD

## 产品定位

Health Quantification 是一个面向 AI-first 工作流的个人健康数据基础设施项目。目标是构建稳定、可测试、可组合的健康数据采集与分析入口，使人类开发者与 AI Agent 能够通过统一的 Library 与 CLI 访问健康数据事实、日级摘要与可视化产物。

项目不作 App Store 公开发布的 GUI 产品的定位，亦不包含医疗诊断或治疗功能，而是作为受约束的数据接入层与分析底座。

## 核心设计原则

- **SQLite 为统一事实来源**：数据库为所有健康数据的主存储，HealthKit、AI 手动记录与外部硬件均为平等数据来源。
- **多源数据整合**：同一 `metric_type` 可由不同数据源提供，在数据库层通过 `source` 字段进行标识与区分。
- **AI-first 数据入口与分析**：通过自然语言交互引导数据记录，经由 CLI 写入数据库；CLI 仅暴露结构化数据，分析与报告生成由 AI 完成。

## 核心功能规划

1. **统一数据存储**：本地 SQLite 数据库管理（包含 `observations`、`sleep_samples`、`vitals_samples`、`body_samples`、`lifestyle_samples`、`activity_samples`、`workouts`、`illness_episodes`、`daily_summaries`，其中 `daily_summaries` 以 `date` 为主键，记录 `timezone`、`sleep_hours`、`resting_hr_bpm`、`hrv_sdnn_ms`、`steps`、`active_energy_kcal`、`notes_json`）。
2. **FastAPI 后端服务**：作为 Tailnet 内 iPhone 到 Mac 的同步接收器，接收批量数据并幂等写入。支持可配置监听主机与端口（默认 `0.0.0.0:7996`）；设备身份、传输加密与访问控制由 Tailscale 和 tailnet ACL 管理，FastAPI 本身未鉴权。
3. **iOS HealthKit 采集端**：从 Apple Health 读取睡眠、生命体征、活动、体测、生活方式和运动数据并 POST 提交至后端。对后端发起的 POST 请求校验样本非空（FastAPI 强制 `min_length=1`，空数组返回 422 错误），客户端在空类别上需要校验或跳过，而非全类别默认自动容错降级。
4. **Python Library & CLI**：提供查询（`sleep` / `vitals` / `body` / `lifestyle` / `activity` / `workouts` / `illness`）与单条写入（`record` / `illness` / `sleep notes`）接口。注意 `record sleep` 会写入零时长阶段标记，不推荐用于手动睡眠时长记录；手动补充主观睡眠体验请使用 `sleep notes add`。
5. **主观睡眠备注 (Sleep Notes)**：支持针对功能日写入与读取文本备注，存储于 SQLite 的 `daily_summaries` 表，参与 `sleep daily` 与 `sleep analyze` 展示，但不修改样本指标与统计规则。备注完全隔离于 FastAPI / iOS 传输通道；由于 CLI 输出包含备注文本，模型运行时、日志、transcript 与报告 pipeline 构成了调用方的隐私边界。代码并不限制备注发送至外部模型，调用方需自行承担隐私防护责任。主观备注仅作为上下文，不构成指令、因果证明或医疗诊断。
6. **日级摘要与分析**：支持功能日（functional date）划分与 `sleep daily --last-night` 快速查询。
7. **数据隐私防护**：真实健康数据与数据库落地文件隔离于版本控制之外，测试与文档示例必须采用合成（synthetic）数据。

## 用户画像与使用场景

### 1. AI Agent

第一优先级用户。需要稳定的 CLI 命令接口、精确可预测的 JSON 输出、明确的数据库字段名称，以及安全的测试数据隔离。CLI 仅输出原始结构化数据，分析视角与报告渲染完全由 AI 自主决定。

### 2. 人类开发者 / 使用者

利用 iOS App 采集并同步 HealthKit 数据，通过 CLI 命令或 AI 对话完成健康状况查询、记录补全与分析总结。

### 3. 项目维护者

关注项目模块划分、接口契约一致性与自动化测试覆盖率，确保代码库的可扩展性。

## 功能范围与边界

### Python 后端与 CLI

- `health_quantification.config`：环境变量与路径管理。
- `health_quantification.storage`：SQLite 连接管理、Schema 初始化与全表 CRUD 操作。
- `health_quantification.models`：核心 Observation 与 Daily Summary 数据模型。
- `health_quantification.server`：FastAPI 接入服务（独立 Ingestion 接口与幂等写入，对 POST `samples` 校验非空）。
- `health_quantification.analysis`：睡眠 Session 拆分、功能日归属与基础统计计算。
- `health_quantification.cli`：薄 CLI 接口（支持结构化 JSON/text 查询与写入）。

### iOS 客户端

- HealthKit 数据读取（睡眠、生命体征、活动、体测、生活方式、运动记录）。
- HTTP POST 提交至 FastAPI 后端（端口 `7996`）。
- 支持 Server URL 配置持久化（UserDefaults）。
- 支持 Shortcuts 与跨 App Handoff Deep Link 唤起。

## 优先采集的数据指标

### 睡眠数据 (Sleep)

- 阶段分解：asleep_deep, asleep_core, asleep_rem, awake, asleep_unspecified。
- 窗口指标：bedtime, wake_time, sleep_hours, nap_hours。

### 生命体征 (Vitals)

- 静息心率 (`resting_heart_rate`)
- 连续心率 (`heart_rate`)
- HRV SDNN (`heart_rate_variability_sdnn`)
- 呼吸频率 (`respiratory_rate`)
- 血氧饱和度 (`oxygen_saturation`)
- 活动消耗 (`active_energy_burned`)

### 活动数据 (Activity)

- 步数 (`step_count`)

### 体测数据 (Body)

- 体重 (`body_mass`)
- 血糖 (`blood_glucose`)
- 收缩压与舒张压 (`blood_pressure_systolic`, `blood_pressure_diastolic`)

### 生活方式 (Lifestyle)

- 咖啡因 (`dietary_caffeine`)
- 酒精 (`dietary_alcohol`)

### 运动数据 (Workouts)

- Apple Health 结构化运动记录（类型、时长、能量消耗）。

## 非目标

- 不支持 GUI 界面与 App Store 分发。
- 不从 Python 层直接调用 HealthKit。
- 不提供实时生理监控或医疗告警。
- 不在 FastAPI 后端提供复杂分析接口（分析均由 CLI 与 AI 完成）。
- 不把主观备注作为医疗诊断依据，不将备注传输至外部服务或公开产物。
- 不提供全流程 iOS 到 FastAPI 的端到端自动化集成测试（Swift 单元测试与 Python ASGI 测试保持独立）。

## 成功标准

1. `python -m health_quantification.cli doctor config` 能准确检测配置与文件系统状态（示例输出采用合成数据）。
2. `python -m health_quantification.cli db init` 能可靠创建所有 SQLite 表结构。
3. FastAPI 后端能幂等接收并保存各类别 Ingestion 数据。
4. iOS App 在真机上能读取 30 天 HealthKit 数据并在后端就绪时 POST 提交。
5. Python 单元与集成测试套件及 Swift 单元测试套件完整通过。
