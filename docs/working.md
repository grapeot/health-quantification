# Working Notes

## Changelog

### 2026-03-30

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
- 增加 `scripts/start_backend.sh` 和 `ecosystem.config.cjs`，通过 pm2 管理 FastAPI 进程，默认监听 `0.0.0.0:7996`（通过 Tailscale 域名 `quantum.tail63c3c5.ts.net` 访问）。
- 更新 PRD 和 RFC，明确三层分离架构：采集层（iOS）、写入层（FastAPI）、分析层（CLI）。
- 修改 iOS `HealthQuantificationIOS` target：增加 `IngestClient`、`SleepSampleRecord`、`IngestEnvelope`，UI 增加 server URL 输入（默认 `http://quantum.tail63c3c5.ts.net:7996`）和 Export Sleep (30 days) 按钮。
- iOS target 增加 unit tests（JSON 编解码、stage 映射）、UI tests（doctor 流程），xcodebuild 和 xcodebuild test 均通过。
- FastAPI 已通过 pm2 启动并验证：`/health` 返回 200，`/docs` Swagger UI 可用。
- iOS 真机验证成功：`healthDataAvailable=true`，`requestSleepAccess` 返回 `granted`。
- 修复 pbxproj config ID 不匹配导致 iOS build 找不到目标平台的问题。macOS target 的 Debug/Release config block 被错误引用为 iOS target 的 config，导致 `SUPPORTED_PLATFORMS=macosx` 覆盖了 iOS target 级别的 `SDKROOT=iphoneos`。
- 修复 ATS exception：`INFOPLIST_KEY_NSAppTransportSecurity` build setting 方式无法生成有效的 `NSAppTransportSecurity` dict，改用自定义 `Info.plist` 配置 `NSExceptionDomains` 白名单 `quantum.tail63c3c5.ts.net`。通过 `PBXFileSystemSynchronizedBuildFileExceptionSet` 排除 Info.plist 不被 auto-include 为资源。
- 清理 git：移除 `.build/`、`data/health_quantification.db`、xcuserdata 等已 track 的构建产物。分 5 个 commit 整理历史。
- iOS 真机端到端验证成功：export 813 samples（30 天），全部来自 Yan's Apple Watch，stage 分布合理（core 384, awake 158, deep 156, rem 103, unspecified 12），0 重复。
- 数据特点：所有时间戳为 UTC（需转 PDT -7 做分析）；3/7 无数据（未佩戴）；3/29 仅 1 条午睡（14:12-15:12 PDT）。
- Housekeeping：删除 native/ 目录（macOS HealthKit 探索结论：iOS 是正确宿主）和 4 个过时脚本。更新 AGENTS.md、README.md、PRD、RFC、skill 文件。修正默认端口从 7980 到 7996。
- 新增 analysis/sleep.py：per-day 和 multi-day 睡眠指标计算（total sleep、deep/core/REM 分解、efficiency、nap 检测）。使用 end-time UTC→PDT 分配处理跨午夜睡眠。
- CLI 新增 `sleep analyze --days N` 和 `sleep daily --date` 子命令，支持 json/text 输出。19 pytest 通过。
- 跨午夜睡眠分配：使用 sample 的 end_at（而非 start_at）来确定归属日期，避免夜间睡眠被拆分到两天。nap 检测使用 has_overnight + total_sleep < 3h 双条件。
- bedtime/wake_time 计算存在已知限制：cross-midnight split 导致某些天的 wake_time 不准确，需要 session segmentation 来精确识别主睡眠窗口。
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
