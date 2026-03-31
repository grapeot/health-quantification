# Health Quantification RFC

## Scope

Phase 1 覆盖项目骨架、Python 主体、FastAPI ingestion server、iOS 采集端、SQLite 存储、CLI analytics、summary / artifact 基础能力。

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

### GET /ingest/sleep

查询已入库的睡眠样本。支持 `from_date`、`to_date`、`source` 过滤。

### DELETE /ingest/sleep?source=<source>

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

### Stage 映射

| HKCategoryValueSleepAnalysis | stage 字符串 | stage_value |
|---|---|---|
| .inBed | in_bed | 0 |
| .awake | awake | 1 |
| .asleepCore | asleep_core | 2 |
| .asleepDeep | asleep_deep | 3 |
| .asleepREM | asleep_rem | 4 |
| .asleepUnspecified | asleep_unspecified | 5 |

## 模块边界

### Python 包

- `config.py`：环境变量与路径配置（含 server_host / server_port）
- `storage.py`：SQLite 连接、schema 初始化、sleep_samples CRUD
- `models.py`：observation / daily summary 数据结构
- `server.py`：FastAPI app，只负责 ingestion
- `cli.py`：薄 CLI，只负责数据查询（JSON/text 输出）
- `analysis/`：纯逻辑 summary 计算
- `artifacts/`：图表辅助函数（PNG，AI 按需调用）

### iOS app

- `HealthKitDiagnosticsModel`：HealthKit 读取服务
- `IngestClient`：HTTP POST 到 FastAPI
- `ContentView`：诊断 + 导出 UI

## CLI 合同

CLI 只负责数据查询，不碰 ingestion 和报告生成：

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --date 2026-03-30 --format json
```

## Deferred

- CGM / smart scale / blood pressure 的完整接入流程
- 每周报告与长期趋势图
- 电子纸显示与自动部署
- 解释层、建议层、告警层
- iOS 后台自动刷新（BGTaskScheduler）
