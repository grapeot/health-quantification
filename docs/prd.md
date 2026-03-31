# Health Quantification PRD

## 产品定位

`health_quantification` 是一个面向 AI-first 工作流的个人健康数据基础设施项目。它的目标是为个人长期健康数据建立稳定、可测试、可组合的采集与分析入口，让人和 AI 可以通过同一套 library 与 CLI 访问健康事实、日级摘要和简单 artifact。

它不是 dashboard，不是面向大众分发的健康 App，也不是医疗诊断系统。它更接近一个受约束的数据入口层与分析底座：先把高价值、低摩擦、可持续的数据流做扎实，再把上层 AI 分析建立在统一事实来源上。

## 核心目标

Phase 1 交付以下能力：

1. 标准项目骨架与独立 git repo
2. Python-first library 与薄 CLI（只负责 readout / analytics）
3. SQLite 初始化与最小 schema（含 sleep_samples 表）
4. FastAPI ingestion server（只负责写入，Tailscale 内网通信）
5. iOS app 作为 Apple Health 采集端，读取睡眠数据并 POST 到 FastAPI
6. 日级 summary contract 与结构化 JSON 数据输出
7. AI 驱动的分析与报告生成（CLI 提供数据，AI 做分析）
8. 幂等 ingestion 协议（重复提交不产生重复数据）
9. 完整测试覆盖（unit + integration + UI tests）
10. pm2 进程管理 FastAPI 后端
11. PRD / RFC / test / working / skill 文档

Phase 2 在 Phase 1 基础上扩展数据采集范围，接入全部 HealthKit 可用数据类型：

12. 生命体征自动采集：静息心率、HRV、呼吸频率、血氧（Apple Watch 自动采集，零用户行为成本）
13. 活动数据自动采集：步数（Apple Watch / iPhone 自动）
14. 体测数据采集：体重（WiFi 智能秤）、血糖（CGM）、血压（蓝牙血压计）
15. 生活方式记录：咖啡因、酒精摄入（通过 Siri / Apple Health 手动记录）
16. 多维度 CLI analytics 支持所有新数据类型
17. 每种新数据类型的 ingestion endpoint、SQLite schema、幂等写入
18. iOS app 支持 Server URL 持久化（UserDefaults）

这些能力必须同时服务三类用户：AI agent、人类使用者、后续维护者。

## 用户画像

### 1. AI agent

AI 是第一优先级用户。它需要稳定的命令入口、可预测的 JSON 输出、清晰的数据边界，以及默认不会碰到真实敏感数据的测试策略。AI 应该能在不读散装脚本的前提下，完成配置检查、数据库初始化和数据查询。CLI 只输出原始数据，分析逻辑和报告生成完全由 AI 承担，以确保分析视角的灵活性和个性化。

### 2. 人类使用者

人类用户需要一个足够薄的 CLI（analytics），一个 FastAPI 后端（ingestion），和一个 iOS app（数据采集）。日常操作是：打开 iOS app 同步睡眠数据，通过 CLI 或 AI 查看分析结果。

### 3. 项目维护者

维护者关心项目是否能被长期迭代。项目不应退化成一组一次性脚本，而应保持标准项目结构、清晰模块边界、可持续文档、测试分层。

## 产品思想

### library-first

这个项目的价值不在 GUI，而在 library。CLI 负责 analytics，FastAPI 负责 ingestion，iOS 负责 collection。三者共享同一个 SQLite 和同一套 schema。

### AI-first 的个人数据底座

重点不是权限营销、分发包装或 onboarding，而是让个人健康数据可以被长期积累、被 AI 准确消费、被后续 workflow 低成本复用。FastAPI 的 Swagger UI 应该对 AI 足够自描述。

### 先 capture，再 interpret

先把原始 observation、sleep session 稳定下来，再决定哪些解释、告警或建议值得固化。

### 职责分离

CLI 只负责 readout/analytics，FastAPI 只负责 ingestion。即使 FastAPI 挂了，CLI 仍然能正常查询已有数据。

## 当前范围

### Python 侧

