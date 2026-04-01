# Working Notes

## Changelog

### 2026-04-01 (Sleep date assignment fix, bedtime/wake_time cross-midnight fix, --last-night CLI flag)

- **修复 `assign_samples_to_days` 的日期归属逻辑**：从 per-sample `end_at` 本地日期改为 session-based 归属。每个 session 归到其最早 `start_at` 的本地日期（bedtime 日期），避免跨午夜睡眠被劈成两半分到两天。例如 22:00 入睡 07:00 醒来的睡眠，整个 session 归到 22:00 那天。
- **修复 `compute_day_metrics` 中 bedtime/wake_time 的跨午夜 bug**：bedtime 只从 start_hour >= 16 的 sample 取（傍晚/晚上），wake_time 只从 start_hour <= 12 的 sample 取（清晨/上午），避免午夜后的 sample 用 `time() < time()` 比较覆盖 evening bedtime。凌晨入睡的场景 fallback 到 session 最早 start_at。
- **新增 `sleep daily --last-night` CLI flag**：自动映射到昨天的日期（因为跨午夜睡眠归到 bedtime 日期）。`--date` 不再 required，不传默认今天。
- 新增 2 个测试（`test_assign_samples_to_days_cross_midnight`、`test_assign_samples_to_days_after_midnight_session`），更新 1 个 fixture（`test_compute_analysis_summary`），总测试数 93。
- 更新 skill 文件：睡眠日期归属规则、`--last-night` 用法、bedtime/wake_time 计算逻辑说明。

### 2026-03-31 (Sleep nap separation, absolute DB path)

### 2026-03-31 (Workout tracking, continuous heart rate, active energy)

- 新增 workouts 表和 POST /ingest/workouts endpoint：记录 Apple Watch structured workouts（类型、时长、卡路里、距离）。
- 新增连续心率（heart_rate）和活动消耗（active_energy_burned）到 vitals 数据类型，通过现有 /ingest/vitals endpoint 接入。
- iOS 端新增 HKWorkoutQuery 读取 workouts，扩展 vitals 查询支持 heartRate 和 activeEnergyBurned。
- 新增 WorkoutRecord Swift 模型，IngestClient 新增 workouts POST。
- CLI 新增 workouts analyze/daily 子命令。
- 新增测试覆盖：workout 模型验证、endpoint 幂等性、CLI smoke test。总测试数 91。
- Python 91 tests pass，iOS xcodebuild build succeeded。

- 修复 config.py 使用相对路径 `data/health_quantification.db` 的隐患：改为基于 `__file__` 解析项目根目录的绝对路径，CLI 从任何 cwd 运行都指向同一个 DB。
- 修复睡眠分析中主睡眠与午睡混算的 bug：`compute_day_metrics` 现在先将同一天的 samples 按时间 gap（>2h）拆分为多个 session，取 asleep 时间最长的作为主睡眠，其余归为午睡。
- `DaySleepMetrics` 新增 `nap_hours` 字段，bedtime/wake_time/stage_hours 只从主睡眠计算，`total_sleep_hours` 包含主睡眠+午睡。
- 新增 `_split_into_sessions()` 和 `_session_stage_hours()` / `_session_asleep_hours()` 辅助函数。
- 新增 5 个测试（主睡眠+午睡、带 stage 的午睡、多次午睡、纯午睡日、短暂间隔不误判为午睡），总测试数 81。
- pm2 后端已重启，PR #1 已 merge（absolute DB path fix）。

### 2026-03-31 (Phase 3: DB as primary storage, multi-source, AI recording)

