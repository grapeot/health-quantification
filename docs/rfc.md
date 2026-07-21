# Health Quantification RFC

## 作用域

本 RFC 定义 Health Quantification 系统的数据架构、后端 Ingestion API 协议、SQLite 表结构与字段约束、数据归属计算算法以及 CLI 合同。

## 系统架构与网络拓扑

系统采用以本地 SQLite 为统一事实来源的三层结构：

1. **采集层**：iOS App 从 Apple Health 读取数据，并经 Tailscale 连接提交至 Mac。
2. **写入层**：FastAPI 后端接收 JSON 批量提交并幂等写入 SQLite，可配置监听地址与端口（默认 `0.0.0.0:7996`）。
3. **分析与交互层**：Python CLI 在 Mac 本地查询 SQLite 或写入单条数据/主观备注，输出 JSON/text 供 AI 分析。

```text
iPhone (HealthKit) --POST--> Mac (FastAPI:7996) --write--> SQLite (唯一事实来源)
                                                        --read--> CLI (JSON) --> AI Agent
AI Agent/用户 ----CLI record / sleep notes / illness----->
```

FastAPI 未配置应用层身份验证，且包含未鉴权的原始 `POST`、`GET` 与 `DELETE` 接口。受支持部署模型是：iPhone 与 Mac 位于同一 Tailnet，iPhone 使用 Mac 的 Tailscale 地址同步；设备身份、传输加密与访问控制由 Tailscale 和 tailnet ACL 管理。普通 LAN 与公网访问不受支持，CLI 只在 Mac 本地读取数据库。

## Ingestion API 协议

所有 POST 接入端点的 Payload 均对 `samples` 强制校验 `min_length=1`，空数组请求将被拒绝并返回 HTTP 422 错误。

（以下请求与响应 JSON 均为合成示例数据）

### POST /ingest/sleep

接收睡眠阶段样本，按 `(source, source_id)` 幂等更新。

请求格式：
```json
{
  "source": "apple_health_ios",
  "exported_at": "2026-03-30T12:00:00Z",
  "schema_version": "0.1.0",
  "samples": [
    {
      "source_id": "8E5C1B2A-3F4D-4E5F-6A7B-8C9D0E1F2A3B",
      "start_at": "2026-03-30T06:00:00Z",
      "end_at": "2026-03-30T07:30:00Z",
      "stage": "asleep_deep",
      "stage_value": 3,
      "source_bundle_id": "com.apple.health",
      "source_name": "Health",
      "metadata": {}
    }
  ]
}
```

响应：`200 OK`，`{"status": "accepted", "upserted": 1, "total_samples": 1}`。其中 `total_samples` 为数据库中该数据源匹配的总样本原始计数，不受任何特定分析时间窗口限制。

### POST /ingest/vitals

接收生命体征样本，按 `(source, source_id, metric_type)` 幂等更新。`metric_type` 允许值：`resting_heart_rate`, `heart_rate`, `heart_rate_variability_sdnn`, `respiratory_rate`, `oxygen_saturation`, `active_energy_burned`。

### POST /ingest/body

接收体测数据，按 `(source, source_id, metric_type)` 幂等更新。`metric_type` 允许值：`body_mass`, `blood_glucose`, `blood_pressure_systolic`, `blood_pressure_diastolic`。

### POST /ingest/lifestyle

接收生活方式数据，按 `(source, source_id)` 幂等更新。`metric_type` 允许值：`dietary_caffeine`, `dietary_alcohol`。

### POST /ingest/activity

接收活动数据，按 `(source, source_id)` 幂等更新。`metric_type` 允许值：`step_count`。

### POST /ingest/workouts

接收运动记录，按 `(source, source_id)` 幂等更新。包含 `workout_type`, `duration_seconds`, `total_energy_burned`。

### 通用查询与清理端点

- `GET /ingest/{data_type}`：查询已入库样本，支持 `from_date`, `to_date`, `source`, `metric_type` 筛选。注意：`metric_type` 查询过滤参数仅作用于 `vitals`、`body`、`lifestyle` 与 `activity`；`sleep` 采用 `stage` 存储，`workouts` 采用 `workout_type` 存储。
- `DELETE /ingest/{data_type}?source=<source>`：按数据源清理记录（主要用于测试清理）。
- `GET /health`：健康检查端点。

