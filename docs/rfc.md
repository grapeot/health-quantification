# Health Quantification RFC

## Scope

Phase 1 覆盖项目骨架、Python 主体、FastAPI ingestion server、iOS 采集端、SQLite 存储、CLI analytics、summary / artifact 基础能力。

Phase 2 在 Phase 1 基础上扩展数据采集范围：生命体征（HR、HRV、呼吸、血氧）、活动（步数）、体测（体重、血糖、血压）、生活方式（咖啡因、酒精）。

## 架构

项目采用以 SQLite 为中心的架构：

1. **SQLite 数据库**：唯一事实来源（single source of truth）。所有健康数据的主存储。
2. **数据源层**（多源整合）：HealthKit（iOS app）、AI 手动记录（CLI record）、第三方硬件（Fitbit、三星等）都是平等的数据输入源。
3. **写入层（FastAPI server）**：接收批量数据（iOS/硬件同步），幂等写入 SQLite。`source` 字段区分数据来源。
4. **CLI 直接写入**：`record` 子命令允许 AI 通过 CLI 直接写入单条数据（手动记录、AI 对话触发）。
5. **分析层（Python CLI）**：只读访问 SQLite，输出结构化 JSON/text 数据；分析和报告生成由 AI 完成。

职责分离保证：FastAPI 挂了不影响 CLI 查询和写入，CLI 挂了不影响数据采集。

## 网络拓扑

iOS app 和 FastAPI 之间通过 Tailscale 内网通信。不需要公网暴露，不需要认证。FastAPI 默认监听 `0.0.0.0:7996`。

```
iPhone (Tailscale) --POST--> Mac (Tailscale:7996) --write--> SQLite (唯一事实来源)
Fitbit / 三星手表 --POST-->                              --read--> CLI (JSON) --> AI
AI 对话 --CLI record-->                                          --> 分析报告
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

`metric_type` 取值：`resting_heart_rate` | `heart_rate` | `heart_rate_variability_sdnn` | `respiratory_rate` | `oxygen_saturation` | `active_energy_burned`

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


### POST /ingest/workouts

接收 structured workout 记录，幂等写入。幂等键为 `(source, source_id)`。

请求体：
```json
{
  "source": "apple_health_ios",
  "exported_at": "ISO8601",
  "schema_version": "0.1.0",
  "samples": [
    {
      "source_id": "UUID from HealthKit",
      "workout_type": "HIIT",
      "start_at": "ISO8601",
      "end_at": "ISO8601",
      "duration_seconds": 1800.0,
      "total_energy_burned": 280.0,
      "total_distance_meters": null,
      "source_bundle_id": "com.apple.health",
      "source_name": "Health",
      "metadata": {}
    }
  ]
}
```

`workout_type` 取值：Apple Health `HKWorkoutActivityType` 名称（如 `running`、`traditionalStrengthTraining`、`HIIT`、`other`）。

### GET /ingest/{data_type}

查询已入库数据。`data_type` 取值：`sleep` | `vitals` | `body` | `lifestyle` | `activity` | `workouts`。支持 `from_date`、`to_date`、`source`、`metric_type` 过滤。

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


### workouts 表

```sql
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    workout_type TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    duration_seconds REAL,
    total_energy_burned REAL,
    total_distance_meters REAL,
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

### Workouts

| HealthKit Type | workout_type |
|---|---|
| HKWorkoutType.workoutType() | HKWorkoutActivityType 名称（running, traditionalStrengthTraining, HIIT, other 等） |


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

CLI 负责数据查询、数据写入和分析输出：

