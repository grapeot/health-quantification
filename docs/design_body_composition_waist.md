# 体成分与腰围记录：调研与设计

状态：proposed；2026-10-04。仅设计与调研，未实现。落地位置在 health_quantification 公开仓库前需注意隐私规范（本仓库为公开代码库，不得提交真实健康数据）。

## Bottom line

**体成分类数据采集不到，根因是采集端没读，不是秤的问题。** HealthKit 有 `bodyFatPercentage`（体脂率）和 `leanBodyMass`（瘦体重）两个类型，第三方体脂秤可以把它们写进 Apple Health，但 iOS 采集端的 `bodyQuantityConfigurations()` 只配了 `bodyMass` 和 `bloodGlucose` 两项。所以数据即使已经在 Apple Health 里，也不会被采集。需要 iOS、后端、CLI 三处一起改，但都是小改。

**腰围同理。** HealthKit 也有 `waistCircumference`，也没读。它和体脂率、瘦体重一样属于体测类，归到现有 `body` 数据域。设计里存的是腰围的**原始厘米值**，不是腰高比——比值属于分析层，不该作为原始数据存。

## 现状：代码证据

| 需求 | HealthKit 是否支持 | 采集端是否读 | 证据 |
|---|---|---|---|
| 体脂率 | 支持 `bodyFatPercentage` | 否 | `HealthQuantificationIOS/HealthKitDiagnosticsModel.swift:779-788` 的 `bodyQuantityConfigurations()` 只列了 `bodyMass`、`bloodGlucose` |
| 瘦体重 | 支持 `leanBodyMass` | 否 | 同上 |
| 腰围 | 支持 `waistCircumference` | 否 | 同上 |
| 体重 | 支持 `bodyMass` | 是 | 已入库 `body_samples.metric_type='body_mass'` |

后端对 `body` 的 `metric_type` 有白名单，硬编码在 `src/health_quantification/server.py:104-109`：

```python
BodyMetricType = Literal[
    "body_mass",
    "blood_glucose",
    "blood_pressure_systolic",
    "blood_pressure_diastolic",
]
```

新 metric 若不在这个 Literal 里，`POST /ingest/body` 会被 Pydantic 以 422 拒绝。这是加新类型时最关键的一道门。存储层反而是通用的：`body_samples` 用 `UNIQUE(source, source_id, metric_type)`，`_upsert_samples_by_metric_type` 按 `metric_type` 写，所以底层不用改表结构，只要放行白名单。

HealthKit 各类型的可用性参考 Apple 的 [HKQuantityTypeIdentifier](https://developer.apple.com/documentation/healthkit/hkquantitytypeidentifier)（体测类含 bodyMass、bodyMassIndex、bodyFatPercentage、leanBodyMass、waistCircumference）。

## 设计：体成分 + 腰围（扩展现有 body 域）

这三个都放进现有 `body` 数据域，复用 `body_samples` 表，不新增存储。

**iOS 改动**（`HealthKitDiagnosticsModel.swift` 的 `bodyQuantityConfigurations()`）：加三条 configuration。

| HealthKit 类型 | metric_type | unitLabel | 取值/归一化 |
|---|---|---|---|
| `bodyFatPercentage` | `body_fat_percentage` | `%` | `doubleValue(for: .percent()) * 100`（HealthKit 存的是 0–1 的比例，和现有 `oxygen_saturation` 同一坑） |
| `leanBodyMass` | `lean_body_mass` | `kg` | `doubleValue(for: .gramUnit(with: .kilo))` |
| `waistCircumference` | `waist_circumference` | `cm` | `doubleValue(for: .meterUnit(with: .centi))` |

`readTypesForExport()`（同文件 `:711`）遍历 `bodyQuantityConfigurations()` 自动收集授权类型，所以授权清单会随之上更新，无需单独改。

**后端改动**（`server.py:104-109`）：往 `BodyMetricType` Literal 加三个值。CLI 的 `body analyze/daily` 是通用实现（`cli.py` 的 `for command_name in ("vitals","body","lifestyle","activity")` 循环注册），加完白名单后无需改 CLI 即可查询。

**单位归一化是唯一要小心的点**：体脂率必须乘 100，否则面板上显示 0.23 而不是 23。这条要在 iOS 端做对，否则数据入库就错了。

**腰围按原始厘米值存**，比值（腰高比）在分析或面板层按需计算，不入库。这也符合你"腰围不是腰高比"的要求。

## 需要你决定的事

这两项是你的领域取舍，不替你拍。

1. **体成分是否现在就动 iOS 端。** 改动本身小，但要经过 build → 真机 → 重新授权 → 导出验证的真实设备流程（见 `docs/ios_real_device_testing.md`），不是纯 Python 能完成的。也可以先在 Python 侧把白名单和 CLI 准备好，iOS 改动攒到一次做。
2. **腰围的录入方式。** 如果体脂秤或 Auto Export 类 App 能把 `waistCircumference` 写进 Apple Health，就走 HealthKit 自动；否则用 CLI 手工 `record`（每月一次，手工成本可忽略）。

## 分阶段实现清单（确认后再做）

**阶段 1——Python 侧（低风险，可先做）**
1. `server.py` 的 `BodyMetricType` Literal 加三项。
2. CLI `record body` 支持新 metric（若走手工录入）。
3. 补合成数据的单元测试与 `doctor config` / smoke check。
4. 更新 `AGENTS.md` 的 schema 说明表。

**阶段 2——iOS 侧（需真机）**
5. `bodyQuantityConfigurations()` 加三条，注意体脂率 ×100。
6. build → 真机 → 重新授权 → 导出一个窗口的数据 → 回读数据库验证三项都有值。
7. 更新 `docs/working.md`。

## 验收与风险

- **验收**：体成分三项在 `body_samples` 里能查到、单位正确（体脂 20 而非 0.2）、能按日聚合；腰围存厘米值。
- **风险**：新增 HealthKit 类型会触发重新授权弹窗；体脂率单位换算是最容易出错的点；BIA 秤的体脂绝对值有 ±3–5% 误差，看趋势而非绝对值；本仓库为公开库，任何真实读数、导出都不得进 Git。