- 架构转变：SQLite 从 HealthKit 镜像升级为唯一事实来源（single source of truth）
- 新增 CLI `record` 子命令：支持 AI/手动写入单条数据到所有表（lifestyle, body, vitals, activity, sleep）
- storage.py 新增 `record_sample()` 函数：自动生成 source_id、默认 source=ai_manual、默认时间=当前 UTC
- 新增 15 个测试（8 unit + 7 integration），总测试数 76，全部通过
- PRD/RFC 更新：多数据源架构、AI 手动记录、知识库（食品/饮料咖啡因含量）、source 字段约定
- Skill file 全面更新：AI 记录工作流、知识库、record CLI 用法、用户分析偏好（ML 背景，精确统计语言）
- 首次 AI 记录：墨西哥可乐 500ml 48mg 咖啡因（2026-03-31 12:00 PT）
- 综合健康分析报告（多 agent 集思广益）：docs/reports/health_synthesis_report_2026-03-31.md（gitignored）

### 2026-03-31 (ATS fix & server update)

- ATS 改用 `NSAllowsArbitraryLoads` 替代 `NSExceptionDomains`，因为 iOS 不支持 `.` 开头的通配子域名（`.ts.net` 无效）。
- 给 export status 区域加 `.textSelection(.enabled)`，支持长按复制错误信息。
- 远端 server 通过 pm2 restart 更新，`db init` 创建了 Phase 2 四张新表（vitals/body/lifestyle/activity）。
- Skill file 更新：反映 Phase 2 全部数据类型和 CLI 子命令。
- Security review 通过：所有待 push 的 commit（`7814997..213de0e`）中无密钥、无 Tailscale 内网 IP/域名、无个人数据。
- 修复空 samples 导致 422：body/lifestyle 无数据时跳过 POST，显示 "no data"。
- 新增测试覆盖：Python 端 empty samples 422、invalid data_type 422（61 tests pass）；iOS 端 normalizedStageValue（14 tests pass）。
- 更新 README、PRD、RFC、skill file 反映 Phase 2 全部数据类型和 iOS 简化 UI。
- 综合健康分析：30 天数据（sleep 812、vitals 1884、activity 2561 samples），发现步数-睡眠显著正相关（r=0.476），睡眠严重不足（日均 5.6h，仅 17% 天达标），HRV 偏低（48ms）。报告、数据、图表分别输出到 docs/reports/ 和 docs/assets/。
- Skill file 补充分析经验：交叉相关性分析优先于单维度统计、步数需要自行聚合、HRV 受短睡眠日数据缺失影响。
- 新增测试覆盖：Python 端 empty samples 422、invalid data_type 422（61 tests pass）；iOS 端 normalizedStageValue（14 tests pass）。
- 更新 README、PRD、RFC、skill file 反映 Phase 2 全部数据类型和 iOS 简化 UI。

### 2026-03-31 (UI simplification & partial auth handling)

- UI 简化：移除 "Export Sleep (30 days)" 按钮，只保留一个 "Export All (30 days)" 按钮；更新副标题为 "Export HealthKit data to your backend"。
- 移除 `requestSleepAccess()` wrapper 方法，统一使用 `requestHealthAccess()`。
- 修复 `fetchBodySamples()` 中的血压授权 bug：与 `readTypesForExport()` 相同的问题——不能对 `HKCorrelationType` 请求授权，改为请求 `bloodPressureSystolic` 和 `bloodPressureDiastolic` 两个 quantity type。
- 每个 `fetch*Samples()` 方法现在优雅处理部分授权拒绝：捕获 `HealthKitServiceError.authorizationDenied`，返回空数组并记录日志，而不是抛出异常。
- `exportAll()` 改为按类别独立 try/catch：某个类别失败不影响其他类别继续导出；全部失败显示红色，部分失败显示橙色，全部成功显示绿色。
- UI 测试 `testDoctorAndRequestSleepAccessFlow` 重命名为 `testDoctorAndRequestHealthAccessFlow`，匹配新的 accessibility identifier。
- xcodebuild build + test 全部通过（7 unit tests + 6 UI tests）。

### 2026-03-31 (Phase 2 iOS export implementation)

