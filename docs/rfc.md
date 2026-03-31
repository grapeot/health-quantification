# Health Quantification RFC

## Scope

Phase 1 覆盖项目骨架、Python 主体、FastAPI ingestion server、iOS 采集端、SQLite 存储、CLI analytics、summary / artifact 基础能力。

Phase 2 在 Phase 1 基础上扩展数据采集范围：生命体征（HR、HRV、呼吸、血氧）、活动（步数）、体测（体重、血糖、血压）、生活方式（咖啡因、酒精）。

## 架构

项目采用三层分离架构：

1. **采集层（iOS app）**：通过 HealthKit 读取 Apple Health 数据，序列化为标准 JSON，POST 到 FastAPI
2. **写入层（FastAPI server）**：接收 JSON，幂等写入 SQLite，提供查询和清理端点
3. **分析层（Python CLI）**：只读访问 SQLite，输出结构化 JSON/text 数据；分析和报告生成由 AI 完成

职责分离保证：FastAPI 挂了不影响 CLI 查询，CLI 挂了不影响数据采集。

## 网络拓扑

iOS app 和 FastAPI 之间通过 Tailscale 内网通信。不需要公网暴露，不需要认证。FastAPI 默认监听 `0.0.0.0:7996`。

```
iPhone (Tailscale) --POST--> Mac (Tailscale:7996) --write--> SQLite
                                                          --read--> CLI
```

## Ingestion 协议

### POST /ingest/sleep

接收一批睡眠样本，幂等写入。幂等键为 `(source, source_id)`。

请求体：
```json
{
  "source": "apple_health_ios",
  "exported_at": "ISO8601",
  "schema_version": "0.1.0",
  "samples": [
    {
      "source_id": "UUID from HealthKit",
      "start_at": "ISO8601",
      "end_at": "ISO8601",
      "stage": "asleep_deep",
      "stage_value": 3,
      "source_bundle_id": "com.apple.health",
      "source_name": "Health",
      "metadata": {}
    }
  ]
}
```

响应 200：
```json
{"status": "accepted", "upserted": 15, "total_samples": 15}
```

### POST /ingest/vitals

接收生命体征样本（静息心率、HRV、呼吸频率、血氧），幂等写入。幂等键为 `(source, source_id, metric_type)`。

请求体：
```json
{
  "source": "apple_health_ios",
  "exported_at": "ISO8601",
  "schema_version": "0.1.0",
  "samples": [
    {
      "source_id": "UUID from HealthKit",
      "recorded_at": "ISO8601",
      "metric_type": "resting_heart_rate",
      "value": 62.0,
      "unit": "count/min",
      "source_bundle_id": "com.apple.health",
      "source_name": "Health",
      "metadata": {}
    }
  ]
}
```

`metric_type` 取值：`resting_heart_rate` | `heart_rate_variability_sdnn` | `respiratory_rate` | `oxygen_saturation`

### POST /ingest/body

接收体测数据（体重、血糖、血压），幂等写入。幂等键为 `(source, source_id, metric_type)`。

请求体：
```json
{
  "source": "apple_health_ios",
  "exported_at": "ISO8601",
  "schema_version": "0.1.0",
  "samples": [
    {
      "source_id": "UUID from HealthKit",
      "recorded_at": "ISO8601",
      "metric_type": "body_mass",
      "value": 75.5,
      "unit": "kg",
      "source_bundle_id": "com.apple.health",
      "source_name": "Health",
      "metadata": {}
    }
  ]
}
```

`metric_type` 取值：`body_mass` | `blood_glucose` | `blood_pressure_systolic` | `blood_pressure_diastolic`

血压说明：收缩压和舒张压作为两条独立记录提交，共享同一 `source_id` 以保持配对关系。iOS 端从 `HKCorrelationType` 中提取。

### POST /ingest/lifestyle

接收生活方式数据（咖啡因、酒精），幂等写入。幂等键为 `(source, source_id)`。

请求体：
```json
{
  "source": "apple_health_ios",
  "exported_at": "ISO8601",
  "schema_version": "0.1.0",
  "samples": [
    {
      "source_id": "UUID from HealthKit",
      "recorded_at": "ISO8601",
      "metric_type": "dietary_caffeine",
      "value": 150.0,
      "unit": "mg",
      "source_bundle_id": "com.apple.health",
      "source_name": "Health",
      "metadata": {}
    }
  ]
}
```

`metric_type` 取值：`dietary_caffeine` | `dietary_alcohol`

### POST /ingest/activity

接收活动数据（步数），幂等写入。幂等键为 `(source, source_id)`。

请求体：
```json
{
  "source": "apple_health_ios",
  "exported_at": "ISO8601",
  "schema_version": "0.1.0",
  "samples": [
    {
      "source_id": "UUID from HealthKit",
      "start_at": "ISO8601",
      "end_at": "ISO8601",
      "metric_type": "step_count",
      "value": 8500,
      "unit": "count",
      "source_bundle_id": "com.apple.health",
      "source_name": "Health",
      "metadata": {}
    }
  ]
}
```

### GET /ingest/{data_type}

