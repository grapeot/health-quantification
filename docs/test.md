# 测试策略

## 验证目标

测试套件旨在保障两套解耦的契约稳定性：
1. Python 侧的数据模型、存储持久化、HTTP Ingestion 与 CLI 合同正确（通过 ASGI 与 Python 测试校验）。
2. iOS 侧 HealthKit 类型映射、JSON 编解码与 Deep Link 命令解析符合规范（通过 Xcode Swift 单元测试校验）。

系统内不存在全流程 iOS 到 FastAPI 的端到端自动化集成测试，各层测试套件保持独立解耦。

新增与修改的测试 Fixture 必须使用独立创建的合成（Synthetic）且非标识数据，严禁依赖或读取真实个人健康数据库。

## Python 测试架构

### 1. 单元测试 (`tests/unit/`)

覆盖纯逻辑计算与 Pydantic 模型校验，不依赖外部网络与服务：

- `test_server_models.py`：校验 HTTP Payload 模型合法性、缺失字段拒绝与未知字段排斥逻辑。
- `test_daily_summary.py`：校验日级摘要计算与默认结构。
- `test_record.py`：校验单条记录、illness episode 与 daily sleep notes 的存储合同。
- `test_sleep_analysis.py`：校验功能日归属、session 拆分与睡眠指标计算。

### 2. 集成测试 (`tests/integration/`)

使用内存或临时文件 SQLite 数据库，校验模块间接缝：

- `test_server.py`：使用 `httpx.AsyncClient` 结合 `ASGITransport` 直接测试 FastAPI Endpoint 的 POST 接受、幂等 Upsert、日期过滤与 GET/DELETE 功能。
- `test_cli.py`：校验 CLI 命令解析、结构化 JSON 输出与数据写入行为。
- `test_cli_record.py`：校验 CLI 手动记录、illness 与 sleep notes 命令合同。

Python 侧会拒绝所有类别的空 `samples` payload；Swift coordinator 的 empty-category 行为尚未通过真实 FastAPI 端到端测试覆盖，属于已知跨层缺口。

## iOS 测试架构 (`HealthQuantification/HealthQuantificationIOSTests/`)

- `HealthKitServiceTests.swift`：验证 HealthKit Category Value 到内部 Stage 枚举的映射。
- `IngestClientTests.swift`：验证数据 Record 与 Ingest Envelope 的 JSON 编解码及其与后端模型的兼容性。
- `HealthExportCommandTests.swift`：验证 Deep Link URL 解析、Callback ID 白名单限制与返回 URL 构建。
- `HealthExportCoordinatorTests.swift`：验证六类别顺序导出与容错逻辑。

测试通过 Xcode 或命令行运行：

```bash
cd HealthQuantification
xcodebuild test -project HealthQuantification.xcodeproj -scheme HealthQuantificationIOS -destination 'platform=iOS Simulator,id=<SIMULATOR_UDID>' CODE_SIGNING_ALLOWED=NO
```

## 测试运行指令

（以下运行指令及命令涉及的入口均使用合成/测试示例配置，不连接默认个人数据库或已运行的个人后端）

### Python 测试

```bash
.venv/bin/python -m pytest -v
```

### 手动 Smoke Check

```bash
smoke_db="$(mktemp -d)/health_quant_smoke.db"
HEALTH_QUANT_DB_PATH="$smoke_db" .venv/bin/python -m health_quantification.cli db init
HEALTH_QUANT_DB_PATH="$smoke_db" .venv/bin/python -m health_quantification.cli sleep notes add --date 2040-01-02 --note "Synthetic smoke context"
```

## 隐私与安全规范

- 新增与修改的自动化测试与手动 Smoke Check 一律使用合成（synthetic）数据。
- 测试过程中生成的临时 SQLite 文件由环境变量控制并于测试结束后销毁，禁止提交至 Git。
