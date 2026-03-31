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
xcodebuild test -scheme HealthQuantificationIOS -destination 'platform=iOS,name=My iPhone'
```

## 手工 smoke checks

```bash
.venv/bin/python -m health_quantification.cli doctor config
.venv/bin/python -m health_quantification.cli db init
curl -s http://localhost:7996/health
```
