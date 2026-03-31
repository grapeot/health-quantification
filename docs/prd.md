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
7. 幂等 ingestion 协议（重复提交不产生重复数据）
8. 完整测试覆盖（unit + integration + UI tests）
9. pm2 进程管理 FastAPI 后端
10. PRD / RFC / test / working / skill 文档

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
- `health_quantification.storage`：SQLite 连接、schema 初始化、sleep_samples CRUD
- `health_quantification.models`：核心 observation / daily summary 数据结构
- `health_quantification.server`：FastAPI ingestion server（POST /ingest/sleep, GET, DELETE）
- `health_quantification.analysis.daily_summary`：最小日级摘要逻辑
- `health_quantification.artifacts.report`：PNG 图表辅助函数（AI 按需调用）
- `health_quantification.cli`：薄 CLI（data-only，不碰 ingestion 和报告生成）
- `scripts/health_quant`：CLI wrapper
- `scripts/start_backend.sh`：FastAPI 启动 wrapper
- `ecosystem.config.cjs`：pm2 配置

### iOS 侧

- `HealthQuantificationIOS` target：HealthKit 读取 + POST 到 FastAPI（端口 7996）
- 包含 Run Doctor / Request Sleep Access / Export Sleep 按钮
- 支持配置 server URL（默认 `http://localhost:7996`）
- ATS exception 白名单 `localhost`（自定义 Info.plist）
- Unit tests、UI tests

## 优先收集的数据

- 睡眠：duration、sleep stages、bedtime、wake time、sleep day window（Phase 1 已实现）
- 恢复与生命体征：resting HR、HRV、respiratory rate、wrist temperature deviation、SpO2（Phase 2）
- 活动：steps、distance、active energy、basal energy、workouts（Phase 2）
- 体重与体成分：body mass、body fat、lean mass（Phase 2）
- 代谢：blood glucose 与相关时间序列特征（Phase 2）
- 上下文事件：caffeine、alcohol、illness、travel、manual notes（Phase 2）

## 非目标

- GUI-first 产品
- App Store 上架
- 直接从 Python 调 HealthKit
- 实时生理监控或告警
- 医疗诊断、治疗建议、风险评分
- FastAPI 负责 analytics（analytics 由 CLI 负责）
- 在 phase 1 中接入完整 CGM / 血压 / 营养 logging 工作流

## 成功标准

- `doctor config` 可以稳定输出当前配置与路径状态
- `db init` 可以创建本地 SQLite 数据库与完整表结构
- FastAPI `POST /ingest/sleep` 能接收 iOS 端发送的睡眠数据并幂等写入
- FastAPI `GET /ingest/sleep` 能查询已入库的睡眠数据
- FastAPI Swagger UI (`/docs`) 对 AI 足够自描述
- iOS app 能读取 30 天睡眠数据并成功 POST 到 FastAPI
- 默认 `pytest` 通过，所有 integration tests 使用临时数据库
- iOS `xcodebuild` 编译通过，tests 通过
- CLI 在 FastAPI 挂掉时仍能正常查询已有数据
