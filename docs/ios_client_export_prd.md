# iOS Client Export PRD

## 概述

Health Quantification iOS 为受信任的 OpenCode iOS 客户端提供受限的 `Export All` 导出 handoff 功能。当 AI 分析判断健康数据缺失或过期时，OpenCode 可通过 Deep Link 唤起 Health Quantification App，自动同步六类 HealthKit 数据，并在完成后通过一次性 Callback 返回 OpenCode 继续原任务。

Health Quantification 作为 Capability Provider 承担数据导出职责，HealthKit 权限、Server URL 保存、导出进度与 Backend 写入逻辑继续由 Health Quantification 独立拥有。

## 用户场景与交互流程

（以下流程与协议参数均采用合成示例数据）

```text
OpenCode 创建一次性 Callback URL
→ 打开 Health Quantification (healthquantification://export-all?callback=...)
→ Health Quantification 顺序导出 30 天 HealthKit 数据至 FastAPI 后端
→ 导出完成后调用 Callback (opencode://client-action-return/<callback-id>?status=...)
→ OpenCode 接收回调并在原 Session 继续分析
```

手动导出按钮与无 Callback 的 Deep Link (`healthquantification://export-all`) 保持兼容与独立可用。

## 功能要求

1. **导出逻辑复用**：带 Callback 的 Deep Link 必须复用手动 Export All 的完整六类别同步路径（sleep, vitals, body, lifestyle, activity, workouts）。
2. **Callback 白名单校验**：Callback 仅允许 `opencode://client-action-return/<callback-id>` 形式。
3. **Callback ID 规范**：Callback ID 必须为 43 至 128 个 URL-safe ASCII 字符。
4. **数据与隐私隔离**：Callback 返回参数仅包含状态 (`status`)、成功样本计数 (`sent`, `upserted`)、失败类别 (`failed`) 与错误码 (`error_code`)。不得在 Callback URL 中附加健康明细、Server URL、设备日志或自由文本。
5. **空数据与错误边界**：FastAPI 后端在 POST 端点上对 `samples` 强制校验 `min_length=1` 并拒绝空数组（HTTP 422）。客户端代码中仅 `body` 与 `lifestyle` 类别在空样本时主动跳过提交，其余类别若无样本仍会发起请求并触发 422 错误。空类别处理属于需要客户端进行数据校验的契约边界，而非全类别默认实现的自动降级保底。
6. **网络与安全边界**：FastAPI 后端只作为 Tailnet 内 iPhone 到 Mac 的同步接收器，默认监听可配置地址与端口（默认 `0.0.0.0:7996`），本身未鉴权。iPhone 必须使用 Mac 的 Tailscale 地址；设备身份、传输加密与访问控制由 Tailscale 和 tailnet ACL 管理。普通 LAN 与公网访问不受支持，CLI 仅在 Mac 本地读取数据。
7. **并发控制**：导出运行时，新的 Callback 请求直接返回 `busy` 状态，禁止并发导出。
8. **配置依赖**：导出使用 App 内已持久化的 Server URL。Server URL 无效时返回 `failed` 状态。

## 非目标

- 不在 Health Quantification App 中处理 OpenCode 的 Session 恢复或上下文展示。
- 不接受调用方在 Deep Link 中传入自定义 Ingestion Server 地址。
- 不支持任意 Custom Scheme 的 Callback 转发。
- 不保证 App 被系统强制终止后的后台导出恢复。
- 不包含全流程 iOS 到 FastAPI 的端到端自动化集成测试（Xcode 中的 Swift 单元测试与 Python ASGI 测试保持独立）。

## 成功标准

1. 手动 Export All 与无 Callback 的 Deep Link 功能无回归。
2. 合法 Callback 正确返回 `success`、`partial`、`failed`、`busy` 四种状态之一。
3. 非法 Callback（包含 userinfo/port/query/fragment、非白名单 Host/Scheme 或越界字符）被一律拒绝。
4. Swift 单元测试（`HealthQuantificationIOSTests`）通过。

## 关联文档

- Provider 接口与实现规范：[`ios_client_export_rfc.md`](ios_client_export_rfc.md)
