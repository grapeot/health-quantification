# 测试策略

## 目标

验证三件事：Python 侧的模型/存储/HTTP 合同稳定，iOS 侧编解码与 stage 映射正确，端到端 ingestion 管道（iOS → FastAPI → SQLite）幂等且数据完整。

## Python 测试

### Unit tests（`tests/unit/`）

纯逻辑，不依赖外部服务或真实数据：

- `test_server_models.py`：Pydantic 模型验证（合法 payload 接受、缺字段拒绝、类型错误拒绝、未知字段拒绝）
- `test_daily_summary.py`：日级 summary 默认结构

### Integration tests（`tests/integration/`）

用临时 SQLite 验证端到端接缝，所有测试自包含，不需要跑真实 FastAPI 进程：

- `test_server.py`：HTTP 合同测试（POST 接受、幂等 upsert、日期过滤、DELETE 清理、/health、422 校验），使用 `httpx.AsyncClient` + `ASGITransport` 直接调 FastAPI app
- `test_cli.py`：CLI smoke test

## iOS 测试（`HealthQuantification/HealthQuantificationIOSTests/`）

- `HealthKitServiceTests.swift`：HealthKit stage → ingestion stage 映射
- `IngestClientTests.swift`：`SleepSampleRecord` / `IngestEnvelope` JSON 编解码，验证与 FastAPI Pydantic 模型兼容
- `HealthExportCommandTests.swift`：旧 deep link 兼容、严格 callback allowlist、success/partial/failed/busy 返回合同与结果聚合
- `HealthExportCoordinatorTests.swift`：六类别顺序执行、空类别处理、单类失败后继续和 partial 聚合

通过 `xcodebuild test -scheme HealthQuantificationIOS` 运行。

## Live integration tests

骨架已保留，用于未来验证真实 adapter。默认 skip，只有 `HEALTH_QUANT_ENABLE_LIVE_TESTS=1` 时运行。

## 真实数据验证（手工）

iOS 真机 export 后，通过 API 确认数据完整性：

```bash
curl -s http://localhost:7996/ingest/sleep | python3 -c "
import json, sys; data = json.load(sys.stdin)
print(f'Total: {len(data)}, Days: {len(set(s[\"start_at\"][:10] for s in data))}')
print(f'Stages: {dict()}')  # 检查 stage 分布是否合理
print(f'Dupes: {len([s[\"source_id\"] for s in data]) - len(set(s[\"source_id\"] for s in data))}')
"
```

已验证（2026-03-30）：813 samples, 30 天, 0 重复, stage 分布符合预期。

## 运行方式

Python：
```bash
.venv/bin/python -m pytest -v
```

iOS（需 Xcode + 真机或 simulator）：
```bash
cd HealthQuantification
xcodebuild build -project HealthQuantification.xcodeproj -scheme HealthQuantificationIOS -destination 'platform=iOS Simulator,id=<SIMULATOR_UDID>' CODE_SIGNING_ALLOWED=NO
xcodebuild test -project HealthQuantification.xcodeproj -scheme HealthQuantificationIOS -destination 'platform=iOS Simulator,id=<SIMULATOR_UDID>' CODE_SIGNING_ALLOWED=NO
```

Build 和 test 必须顺序运行。Simulator 覆盖 pure contract、coordinator 和 UI regression；真实 HealthKit 数据、两个 App 的 custom URL 冷/热启动及自动回跳仍需真机验收。

Callback contract 的自动化验收至少包括：错误 scheme/host、userinfo、port、额外 path、callback 自带 query/fragment、非 canonical percent encoding、未知外层 query、空 callback 和短 ID 均拒绝；合法结果只出现 RFC allowlist 字段，不能包含健康样本或自由文本错误。`HealthExportRuntime` 的 pure test 验证多 scene 重复 command 只 claim 一次、并发不同 command 只产生一次 busy decision。

## 手工 smoke checks

```bash
.venv/bin/python -m health_quantification.cli doctor config
.venv/bin/python -m health_quantification.cli db init
curl -s http://localhost:7996/health
```
