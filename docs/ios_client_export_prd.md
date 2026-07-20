# iOS Client Export PRD

## 结论

Health Quantification iOS 为受信任的 OpenCode iOS client 提供一次受限的 Export All handoff。OpenCode 可以打开 Health Quantification、等待六类 HealthKit 数据同步完成，再通过一次性 callback 回到原任务。用户不再需要手工切换 App、点击导出后重新描述分析目标。

本功能只让 Health Quantification 成为 capability provider。OpenCode 负责模型请求、本地授权、callback identity 和原 session continuation；Health Quantification 继续拥有 HealthKit 权限、Server URL、导出进度和 ingestion 行为。

## 用户场景

当 AI 判断睡眠分析所需数据缺失或过期时，支持 client capability 的 OpenCode iOS 可以发起 `health_quantification.export_all`：

```text
OpenCode 创建一次性 callback
→ 打开 Health Quantification
→ Health Quantification 导出最近 30 天数据
→ callback 回 OpenCode
→ OpenCode 在原 session 继续分析
```

原有手动按钮和 `healthquantification://export-all` deep link 保持可用，不要求 OpenCode 才能导出。

## 产品要求

- 带 callback 的 deep link 必须复用手动 Export All 的同一条六类别导出路径。
- callback 只允许返回 `opencode://client-action-return/<callback-id>`。
- callback ID 必须是 43 至 128 个 URL-safe ASCII 字符；43 个字符可承载无 padding 的 256-bit base64url token。
- callback 结果只包含状态、计数、失败类别和稳定错误码，不包含健康明细、Server URL、日志或自由文本错误。
- sleep、vitals、body、lifestyle、activity、workouts 独立执行；单类失败不能阻止后续类别。
- 已有导出运行时，新的 callback 请求立即返回 `busy`，不能覆盖当前请求或并发导出。
- Server URL 无效时，带 callback 的请求返回 `failed`；手动导出继续在本地 UI 显示错误。
- Health Quantification 不接收 OpenCode session ID、host、workspace、凭证或 continuation 文本。

## 非目标

- 不在 Health Quantification 中实现 OpenCode session continuation。
- 不接受调用方提供 ingestion server，导出始终使用 App 内已保存的 Server URL。
- 不支持任意 callback scheme、任意 URL launcher 或通用 workflow engine。
- 不复制 OpenCode 的权限存储、Pending/Outbox 或重试状态。
- 不保证 App 被系统强制终止后仍完成导出。
- V0 不防御同设备恶意 App 抢占 custom URL scheme；consumer 必须在 callback 后重新读取 server 数据，不能把 callback 当作健康事实。

## 成功标准

- 原有无 callback deep link 和手动按钮行为不回归。
- 合法 callback 可完成 success、partial、failed、busy 四种结果返回。
- 非 OpenCode、带 userinfo/port/query/fragment、额外 path、非 canonical 编码或长度越界的 callback 全部拒绝。
- 六类导出按固定顺序执行并聚合 `sent`、`upserted` 和失败类别。
- iOS simulator build 与 unit/UI test suite 通过；真实双 App 往返作为后续真机验收。

## 关联文档

- Provider wire contract 与实现边界：[`ios_client_export_rfc.md`](ios_client_export_rfc.md)
- 跨 App runtime owner 的正式协议：OpenCode iOS repo 的 `docs/client_capabilities_protocol.md`（由 OpenCode implementation PR 交付）
