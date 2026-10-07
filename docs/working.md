# Working Notes

## 技术变更日志 (Changelog)

（本日志引用的路径、指令与格式参数均基于公开契约与合成示例）

### 2026-10-07 (主屏长按立即传输)

- 新增主屏幕静态快捷操作 Transfer Now。它使用应用内已保存的服务器地址导出最近 30 天样本，等同于无 callback 的 `healthquantification://export-all`，不接收服务器地址、回调或任何调用方参数。
- 冷启动只在 scene 连接回调接收一次。应用已在后台时进入同一条导出路径。
- 导出状态放在进程内共享对象里，多个窗口共用这一份。已有导出进行中时不会再启动一次。这是代码结构和一条单元测试，没有做 iPad 界面测试。
- 测试用 server URL 覆盖只编译进模拟器 Debug，不进入真机安装包。只在已保存地址与覆盖值不同时写入，不会在每次启动无条件重写。
- 长按的冷启动和热启动只在 iOS 模拟器主屏幕快捷菜单上用 XCUITest 各跑过一次。没有在真机上验证长按。真机只做了原地安装。

### 2026-10-06: End-to-End Export and Ingest Optimization

- Cached `ISO8601DateFormatter` per thread across export categories, preserving its existing UTC whole-second output and near-second-boundary rounding. Boundary and concurrent reuse tests guard against changing timestamp semantics.
- Replaced full-row materialization for counts with source-scoped SQL `COUNT(*)` in six non-ECG ingest endpoints. Added `--compare-summary` to report timing improvements and workload drift while rejecting mismatched build configuration, warm/cold mode and warmup count.
- Same-device Release benchmarks (one discarded warmup and five warm runs per batch) improved median export from 9.46 s to 3.05 s, a 3.10x speedup. All seven HealthKit-source tables had matching stored payload checksums and row counts before/after, excluding audit timestamps. All 172 Python tests and 33 XCTest unit tests passed. See `docs/performance.md` for methodology and limitations.

### 2026-10-06: Export Profiling Infrastructure and Real-Device Baseline

- Implemented automated real-device export profiling: host runner (`scripts/ios_profile.py`), strict `profile-export` deep link, opt-in client instrumentation, backend `Server-Timing`, and atomic progress/completion artifacts. See `docs/performance.md`.
- Verified XCTest unit suites and all 170 Python tests; executed Release exports on physical hardware against the configured live backend. Raw artifacts stay in ignored scratch directories.

### 2026-10-04 (体测体成分与腰围接入)

- iOS 采集端 `bodyQuantityConfigurations()` 新增三项 HealthKit 体测类型：`bodyFatPercentage`（`body_fat_percentage`，`%`，按 `.percent()` 取值后乘 100，与 `oxygen_saturation` 同一归一化约定）、`leanBodyMass`（`lean_body_mass`，`kg`）、`waistCircumference`（`waist_circumference`，`cm`）。此前采集端只配了 `bodyMass` 和 `bloodGlucose`，Apple Health 里已有的体成分与腰围数据不会被采集。
- 后端 `BodyMetricType` Literal 放行三个新 metric；存储层 `body_samples` 按 `metric_type` 区分，无需改表。
- 腰围按原始厘米值存，腰高比等派生比值不入库，归分析层。
- 新增 Python 单测 `test_body_ingest_accepts_new_metrics`；`test_phase_2_ingest_requests_reject_unknown_metric_type` 的 body 反例由已合法化的 `body_fat_percentage` 改为 `unknown_body_metric`。Swift `HealthKitServiceTests.testReadAuthorizationIncludesOnlyExportedTypes` 的授权清单同步加入三项。
- 实测 `.venv/bin/python -m pytest -q` 为 167 passed；Swift 在 iPhone 17 Pro 模拟器（iOS 26.5）为 TEST SUCCEEDED。没有写入真实体成分读数或腰围。
- 新增设计文档 `docs/design_body_composition_waist.md`。

### 2026-09-28 (心电图写入不降级与请求边界)

- 同一条已有非空波形时，后续 `query_failed`、空电压或更短 partial 不再覆盖；点数不少于已存 partial 的新 partial，以及新的完整波形，仍可刷新。已存症状不会被后续症状查询失败写成空列表。这是字段级保留，不是整行冻结。
- `ecg export` 在仓库内只接受 resolve 之后仍位于 `data/exports/` 的路径。`data/ecg.json`、指向该位置的 symlink，以及父目录 symlink，都会在写文件前拒绝。仓库外路径仍可写。测试不写入真实 `data/exports/`。
- `GET /ingest/ecg` 的日期边界改为与 CLI 共用 `normalize_ecg_bound`。`YYYY-MM-DD` 是配置时区的本地整日，带偏移的 ISO 时间转 UTC。`ecg list --days` 是从当前时刻往回滚动的窗口，不是本地日历日；`--days 30` 表示现在之前的 30 天。
- `POST /ingest/ecg` 在 JSON 解析前按实际字节拒绝超过 8MB 的请求。声明的 Content-Length 已经超限时先拒绝，不再读正文；缺失或偏小的 Content-Length 仍按读到的字节计数。只作用于这个路径。心电图校验失败只返回字段位置和错误类型。其他 ingest 路径的 422 行为不变。iOS 心电图提交失败只保留状态码，不把服务器响应正文放进错误描述。
- 没有重启正在运行的后端，也没有改表结构。新保护要等人类重启 `health_quant_backend` 之后才在线上生效。重启前旧进程仍按旧代码工作，数据库仍可读。
- 实测 `.venv/bin/python -m pytest -q` 为 157 passed。Swift `HealthQuantificationIOSTests` 在 iPhone 17 模拟器（iOS 26.5）为 29 passed，0 failed。没有读取真实心电图，也没有写入 `data/exports/`。