- 扩展 `HealthQuantificationIOS` 的 `HealthKitService`：在保留 sleep export 流程的前提下，新增 vitals、body、lifestyle、activity 四类 HealthKit 读取逻辑，并把授权范围扩展到 RFC 要求的全部类型。
- 新增 Swift 数据模型 `VitalsSampleRecord`、`BodySampleRecord`、`LifestyleSampleRecord`、`ActivitySampleRecord`，JSON 字段名与 `docs/rfc.md` 一致；`IngestEnvelope` 改为通用 envelope，继续复用现有 sleep 序列化模式。
- 扩展 `IngestClient`：新增 POST `/ingest/vitals`、`/ingest/body`、`/ingest/lifestyle`、`/ingest/activity`，沿用现有 `URLRequest + JSONEncoder + JSONDecoder` 模式；sleep endpoint 保持不变。
- `ContentView` 保留原有 `Export Sleep (30 days)` 按钮，同时新增 `Export All (30 days)`，按类别顺序读取并分别 POST 到五个 ingestion endpoint。
- 血压按 RFC 通过 `HKCorrelationType.bloodPressure` 读取，拆成 `blood_pressure_systolic` 和 `blood_pressure_diastolic` 两条记录，并共享同一个 `source_id`（correlation UUID）。
- 验证计划：对改动过的 Swift 文件运行 `lsp_diagnostics`，再跑 `xcodebuild -scheme HealthQuantificationIOS -showdestinations` 和 iOS build，确认工程可编译。

### 2026-03-31 (Phase 2 backend implementation)

- 实现 Phase 2 SQLite schema：在 `storage.py` 初始化流程中加入 `vitals_samples`、`body_samples`、`lifestyle_samples`、`activity_samples` 四张表，并补齐对应的 upsert/query/delete 函数。
- 扩展 FastAPI ingestion server：新增 POST `/ingest/vitals`、`/ingest/body`、`/ingest/lifestyle`、`/ingest/activity`，并用通用 GET/DELETE `/ingest/{data_type}` 覆盖 sleep + Phase 2 全部数据类型，支持 `from_date`、`to_date`、`source`、`metric_type` 过滤。
- 扩展 CLI：新增 `vitals`、`body`、`lifestyle`、`activity` 顶层子命令，均支持 `analyze --days N --metric TYPE --format json|text` 和 `daily --date DATE --format json|text`；Phase 2 分析实现为按天聚合的基础统计（count、avg、min、max、std）。
- 扩展 `models.py` 和新增 `analysis/metrics.py`，为 Phase 2 提供通用 numeric stats / daily summary 数据结构与计算逻辑，同时保持 `analysis/sleep.py` 不变。
- 测试补齐：新增 Phase 2 Pydantic 模型验证、HTTP endpoint 幂等性与过滤测试、CLI smoke test；另外修正一个既有 sleep analysis fixture，使其符合项目当前基于 local `end_at` 归属日期的规则。
- 验证结果：修改文件的 `lsp_diagnostics` 已跑过且无 error；在项目 `.venv` 中执行 `source .venv/bin/activate && pytest`，51 个测试全部通过。

### 2026-03-31 (Phase 2 kickoff)