查询已入库数据。`data_type` 取值：`sleep` | `vitals` | `body` | `lifestyle` | `activity`。支持 `from_date`、`to_date`、`source`、`metric_type` 过滤。

### DELETE /ingest/{data_type}?source=<source>

按 source 删除。主要用于测试清理。

### GET /health

健康检查。

## 数据模型

### sleep_samples 表

```sql
CREATE TABLE IF NOT EXISTS sleep_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT,
    stage TEXT NOT NULL,
    stage_value INTEGER NOT NULL,
    source_bundle_id TEXT,
    source_name TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
)
```

`source` + `source_id` 是幂等键。`ON CONFLICT` 时更新所有字段和 `updated_at`。

### vitals_samples 表

```sql
CREATE TABLE IF NOT EXISTS vitals_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source_bundle_id TEXT,
    source_name TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id, metric_type)
)
```

### body_samples 表

```sql
CREATE TABLE IF NOT EXISTS body_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source_bundle_id TEXT,
    source_name TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id, metric_type)
)
```

### lifestyle_samples 表

```sql
CREATE TABLE IF NOT EXISTS lifestyle_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source_bundle_id TEXT,
    source_name TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
)
```

### activity_samples 表

```sql
CREATE TABLE IF NOT EXISTS activity_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    start_at TEXT,
    end_at TEXT,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source_bundle_id TEXT,
    source_name TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
)
```

## HealthKit Type 映射

### Sleep（Phase 1）

| HKCategoryValueSleepAnalysis | stage 字符串 | stage_value |
|---|---|---|
| .inBed | in_bed | 0 |
| .awake | awake | 1 |
| .asleepCore | asleep_core | 2 |
| .asleepDeep | asleep_deep | 3 |
| .asleepREM | asleep_rem | 4 |
| .asleepUnspecified | asleep_unspecified | 5 |

### Vitals（Phase 2）

| HealthKit Type | metric_type | unit |
|---|---|---|
| HKQuantityTypeIdentifier.restingHeartRate | resting_heart_rate | count/min |
| HKQuantityTypeIdentifier.heartRateVariabilitySDNN | heart_rate_variability_sdnn | ms |
| HKQuantityTypeIdentifier.respiratoryRate | respiratory_rate | count/min |
| HKQuantityTypeIdentifier.oxygenSaturation | oxygen_saturation | % |

### Body（Phase 2）

| HealthKit Type | metric_type | unit |
|---|---|---|
| HKQuantityTypeIdentifier.bodyMass | body_mass | kg |
| HKQuantityTypeIdentifier.bloodGlucose | blood_glucose | mg/dL |
| HKCorrelationType.bloodPressure | blood_pressure_systolic | mmHg |
| HKCorrelationType.bloodPressure | blood_pressure_diastolic | mmHg |

### Lifestyle（Phase 2）

| HealthKit Type | metric_type | unit |
|---|---|---|
| HKQuantityTypeIdentifier.dietaryCaffeine | dietary_caffeine | mg |
| HKQuantityTypeIdentifier.dietaryAlcohol | dietary_alcohol | g |

### Activity（Phase 2）

| HealthKit Type | metric_type | unit |
|---|---|---|
| HKQuantityTypeIdentifier.stepCount | step_count | count |

## 模块边界

### Python 包

- `config.py`：环境变量与路径配置（含 server_host / server_port）
- `storage.py`：SQLite 连接、schema 初始化、所有数据类型的 CRUD
- `models.py`：observation / daily summary 数据结构（覆盖所有数据类型）
- `server.py`：FastAPI app，每种数据类型独立 ingestion endpoint
- `cli.py`：薄 CLI，支持所有数据类型的查询与分析
- `analysis/`：纯逻辑 summary 计算（sleep + vitals + body + lifestyle + activity）
- `artifacts/`：图表辅助函数（PNG，AI 按需调用）

### iOS app

- `HealthKitDiagnosticsModel`：HealthKit 读取服务（读取所有数据类型，部分授权拒绝时返回空数组）
- `IngestClient`：HTTP POST 到 FastAPI（支持所有 endpoint）
- `ContentView`：诊断 + 导出 UI（Server URL 通过 @AppStorage/UserDefaults 持久化，单按钮 Export All）
- `Info.plist`：ATS 使用 `NSAllowsArbitraryLoads`（个人项目 + Tailscale 加密内网）

## CLI 合同

CLI 只负责数据查询，不碰 ingestion 和报告生成：

```bash
# Phase 1
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --date 2026-03-30 --format json

# Phase 2
python -m health_quantification.cli vitals analyze --days 30 --metric resting_heart_rate --format json
python -m health_quantification.cli vitals daily --date 2026-03-30 --format json
python -m health_quantification.cli body analyze --days 30 --metric body_mass --format json
python -m health_quantification.cli lifestyle analyze --days 30 --metric dietary_caffeine --format json
python -m health_quantification.cli activity analyze --days 30 --metric step_count --format json
```

## Deferred

- 每周报告与长期趋势图（由 AI 分析完成）
- 电子纸显示与自动部署
- 解释层、建议层、告警层（由 AI 分析完成，不固化到 CLI）
- iOS 后台自动刷新（BGTaskScheduler）
- 饮水量、营养日志、详细运动记录（workouts）