```bash
# 数据库管理
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init

# 数据写入（AI 手动记录 / 对话触发）
python -m health_quantification.cli record lifestyle --metric dietary_caffeine --value 57 --unit mg --time "2026-03-31T12:00:00-07:00" --note "Costco Mexican Coke 500ml"
python -m health_quantification.cli record body --metric body_mass --value 75.5 --unit kg --time "2026-03-31T07:00:00-07:00"

# Phase 1 查询
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --date 2026-03-30 --format json

# Phase 2 查询
python -m health_quantification.cli vitals analyze --days 30 --metric resting_heart_rate --format json
python -m health_quantification.cli vitals daily --date 2026-03-30 --format json
python -m health_quantification.cli body analyze --days 30 --metric body_mass --format json
python -m health_quantification.cli lifestyle analyze --days 30 --metric dietary_caffeine --format json
python -m health_quantification.cli activity analyze --days 30 --metric step_count --format json
```

### record 子命令

`record` 子命令用于写入单条数据到 SQLite，主要给 AI agent 调用。参数：

- `data_type`: `sleep` | `vitals` | `body` | `lifestyle` | `activity`
- `--metric`: metric_type（如 `dietary_caffeine`）
- `--value`: 数值
- `--unit`: 单位（如 `mg`、`kg`）
- `--time`: ISO 8601 时间戳（默认当前时间）
- `--source`: 数据来源标识（默认 `ai_manual`）
- `--note`: 可选备注

写入时自动生成 `source_id`（UUID），幂等键与 POST endpoint 相同。

### source 字段约定

| source 值 | 含义 |
|-----------|------|
| `apple_health_ios` | Apple Health / iOS app 批量导出 |
| `ai_manual` | AI agent 通过 CLI record 写入 |
| `manual_cli` | 用户手动通过 CLI 写入 |
| `fitbit` | Fitbit 设备（预留） |
| `samsung_health` | Samsung Health（预留） |

## Deferred

- 每周报告与长期趋势图（由 AI 分析完成）
- 电子纸显示与自动部署
- 解释层、建议层、告警层（由 AI 分析完成，不固化到 CLI）
- iOS 后台自动刷新（BGTaskScheduler）
- 饮水量、营养日志

## Phase 3: AI 驱动的知识库

### 设计思路

当用户通过自然语言告诉 AI 健康事件（如"我喝了瓶可乐"），AI 需要：

1. **识别意图**：这是一个需要记录的健康事件
2. **补全细节**：引导用户确认品牌、容量、时间等
3. **查表换算**：从知识库或网上获取营养数据（咖啡因含量、卡路里等）
4. **写入数据库**：通过 CLI `record` 命令写入 SQLite

### 知识库格式

知识库以自然语言 JSON 存储，初始版本覆盖常见饮料和食品：

```json
{
  "items": [
    {
      "name": "Mexican Coca-Cola",
      "brand": "Coca-Cola (Mexico)",
      "serving_size_ml": 500,
      "serving_size_fl_oz": 16.9,
      "caffeine_mg": 57,
      "caffeine_per_100ml_mg": 11.4,
      "sugar_g": 54,
      "source": "USDA / product label",
      "notes": "玻璃瓶装，Costco 有售"
    },
    {
      "name": "Diet Coke",
      "brand": "Coca-Cola",
      "serving_size_ml": 355,
      "caffeine_mg": 0,
      "notes": "无咖啡因版本"
    }
  ]
}
```

### 知识库扩展流程

1. 用户提到知识库中没有的食物/饮料
2. AI 上网搜集营养数据（优先 USDA、产品官网、权威营养数据库）
3. AI 向用户确认数据后，添加到知识库
4. 后续相同物品直接查表，不再重复搜集

### AI 交互示例

用户："我刚喝了瓶可乐"
AI："帮你记录一下。确认一下细节：
- 哪种可乐？普通可口可乐（34mg/330ml）还是墨西哥可乐（玻璃瓶 500ml）？
- 多大容量？标准 500ml 瓶装？

用户："墨西哥可乐，Costco 买的 500ml 那种"
AI："Costco 墨西哥可乐 500ml，约 57mg 咖啡因。我现在帮你记到数据库。你是什么时候喝的？"

用户："12 点左右"
AI 记录完成。