- 完成 sleep comprehensive analysis 的交叉分析：交叉比对 Apple Watch 睡眠数据、每日活动记录（daily_records/2026.md）和生活录音摘要（life_record/），结合用户补充上下文（6mg 褪黑素、娃感冒夜醒、频繁起夜、3 杯拿铁/天）。
- 发现睡眠异常的核心模式：21:00 后工程调试是 #1 睡眠杀手，多项目并行是 #2，缺乏睡前过渡仪式是 #3。
- 整体重写报告为连贯文档（`sleep_comprehensive_analysis_2026-03-31.md`），发布到 Google Docs 并插入 7 张 PNG 图表。
- 调研个人放松方式：从 90 天生活记录中提取休闲活动画像，发现用户"大脑没有 off switch"，建议无屏幕手工活动（莳绘/写字）、游戏时间前移到 19:00-21:00、有目的户外步行、decaf 咖啡仪式。
- 咖啡因计算：14g 浅烘 double shot ≈ 150mg 咖啡因（Arabica 1.4% × 14g × 80% 萃取率），3 杯/天 ≈ 450mg，接近 FDA 400mg 上限。
- iOS localStorage：确认 server URL 已通过 `@AppStorage("serverURL")` 持久化（UserDefaults），无需代码改动。xcodebuild 编译和测试通过。
- **Phase 2 规划**：更新 PRD 和 RFC，接入全部新数据类型：
  - 生命体征（Apple Watch 自动）：静息心率、HRV、呼吸频率、血氧
  - 活动（Apple Watch 自动）：步数
  - 体测（外部设备）：体重（WiFi 秤）、血糖（CGM）、血压（蓝牙血压计）
  - 生活方式（Siri 手动）：咖啡因（~150mg/杯）、酒精
  - 新增 4 张 SQLite 表（vitals_samples, body_samples, lifestyle_samples, activity_samples）
  - 新增 4 个 ingestion endpoint（POST /ingest/{vitals,body,lifestyle,activity}）
  - 新增 CLI 子命令（vitals, body, lifestyle, activity 的 analyze/daily）

### 2026-03-30

- 完成首次 comprehensive sleep analysis：28 个过夜夜晚的 7 维分析（duration、stages、efficiency、bedtime/waketime、weekly pattern、sleep debt、data quality），生成 7 张 PNG 图表和 1 份 MD 报告，输出到 `docs/reports/` 和 `docs/assets/`。
- 架构调整：移除 CLI 的 `report` 子命令和 `sleep --report` flag，移除 `artifacts/report.py` 中的 hardcoded MD 模板函数。CLI 改为纯数据接口，分析和报告生成完全交给 AI。
- `artifacts/report.py` 中的图表辅助函数从 SVG 迁移到 PNG（matplotlib），因为 SVG 在 Markdown 预览中无法渲染。
- 新增 `scripts/gen_charts.py` 作为一次性图表生成脚本（7 种图表类型），供 AI 参考和复用。
- 添加 `matplotlib>=3.10` 到 dev dependencies。
- 更新 PRD、RFC、AGENTS.md、README.md、skill 文件，统一反映"CLI 只提供数据，AI 做分析"的架构原则。
- 19 pytest 全部通过。

### 2026-03-30 (earlier)

- 初始化 `health_quantification` 项目骨架、文档、Python package 和 wrapper 脚本。
- 明确 phase 1 采用 Python-first 架构，native Apple Health exporter 只保留为未来 adapter 边界。
- 增加最小 CLI：`doctor config`、`db init`、`summary daily`、`artifact daily-card`。
- 增加 project-local skill，面向 AI 与人类描述项目目标、合同和边界。
- 将 `native/apple_health_exporter/` 升级为真实 Swift spike，增加 `doctor` 与 `export sleep` 命令、entitlements 占位、Info.plist 和 build/run 脚本。
- 在本机完成 Swift build 与 `doctor` 验证；当前结果是可编译，但 `HKHealthStore.isHealthDataAvailable()` 返回 `false`。
- 增加最薄 macOS `.app` shell，并验证 bundle、entitlement、开发证书签名与 LaunchServices 启动链路。
- 系统日志确认 `HealthKit` entitlement 触发了 provisioning profile 要求；仅靠手工 `codesign` 不足，当前错误是 `No matching profile found`。
- 把 HealthKit 验证界面迁入 Xcode 新建的 `HealthQuantification` macOS App 工程，并通过 `xcodebuild -allowProvisioningUpdates build` 成功构建。
- 当前 Xcode 自动签名拿到的是 wildcard 的 `Mac Team Provisioning Profile: *`，最终 signed app 里仍然没有 `com.apple.developer.healthkit`；下一步需要在 Xcode UI 里显式添加 HealthKit capability，让 profile 升级为带该能力的显式配置。
- 新增 `HealthQuantificationIOS` target，并将 HealthKit 诊断界面迁入 iOS app。当前 iOS target 已成功编译，build 阶段生成的 entitlements 明确包含 `com.apple.developer.healthkit`。
- 这确认了最现实的 phase 1 采集端应该是 iOS，而不是纯 macOS target。下一步应在真机上点一次授权，观察 `healthDataAvailable` 和 `requestSleepAccess` 的结果。

