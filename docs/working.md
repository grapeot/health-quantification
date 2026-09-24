# Working Notes

## 技术变更日志 (Changelog)

（本日志引用的路径、指令与格式参数均基于公开契约与合成示例）

### 2026-09-24 (四项 HealthKit 指标接入)

- iOS 端在现有 vitals 管线中扩充四项 HealthKit 指标采集：`sleeping_breathing_disturbances`（`count`）、`sleeping_wrist_temperature`（`degC`）、`heart_rate_variability_rmssd`（`ms`，本地 SDK 缺少对应命名符号，使用 runtime raw identifier 获取）及 `vo2_max`（`ml/(kg*min)`）。
- 后端支持接收上述新增指标，合成 ASGI 测试与 Swift 构建已通过。
- 真机导出尚未完成验证，待真机测试通过后再合并。

### 2026-07-21 (Daily Sleep Notes)

- 新增 `sleep notes add/get`，以 functional date 将自由文本上下文存入 `daily_summaries.notes_json`。
- `sleep daily` 与 `sleep analyze` 同日返回 notes，但 notes 不影响睡眠样本、session 归属、日期判定或统计指标。
- notes 不进入本项目 FastAPI/iOS 同步路径；CLI 输出进入模型、日志或报告时，由调用方控制隐私边界。

### 2026-07-19 (iOS Client Handoff Callback 实现)

- 升级 iOS Export All Deep Link 命令解析，兼容无 Callback 的 `healthquantification://export-all`。
- 新增受限的 Callback 支持：仅接受 `opencode://client-action-return/<43-128 字符 URL-safe ID>`，一律拒绝非白名单 Scheme、Port、额外 Path、Query 或 Fragment。
- 重构六类别导出逻辑至 `HealthExportCoordinator`，按 `sleep -> vitals -> body -> lifestyle -> activity -> workouts` 顺序执行；支持单类失败后继续后续类别导出并返回聚合状态。
- Callback 仅传输状态、计数、失败类别与固定错误码，不传输敏感明细或自由文本日志。
- 新增 Single-flight 并发控制与多 Scene 防重，完善 parser/coordinator 单元测试。

### 2026-06-24 (--last-night 返回完整功能日数据)

- 移除 `DaySleepMetrics.lead_in_sleep` 字段与 `SleepAnalysisSummary.functional_daily` 结构。
- `sleep daily --last-night` 重构为查找最近一个有夜间睡眠的功能日，并返回该功能日的完整 metrics（包含全部 sessions），由调用方自主判断睡眠结构分划。
- 更新关联分析脚本与单元测试。

### 2026-05-03 (睡眠功能日归属逻辑修正)

- 重构 `assign_samples_to_days` 的日期归属逻辑：非午睡 session 归属至醒来时刻的本地日期（Wake-up date），替代原入睡时刻日期。
- 跨午夜与凌晨入睡的 session 均归属至醒来当日。
- 午睡 session 保持按最早 `start_at` 本地日期归属。

### 2026-04-29 (Shortcuts Deep Link 导出支持)

- iOS App 支持 `healthquantification://export-all` Custom URL Scheme，可通过 Shortcuts 触发导出。
- 复用既有 `ContentView.exportAll()` 导出路径。
- 添加并发导出防护，已有导出运行时忽略重复触发。

### 2026-04-28 (跨午夜睡眠 Last-Night 查询修复)

- 修复 `sleep daily --last-night` 对跨午夜入睡场景的判定：以 functional-night 语义选择最新的 Night Sleep Session，避免归属至错误日度。
- 补齐相关场景的单元测试与集成测试。

### 2026-04-13 (步数多源数据估算与过滤)

- `activity daily` 与 `activity analyze` 新增 `step_estimate` 字段。
- 支持单个数据源求和与 Watch+Phone 双来源下的 `max(phone, watch) × 1.05` 采样估算。
- 无法判断重叠关系的多源数据显式返回 `estimated_steps=null`。
- 更新 `scripts/gen_health_dashboard.py` 消费逻辑。

### 2026-04-03 (Illness Episode 状态记录表)