- `health_quantification.config`：读取环境变量和路径配置（含 server_host / server_port）
- `health_quantification.storage`：SQLite 连接、schema 初始化、所有数据类型的 CRUD
- `health_quantification.models`：核心 observation / daily summary 数据结构
- `health_quantification.server`：FastAPI ingestion server（每种数据类型独立 endpoint，幂等写入）
- `health_quantification.analysis.daily_summary`：日级摘要逻辑（支持所有数据类型）
- `health_quantification.artifacts.report`：PNG 图表辅助函数（AI 按需调用）
- `health_quantification.cli`：薄 CLI（data-only，支持所有数据类型的查询与分析）
- `scripts/health_quant`：CLI wrapper
- `scripts/start_backend.sh`：FastAPI 启动 wrapper
- `ecosystem.config.cjs`：pm2 配置

### iOS 侧

- `HealthQuantificationIOS` target：HealthKit 读取 + POST 到 FastAPI（端口 7996）
- 包含 Run Doctor / Request Health Access / Export All 按钮（单按钮导出所有数据类型）
- 支持配置 server URL（默认 `http://localhost:7996`，通过 UserDefaults 持久化）
- 读取并提交所有已接入的 HealthKit 数据类型（睡眠、生命体征、活动、体测、生活方式）
- 部分授权拒绝时优雅降级：跳过未授权类别，继续导出其余数据
- ATS 使用 `NSAllowsArbitraryLoads`（个人项目 + Tailscale 加密内网）
- Unit tests、UI tests

## 优先收集的数据

### Phase 1（已实现）

- 睡眠：duration、sleep stages、bedtime、wake time、sleep day window

### Phase 2（全部接入）

#### 生命体征（Apple Watch 自动采集，零用户行为成本）

- 静息心率（resting heart rate）：自主神经系统活动指标，与恢复状态直接相关
- HRV（heart rate variability SDNN）：恢复/压力的最强生物标志物，与深度睡眠和失眠事件直接相关
- 呼吸频率（respiratory rate）：睡眠呼吸质量指标
- 血氧（SpO2）：睡眠呼吸暂停筛查

#### 活动（Apple Watch / iPhone 自动采集）

- 步数（step count）：日运动量指标，与深度睡眠正相关

#### 体测（外部设备自动采集）

- 体重（body mass）：WiFi 智能秤，长期趋势跟踪
- 血糖（blood glucose）：CGM 连续血糖监测，高血糖→频繁起夜
- 血压（blood pressure）：蓝牙血压计，收缩压/舒张压

#### 生活方式（手动记录，通过 Siri / Apple Health）

- 咖啡因（dietary caffeine）：每杯约 150mg（14g 浅烘 double shot），Siri 记录
- 酒精（dietary alcohol）：Siri 记录，酒精破坏后半夜睡眠架构

## 非目标

- GUI-first 产品
- App Store 上架
- 直接从 Python 调 HealthKit
- 实时生理监控或告警
- 医疗诊断、治疗建议、风险评分
- FastAPI 负责 analytics（analytics 由 CLI 负责）
- 饮水量、营养日志、详细运动记录（Phase 2 暂不接入）
- 解释层、建议层、告警层（由 AI 分析完成，不固化到 CLI）

## 成功标准

- `doctor config` 可以稳定输出当前配置与路径状态
- `db init` 可以创建本地 SQLite 数据库与完整表结构
- FastAPI `POST /ingest/sleep` 能接收 iOS 端发送的睡眠数据并幂等写入
- FastAPI `POST /ingest/{data_type}` 能接收所有 Phase 2 数据类型并幂等写入
- FastAPI `GET /ingest/{data_type}` 能查询已入库数据（支持过滤）
- FastAPI Swagger UI (`/docs`) 对 AI 足够自描述
- iOS app 能读取 30 天所有数据类型并成功 POST 到 FastAPI
- 部分授权拒绝时 iOS app 不崩溃，优雅降级导出已授权类别
- 默认 `pytest` 通过，所有 integration tests 使用临时数据库
- iOS `xcodebuild` 编译通过，tests 通过
- CLI 在 FastAPI 挂掉时仍能正常查询已有数据