### 2026-03-31

- 实现 FastAPI ingestion server（`src/health_quantification/server.py`），包含 POST/GET/DELETE `/ingest/sleep` 和 `/health` 四个端点，Pydantic 模型完整，Swagger UI 自描述。
- 增加 `sleep_samples` 表和 `upsert_sleep_samples()`、`query_sleep_samples()`、`delete_sleep_samples()` 到 `storage.py`，使用 `(source, source_id)` 做幂等键。
- 增加 FastAPI unit tests（模型验证）和 integration tests（HTTP 合同、幂等性、日期过滤、清理），共 12 个 pytest 全部通过。
- 增加 `scripts/start_backend.sh` 和 `ecosystem.config.cjs`，通过 pm2 管理 FastAPI 进程，默认监听 `0.0.0.0:7996`（通过 Tailscale 内网通信）。
- 更新 PRD 和 RFC，明确三层分离架构：采集层（iOS）、写入层（FastAPI）、分析层（CLI）。
- 修改 iOS `HealthQuantificationIOS` target：增加 `IngestClient`、`SleepSampleRecord`、`IngestEnvelope`，UI 增加 server URL 输入（默认 `http://localhost:7996`）和 Export Sleep (30 days) 按钮。
- iOS target 增加 unit tests（JSON 编解码、stage 映射）、UI tests（doctor 流程），xcodebuild 和 xcodebuild test 均通过。
- FastAPI 已通过 pm2 启动并验证：`/health` 返回 200，`/docs` Swagger UI 可用。
- iOS 真机验证成功：`healthDataAvailable=true`，`requestSleepAccess` 返回 `granted`。
- 修复 pbxproj config ID 不匹配导致 iOS build 找不到目标平台的问题。macOS target 的 Debug/Release config block 被错误引用为 iOS target 的 config，导致 `SUPPORTED_PLATFORMS=macosx` 覆盖了 iOS target 级别的 `SDKROOT=iphoneos`。
- 修复 ATS exception：`INFOPLIST_KEY_NSAppTransportSecurity` build setting 方式无法生成有效的 `NSAppTransportSecurity` dict，改用自定义 `Info.plist` 配置 `NSExceptionDomains` 白名单 `localhost`。通过 `PBXFileSystemSynchronizedBuildFileExceptionSet` 排除 Info.plist 不被 auto-include 为资源。
- 清理 git：移除 `.build/`、`data/health_quantification.db`、xcuserdata 等已 track 的构建产物。分 5 个 commit 整理历史。
- iOS 真机端到端验证成功：export 813 samples（30 天），全部来自 Yan's Apple Watch，stage 分布合理（core 384, awake 158, deep 156, rem 103, unspecified 12），0 重复。
- 数据特点：所有时间戳为 UTC（需转 PDT -7 做分析）；3/7 无数据（未佩戴）；3/29 仅 1 条午睡（14:12-15:12 PDT）。
- Housekeeping：删除 native/ 目录（macOS HealthKit 探索结论：iOS 是正确宿主）和 4 个过时脚本。更新 AGENTS.md、README.md、PRD、RFC、skill 文件。修正默认端口从 7980 到 7996。
- 新增 analysis/sleep.py：per-day 和 multi-day 睡眠指标计算（total sleep、deep/core/REM 分解、efficiency、nap 检测）。使用 end-time UTC→PDT 分配处理跨午夜睡眠。
- CLI 新增 `sleep analyze --days N` 和 `sleep daily --date` 子命令，支持 json/text 输出。19 pytest 通过。
- 跨午夜睡眠分配：使用 sample 的 end_at（而非 start_at）来确定归属日期，避免夜间睡眠被拆分到两天。nap 检测使用 has_overnight + total_sleep < 3h 双条件。
- bedtime/wake_time 计算：已通过 session segmentation 修复。同一天的 samples 按时间 gap（>2h）拆分为多个 session，主睡眠用于 bedtime/wake_time，午睡单独报告。
- 替换 SVG daily card 为 MD 报告系统。报告输出到 `docs/reports/`（.gitignore 排除），图表输出到 `docs/assets/`（SVG）。CLI 新增 `report daily` 和 `report analyze` 子命令，AI 自由决定文件名。
- Skill 通过 symlink 注册到 `rules/skills/health_quantification.md`，从 workspace 根目录也可通过自然语言调用。

