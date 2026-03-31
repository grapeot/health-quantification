# Apple Health Exporter App Shell

这个目录提供一个最薄的 macOS app shell，用来验证 bundle、签名、entitlement 和 HealthKit 运行时可用性。

它的目标不是替代 Python 主体，也不是长期 UI。它只回答一个问题：把 exporter 放进真正的 `.app` 之后，`HKHealthStore.isHealthDataAvailable()` 和睡眠读取授权能不能成立。

## 包含内容

- `Sources/main.swift`：最小 AppKit app，带两个按钮：`Run Doctor` 和 `Request Sleep Access`
- `Info.plist`：Health 使用说明
- `apple_health_exporter_app.entitlements`：HealthKit entitlement 占位

## 构建方式

从项目根目录：

```bash
scripts/build_native_exporter_app.sh
open native/apple_health_exporter_app/build/AppleHealthExporterApp.app
```

如果你本机已经有可用签名身份，也可以显式指定：

```bash
APPLE_CODESIGN_IDENTITY="Apple Development: Your Name (...)" scripts/build_native_exporter_app.sh
```

默认脚本会尝试 ad-hoc 签名。它足够验证 bundle 生成和本地启动，但 HealthKit capability 是否真正生效，仍然取决于 macOS 对签名身份与 entitlement 的运行时要求。

当前这台机器上的验证结果更进一步：即使用 Apple Development 证书重签，系统日志仍然报 `No matching profile found`。这说明 `com.apple.developer.healthkit` 对这个 app shell 来说是 restricted entitlement，单靠手工 `codesign` 不够，仍然需要一个匹配的 provisioning profile。

## 你需要做什么

最可能需要的用户动作如下：

- 在 Xcode 里用你的 team 打开一个真正的 macOS App target
- 开启 `HealthKit` capability，让 Xcode 自动生成 entitlement 与 provisioning profile
- 让 Xcode 自动签名一次
- 运行 app，看窗口顶部的 `healthDataAvailable` 状态
- 点击 `Request Sleep Access`
- 如果系统弹出健康数据权限框，点允许
- 把窗口里输出的结果告诉我

如果你愿意手动介入，最省事的方式不是从零写代码，而是用 Xcode 新建一个空的 macOS App，然后把这里的 `Sources/main.swift` 逻辑迁进去，交给 Xcode 处理 profile 和 capability。
