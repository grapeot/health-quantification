# iOS Client Export RFC

## 作用域

本 RFC 定义 Health Quantification iOS App 作为 `health_quantification.export_all` provider 的 Deep Link 唤起、六类别导出执行与 Callback 返回协议。

OpenCode 侧的权限控制、Callback 持久化与 Session 恢复逻辑不属于本仓库范围。

## 唤起协议 (Launch Contract)

（以下所有 Deep Link 与 Callback 示例 URL 均使用合成示例数据）

### 基础唤起（无 Callback）

```text
healthquantification://export-all
```

### 跨 App Handoff 唤起

```text
healthquantification://export-all?callback=<percent-encoded-callback-url>
```

### Callback URL 校验规则

解码后的 Callback URL 必须严格满足以下条件：

1. Scheme 必须为 `opencode`，Host 必须为 `client-action-return`。
2. Path 仅包含单个 Callback ID，不允许包含额外 Path 层级。
3. Callback ID 长度为 43 至 128 个 ASCII 字符（仅允许字母、数字、`-`、`_`）。
4. 禁止包含 userinfo、port、query 或 fragment。
5. 解码后的 Callback 字符串总长度不得超过 512 字符。

外层 URL 仅允许单个 `callback` 查询参数。任何未知或重复参数将导致唤起命令被直接拒绝。唤起命令不得修改 App 内持久化的 Server URL。

## 执行协议 (Execution Contract)

`HealthExportCoordinator` 在 MainActor 上按固定顺序依次执行：

```text
sleep → vitals → body → lifestyle → activity → workouts
```

每个类别的 Fetch 与 Ingest 独立捕获异常。FastAPI 后端针对 Ingestion POST 端点强制要求 `samples` 数组最小长度为 1，接收空数组时返回 422 错误。在 Swift `HealthExportCoordinator` 当前实现中，仅 `body` 与 `lifestyle` 类别主动对空样本进行判断（`samples.isEmpty`）并跳过 HTTP POST；其余类别若未查到样本仍会尝试提交并触发后端 422 错误。因此空类别与无数据场景需要客户端进行前置校验，而非全类别自动容错。

### 状态与错误码聚合规则

| 条件 | status | error_code |
|---|---|---|
| 无类别失败 | `success` | 无 |
| 部分类别失败 | `partial` | `category_failure` |
| 全部类别失败 | `failed` | `category_failure` |
| 已有导出正在运行 | `busy` | `export_in_progress` |
| Server URL 无效 | `failed` | `invalid_server_url` |

`sent` 表示成功提交至 Ingestion 后端的样本总数；`upserted` 表示后端返回的 `upserted` 累计值。失败类别的样本计数不计入总数。

## 返回协议 (Return Contract)

### Callback 格式示例

成功返回（合成示例）：
```text
opencode://client-action-return/<callback-id>?status=success&sent=1200&upserted=1200
```

部分失败返回（合成示例）：
```text
opencode://client-action-return/<callback-id>?status=partial&sent=1000&upserted=1000&failed=sleep,workouts&error_code=category_failure
```

### 参数说明

| 字段 | 允许值 / 规范 |
|---|---|
| `status` | `success` / `partial` / `failed` / `busy` |
| `sent` | 非负十进制整数 |
| `upserted` | 非负十进制整数 |
| `failed` | 逗号分隔的失败类别枚举（无失败时省略） |
| `error_code` | `category_failure` / `export_in_progress` / `invalid_server_url`（无错误时省略） |

返回 URL 使用 Foundation `URLComponents` 构造。不得包含健康明细、设备标识、内部日志或自由文本。

## 并发控制与生命周期

1. **Single-Flight 机制**：App 级共享 `HealthExportRuntime` 在创建异步 Export Task 前同步 claim 命令。在已有导出运行期间，后续唤起请求直接返回 `busy` 状态。
2. **多 Scene 隔离**：同一命令被多个 iPad Scene 观察到时，仅首个 Scene 触发导出，其余判定为重复命令。
3. **一次性唤起**：每个已接受的命令最多触发一次 Callback。Callback 不在 iOS App 端持久化。

## 安全边界

- Callback ID 由调用方生成，Health App 仅验证格式并原样返回。
- Callback URL 不传输任何健康数据样本、用户身份标识、Server 地址或凭据。
- 接收 Callback 后，调用方必须通过 CLI 或后端 API 重新读取数据确认 freshness，不得将 Callback 状态直接等同于健康事实。
- 系统不包含 iOS 到 FastAPI 的端到端自动化测试；Swift 单元测试（位于 `HealthQuantificationIOSTests`）独立验证 Xcode 项目逻辑。

## 代码结构映射

- `Models/HealthExportCommand.swift`：Deep Link 命令解析与 Callback URL 构建。
- `Services/HealthExportCoordinator.swift`：六类别顺序导出与结果聚合。
- `HealthQuantificationIOSApp.swift`：App 级 Deep Link URL 入口捕获。
- `ContentView.swift`：导出状态展示与 UI 交互处理。
- `HealthQuantificationIOSTests/HealthExportCommandTests.swift`：命令解析与 Callback 构建单元测试。
- `HealthQuantificationIOSTests/HealthExportCoordinatorTests.swift`：顺序导出与容错逻辑单元测试。