## Lessons Learned

- Apple 侧权限与 HealthKit 读取能力应被隔离在最薄 native adapter 中，避免把整个项目锁进原生 GUI 形态。
- 睡眠与恢复指标跨午夜，日级 summary 不能反向定义源数据模型；原始 observation 与 interval 才是事实层。
- 对 AI-first 健康项目来说，稳定 contract 比早期 feature richness 更重要。先把 CLI、schema 和 artifact 路径固定下来，后续接入数据源的成本更低。
- 当前 SwiftPM executable 已经证明 `HealthKit` 可以被编译和链接；下一阶段的问题是运行时可用性，而不是语法或依赖管理。
- 对带 `com.apple.developer.healthkit` 的 macOS app shell，Xcode 自动签名与匹配 provisioning profile 很可能是必需条件。手工 bundle + 手工 `codesign` 已经越过了编译和结构验证，但卡在 profile 层。
- 即使工程里手动写入 entitlements 文件和 build setting，最终 signed app 是否真的拿到该 capability，仍由 Xcode capability 配置与 provisioning profile 决定。判断标准要看 signed app 的最终 entitlements，而不是只看工程文件。
- iOS target 明显更顺：Xcode 自动签名能够把 `HealthKit` capability 真正带进 build 产物。对 Apple Health 的 phase 1 数据采集，不应把 macOS 作为首选宿主。
- `NSHealthShareUsageDescription` 必须在 iOS target 的 build settings 里显式设置（`INFOPLIST_KEY_NSHealthShareUsageDescription`），仅靠 entitlements 文件不够；否则请求授权时直接 crash。
- 三层分离（采集/写入/分析）让各层可以独立开发和部署。CLI 不依赖 FastAPI 存活就能查询已有数据，FastAPI 挂了也不影响 CLI。
- 幂等 ingestion 用 `(source, source_id)` 做 upsert 键，重复导出不会产生重复数据，这对 cron / 手动重跑都很重要。
- `INFOPLIST_KEY_NSAppTransportSecurity = YES` 这种 build setting 写法无法生成有效的 ATS exception。Xcode 会把值设成布尔 `YES` 而不是 dict。正确做法是创建自定义 `Info.plist`，用 `NSExceptionDomains` 精确白名单目标域名，然后在 build settings 里设 `INFOPLIST_FILE` 指向它。
- 使用 `PBXFileSystemSynchronizedRootGroup` 时，自定义 `Info.plist` 会被自动 include 为资源导致 "Multiple commands produce Info.plist" 错误。需要用 `PBXFileSystemSynchronizedBuildFileExceptionSet` 的 `membershipExceptions` 排除它。
- HealthKit 导出的睡眠时间戳全部是 UTC。做日级分析时必须转换到用户时区（PDT/PST），否则跨午夜的数据会被错误地分到两天。
- Apple Watch 午睡追踪精度低，通常只产生 1 条 `asleep_unspecified` stage，不会细分 core/deep/rem。
- CLI 生成 hardcoded 报告是反模式。用户的分析需求高度个性化（对比周期、异常检测、因果推理），这些不可能被预编码进 Python 模板。正确做法是 CLI 只提供数据接口（JSON），AI 自行决定分析角度和报告格式。可视化用 PNG 而非 SVG，因为大部分 Markdown 渲染器不支持 SVG 内嵌。