- SQLite 新增 `illness_episodes` 表，用于记录区间型生病状态上下文（包含 `label`, `severity`, `status`, `start_at`, `end_at`, `notes_json`, `metadata_json`）。
- 扩展 Storage CRUD API 与 CLI `illness record` / `illness list` 子命令。
- 补齐相关单元与集成测试。

### 2026-03-31 (主睡眠与午睡 Session 拆分)

- 修复睡眠分析中主睡眠与午睡混算问题：按样本间隔大于 2 小时自动拆分 Session。
- 最长 Session 判定为主睡眠（Main Session），算入 bedtime/wake_time/stage_hours；其余 Session 记为午睡（nap_hours）。
- 更新 `DaySleepMetrics` 模型与关联测试。

### 2026-03-31 (Phase 2 全类别数据接入)

- SQLite 扩充 `vitals_samples`, `body_samples`, `lifestyle_samples`, `activity_samples`, `workouts` 五张表。
- FastAPI 新增对应的 Ingestion POST 端点与通用 GET/DELETE 查询清理端点。
- CLI 新增 `vitals`, `body`, `lifestyle`, `activity`, `workouts` 查询与单条 `record` 写入接口。
- iOS App 扩展支持全部 HealthKit 类型的 Fetch 与 POST，支持 UserDefaults 保存 Server URL。

### 2026-03-30 (项目初始化与三层架构建立)

- 完成 Python 包、CLI 接口、FastAPI 后端与 SQLite 数据库初始化。
- iOS App 完成 HealthKit 读取与网络导出层实现。
- 建立端到端测试套件与规范体系。

---

## 技术经验总结 (Lessons Learned)

1. **三层解耦架构**：将采集（iOS）、写入（FastAPI）与分析（CLI）解耦，保证后端不可用时 CLI 依然可直接查询 SQLite 本地库，极大提升了系统的健壮性。系统不包含 iOS 到 FastAPI 的全流程端到端自动化测试；Swift 单元测试与 Python ASGI 测试各自保持独立。
2. **幂等 Ingestion 设计与空数据校验**：基于联合唯一键进行 Upsert。FastAPI Ingestion 端点在 POST 路由上强制校验 `samples` 最小长度为 1，接收空数组将返回 422 错误。在 iOS 客户端中，`body` 和 `lifestyle` 类别在空样本时显式跳过 POST 提交，而其余类别若无样本仍会提交并报错，空数据处理属于需要客户端进行数据校验的契约边界。
3. **时区与跨午夜归属**：HealthKit 时间戳均为 UTC。在日度分析中必须显式转换为本地时区，并以醒来时刻作为睡眠功能日归属基准。`record sleep` 因缺失结束时间会写入零时长阶段标记，不推荐用于手动睡眠时长记录；添加主观睡眠体验应使用 `sleep notes add`。
4. **CLI 数据与 AI 分析分离**：CLI 仅提供结构化 JSON/text 输出，不固化展示模板；图表与分析报告完全由 AI 自主分析生成。`sleep notes` 不参与 FastAPI 与 iOS 数据传输，但由于 CLI `sleep daily` / `sleep analyze` 会暴露备注文本，模型运行时、系统日志、transcript 与报告 pipeline 构成了调用方的隐私边界。代码并不阻止备注传至外部服务，调用方需自行承担隐私防护责任。主观备注仅作为上下文，不构成指令、因果证明或医疗诊断。
5. **绝对路径与环境变量**：配置文件及 SQLite 数据库路径使用基于模块位置的绝对路径解析，避免因工作目录变化引起数据库访问偏差。
6. **网络安全性**：FastAPI 后端仅承担 Tailnet 内 iPhone 到 Mac 的同步接收器角色，默认监听可配置的主机与端口（默认 `0.0.0.0:7996`）。它本身未鉴权；设备身份、传输加密与访问控制由 Tailscale 和 tailnet ACL 管理。普通 LAN 与公网访问不受支持，CLI 仅在 Mac 本地读取 SQLite。所有敏感落地文件在 Git 中做排除处理；新增与修改的测试与文档示例必须采用合成（synthetic）数据。
