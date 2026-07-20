# iOS Client Export RFC

## Scope

本 RFC 定义 Health Quantification iOS 作为 `health_quantification.export_all` provider 的输入、执行和 callback 合同。OpenCode 侧的本地权限、callback persistence、session correlation 和 continuation 不属于本仓库。

## Launch Contract

旧入口继续支持：

```text
healthquantification://export-all
```

OpenCode handoff 使用：

```text
healthquantification://export-all?callback=<percent-encoded-callback-url>
```

解码后的 callback 必须满足以下全部条件：

- scheme 为 `opencode`，host 为 `client-action-return`。
- path 只有一个 callback ID，不允许额外 path segment。
- callback ID 长度为 43 至 128，只含 ASCII 字母、数字、`-`、`_`，且 path 不使用 percent escape 表示这些字符。
- 不含 user、password、port、query 或 fragment。
- 解码后的 callback 字符串不超过 512 字符。

外层 URL 只接受零个或一个 `callback` query item。任何未知或重复 query item 都会让命令解析失败。调用方不能通过 deep link 覆盖 Health Quantification 已保存的 Server URL。

## Execution Contract

`HealthExportCoordinator` 在 MainActor 上按固定顺序执行：

```text
sleep → vitals → body → lifestyle → activity → workouts
```

每类 fetch 或 ingest 独立捕获错误。body 和 lifestyle 没有样本时跳过 POST，记录为成功且计数为零；其他类别沿用既有 ingestion 行为。聚合规则为：

| 条件 | status | error_code |
|---|---|---|
| 无类别失败 | `success` | 无 |
| 部分类别失败 | `partial` | `category_failure` |
| 全部类别失败 | `failed` | `category_failure` |
| 已有导出运行 | `busy` | `export_in_progress` |
| Server URL 无效 | `failed` | `invalid_server_url` |

`sent` 是成功进入 ingest 的样本数之和；`upserted` 是 FastAPI 对成功请求返回的 `upserted` 之和。失败类别的计数不进入总数。`upserted` 沿用后端语义，包含 insert 和 conflict update，不表示纯新增。

## Return Contract

成功示例：

```text
opencode://client-action-return/<callback-id>?status=success&sent=1240&upserted=1240
```

部分失败示例：

```text
opencode://client-action-return/<callback-id>?status=partial&sent=1100&upserted=1100&failed=sleep,workouts&error_code=category_failure
```

允许的 query 字段：

| 字段 | 合同 |
|---|---|
| `status` | `success`、`partial`、`failed`、`busy` |
| `sent` | 非负十进制整数 |
| `upserted` | 非负十进制整数 |
| `failed` | 逗号分隔的固定类别枚举；没有失败时省略 |
| `error_code` | `category_failure`、`export_in_progress`、`invalid_server_url`；没有错误时省略 |

Health Quantification 用 Foundation `URLComponents` 和 `URLQueryItem` 构造返回 URL，不拼接自由文本。完整 category error 只留在本地状态 UI，不进入 callback。

## Concurrency And Lifecycle

App 入口把已解析 command 追加到数组，而不是覆盖单个 optional slot；即使多个 URL 在 SwiftUI render 前到达，也会在下一次 observation 中一起 drain。App 级共享的 `HealthExportRuntime` 在创建异步 export Task 前同步 claim command。多个 iPad scene 观察到同一个 command 时，只有第一个 scene 启动导出，其余视为 duplicate；不同 command 在导出期间只返回一次 `busy`。手动重复点击由共享状态和 disabled button 阻止。

每个已接受的 command 最多触发一次 callback。Health App 不持久化 callback；OpenCode 在打开 Health App 前持久化 correlation，因此 OpenCode 被系统终止后仍可在 callback 唤起时恢复原任务。Health App 自身被终止时，本次调用由 OpenCode 的短期 Pending expiration 收敛。

## Security Boundary

- callback ID 由 OpenCode 生成并兼作一次性 bearer token；Health App 只验证形状并原样返回。
- Health App 不知道 token 对应哪个 session，也无法指定 continuation 目标。
- callback URL 不携带健康样本、用户身份、host、workspace、server response 或认证信息。
- custom URL scheme 不是调用方认证。真正的 callback 验收由 OpenCode 通过本地未过期 Pending record 完成。

V0 明确接受 custom URL scheme 可被同设备恶意 App 抢占的残余风险。抢占者可能窃取 callback ID 并伪造“导出完成”，但 callback 不能携带健康事实，也不授权后续副作用；OpenCode continuation 必须重新从 Health Quantification server 读取 freshness 和样本后再分析。需要抵御同设备恶意 App 时，应把 launch/return transport 升级为绑定 Associated Domains 的 universal link，而不是继续扩展 custom scheme。

## Implementation Map

- `Models/HealthExportCommand.swift`：strict parser、结果枚举和 callback builder。
- `Services/HealthExportCoordinator.swift`：六类别顺序执行与聚合。
- `HealthQuantificationIOSApp.swift`：deep-link command 入口。
- `ContentView.swift`：single-flight、状态 UI 和 callback handoff。
- `HealthQuantificationIOSTests/HealthExportCommandTests.swift`：URL/result contract。
- `HealthQuantificationIOSTests/HealthExportCoordinatorTests.swift`：顺序执行和 partial continuation。