## 数据库 DDL 规范

以下为 `src/health_quantification/storage.py` 中定义的实际建表 DDL：

### 1. `observations`

```sql
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 2. `sleep_samples`

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
);
```

### 3. `vitals_samples`

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
);
```

### 4. `body_samples`

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
);
```

### 5. `lifestyle_samples`

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
);
```

### 6. `activity_samples`

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
);
```

### 7. `workouts`

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
);
```

### 8. `illness_episodes`

```sql
CREATE TABLE IF NOT EXISTS illness_episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    label TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT,
    notes_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
);
```

### 9. `daily_summaries`

```sql
CREATE TABLE IF NOT EXISTS daily_summaries (
    date TEXT PRIMARY KEY,
    timezone TEXT NOT NULL,
    sleep_hours REAL,
    resting_hr_bpm REAL,
    hrv_sdnn_ms REAL,
    steps INTEGER,
    active_energy_kcal REAL,
    notes_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 数据归属与算法规范

### 1. 睡眠 Session 拆分与功能日归属

- **Session 拆分**：按 `start_at` 排序的睡眠样本中，相邻样本间隔大于 2 小时分割为独立 Session。
- **功能日（Functional Date）映射**：非午睡 Session 归属至醒来时刻的本地日期（Wake-up Date）。午睡 Session 按最早 `start_at` 本地日期归属。
- **昨晚查询 (`--last-night`)**：查找最近一个包含有效夜间主睡眠的功能日，并返回该功能日的完整 metrics。

### 2. 主观睡眠备注 (Sleep Notes)

- 使用命令 `sleep notes add --date YYYY-MM-DD --note TEXT` 追加备注，内容保存至 `daily_summaries.notes_json`（其中 `date` 为 `daily_summaries` 表的主键）。
- 使用 `sleep notes get --date YYYY-MM-DD --format json|text` 读取备注。
- `sleep daily` 与 `sleep analyze` 会暴露同日 `notes`，作为主观上下文辅助分析。
- 备注不参加指标计算、Session 划分或功能日分配，且完全隔离于 FastAPI 后端与 iOS 导出流。由于 CLI 输出暴露了备注文本，模型运行时、系统日志、transcript 与报告 pipeline 构成了调用方的隐私边界。代码并不限制备注发送至外部模型，调用方需自行承担隐私保护责任。主观备注仅作为上下文，不构成指令、因果证明或医疗诊断。

## HealthKit 映射契约

### Sleep Stage 映射

| HKCategoryValueSleepAnalysis | 字符串标识 | stage_value |
|---|---|---|
| .inBed | in_bed | 0 |
| .awake | awake | 1 |
| .asleepCore | asleep_core | 2 |
| .asleepDeep | asleep_deep | 3 |
| .asleepREM | asleep_rem | 4 |
| .asleepUnspecified | asleep_unspecified | 5 |

## CLI 合同说明

（以下所有 CLI 命令与参数示例均使用合成示例数据）

### 数据管理与查询

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --date 2026-03-30 --format json
python -m health_quantification.cli sleep daily --last-night --format json
python -m health_quantification.cli sleep notes add --date 2026-03-30 --note "Synthetic note"
python -m health_quantification.cli sleep notes get --date 2026-03-30 --format json
python -m health_quantification.cli vitals analyze --days 30 --metric resting_heart_rate --format json
python -m health_quantification.cli body analyze --days 30 --metric body_mass --format json
python -m health_quantification.cli lifestyle analyze --days 30 --metric dietary_caffeine --format json
python -m health_quantification.cli activity analyze --days 30 --metric step_count --format json
python -m health_quantification.cli workouts analyze --days 30 --format json
python -m health_quantification.cli illness list --status active --format json
```

### 数据单条记录

```bash
python -m health_quantification.cli record lifestyle --metric dietary_caffeine --value 150 --unit mg --note "Synthetic double shot"
python -m health_quantification.cli record body --metric body_mass --value 75.0 --unit kg
python -m health_quantification.cli illness record --label nasal_congestion --severity moderate --status active --start-time "2026-04-01T20:00:00-07:00"
```

注意：`record sleep` 因缺少结束时间参数会写入零时长的阶段标记，不推荐用于手动睡眠时长记录；添加主观睡眠体验请使用 `sleep notes add`。