### 2026-09-28 (HealthKit 心电图读取与入库)

- iOS 读取授权增加 `HKElectrocardiogram`，以及心电图记录可能关联的症状类别。电压用 `HKElectrocardiogramQueryDescriptor` 读取，单位为伏，相对时刻为 `timeSinceSampleStart`，采样频率来自 `samplingFrequency`（赫兹）。官方说明：<https://developer.apple.com/documentation/healthkit/hkelectrocardiogram>、<https://developer.apple.com/documentation/healthkit/hkelectrocardiogramquery>。本机 SDK 将回调式 `HKElectrocardiogramQuery` 标为 Swift 弃用，改用 descriptor。
- `classification` 存为算法分类名和原始值，不是诊断。`symptomsStatus` 只表示用户是否录入症状；症状明细要另做 `predicateForObjectsAssociated(electrocardiogram:)` 查询。查不到关联样本记为 `not_returned`，不能当成没有症状。
- 新表 `ecg_records` 用 `CREATE TABLE IF NOT EXISTS` 加入现有初始化，不改旧表。幂等键是 `(source, source_id)`。同一条已存完整波形时，后续 `unavailable`、`partial`、`query_failed` 或空电压重导不覆盖该行；新的完整波形仍按原 upsert 替换。单条电压失败不中断其它心电图，也不中断睡眠、体征、活动、运动导出。心电图放在导出序列最后。
- 列表和 `GET /ingest/ecg` 不返回电压。电压只走 `GET /ingest/ecg/voltage?source_id=&max_points=` 或 `ecg export` 写文件。CLI 标准输出不打印波形。仓库内导出路径必须在 `data/` 下。
- 空结果不是正常分类，也不是“没有心电图”的证明。HealthKit 拒绝读取时查询也会表现为空。`health_data_unavailable` 与空结果分开。本应用部署目标已覆盖 iOS 14 的心电图类型；模拟器或未授权设备上的空集不能当成已读到心电图。
- 模拟器上跑过 `HealthQuantificationIOSTests`，不是只编译。没有安装到真机，没有重启生产服务，也没有读取真实心电图。要在手机上生效，用同一 bundle ID 原位更新，不删除重装，并在系统健康权限里允许新的心电图读取；后端要在人类重启 `health_quant_backend` 之后才有新路由。重启前可对目标库执行 `db init`，它只补表，不删旧行。
- `ecg list` 的 `YYYY-MM-DD` 按配置时区的本地整日转 UTC。查询比较把时间规范成固定 6 位小数再比，避免整秒 `...59Z` 在 TEXT 序里大于 `...59.999999Z` 而被漏掉，也避免同秒更早的整秒被带小数的起点误纳入。本地当日 `23:59:59` 包含，次日 `00:00:00` 不包含。
- 复核时全量 pytest 为 132 passed，Swift `HealthQuantificationIOSTests` 为 27 passed。日期边界修复后我实测全量 pytest 为 133 passed。Swift 27 由独立复核确认，这次没有改 Swift，没有重跑 `xcodebuild`。

### 2026-09-24 (四项 HealthKit 指标接入)

- iOS 端在现有 vitals 管线中扩充四项 HealthKit 指标采集：`sleeping_breathing_disturbances`（`count`）、`sleeping_wrist_temperature`（`degC`）、`heart_rate_variability_rmssd`（`ms`，本地 SDK 缺少对应命名符号，使用 runtime raw identifier 获取）及 `vo2_max`（`ml/(kg*min)`）。
- 后端支持接收上述新增指标，合成 ASGI 测试与 Swift 构建已通过。
- PR 合并后已完成真机全量导出及本地数据库回读；四项新增 vitals 指标的单位、数量与来源样本 ID 均已核对。
- 移除临时 Type Audit 和 Verify Health Metrics 按钮，权限请求范围收敛到实际导出类型；模拟器单测与 UI 测试通过。使用 `devicectl --payload-url` 在真机触发导出，后端 sleep、vitals、activity、workouts 写入时间均推进；旧的系统授权不会因代码收窄而自动撤销。

### 2026-09-24 (iOS 只读体能诊断工件)

- 新增受限的 `physical-effort` URL 诊断路由与 Mac 探针脚本；app 将样本数、MET 单位和分布摘要原子写入受文件保护的私有缓存 JSON，不传原始样本，也不向后端发送数据。旧工件在后续诊断运行时按 24 小时期限清理。
- 已通过模拟器 URL 解析/工件测试和真机完整构建安装、沙盒 JSON 取回；`--skip-build-install` 向原有 app 进程派发新 URL 并取得另一份对应 `run_id` 的结果。测试产物只保留在 Git 忽略的目录；系统权限弹窗仍需本人确认。

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
