# Apple Health Exporter Spike

这个目录现在不再只是占位，而是一个可编译的 Apple Health adapter spike。它当前采用 Swift Package executable 形态，目的是尽快验证三件事：

1. `HealthKit` 在当前 macOS 开发环境下能否被稳定编译与链接
2. 最薄的命令行形态能否承载 sleep export 逻辑
3. 真正的权限与签名约束到底要求 Swift CLI 还是 app bundle shell

当前实现包括：

- `doctor`：打印当前环境、平台、HealthKit 可用性
- `export sleep --days N --output <path>`：请求读取睡眠数据并导出 JSON
- `apple_health_exporter.entitlements`：HealthKit entitlement 占位
- `Info.plist`：usage description 占位

## 当前结论

这个 spike 的目标是先把编译、命令入口和数据 contract 固定下来。它还不等于最终打包方案。真正能否成功弹出权限、读到数据，取决于 macOS 对可执行文件签名、bundle、entitlement 和 HealthKit 授权链路的具体要求。这里保留了最小文件集合，方便下一步继续验证。

## 用法

```bash
swift build
.build/debug/apple_health_exporter doctor
.build/debug/apple_health_exporter export sleep --days 7 --output ../../data/exports/apple_health_sleep_7d.json
```

也可以从项目根目录使用：

```bash
scripts/build_native_exporter.sh
scripts/apple_health_exporter doctor
scripts/apple_health_exporter export sleep --days 7 --output data/exports/apple_health_sleep_7d.json
```

## 风险与限制

- 当前输出是 adapter spike，不是生产打包方案
- 真正的 HealthKit 权限可能要求签名后的 bundle，而不是裸 SwiftPM executable
- 真实个人健康数据不应进入 git
