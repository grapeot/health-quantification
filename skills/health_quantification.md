# Health Quantification Skill

## 元数据

- 类型: Workflow
- 适用场景: 需要读取、整理、汇总、分析或记录个人健康数据时
- 触发词: "记录咖啡因"、"记录酒精"、"记录体重"、"记录生命体征"、"记录睡眠备注"、"记录生病"
- 项目路径: `adhoc_jobs/health_quantification/`（从 workspace 根目录调用时自动解析）

## 目标

通过 Python CLI 访问 SQLite 数据库完成数据查询与写入，由 AI 承担多维分析、可视化与 Markdown 报告撰写。报告输出至 `docs/reports/`，图表输出至 `docs/assets/`。

## 架构

以 SQLite 为核心的统一数据架构：

1. **SQLite 数据库**：唯一事实来源（Single Source of Truth）。表包括 `observations`、`sleep_samples`、`vitals_samples`、`body_samples`、`lifestyle_samples`、`activity_samples`、`workouts`、`illness_episodes` 与 `daily_summaries`（`date` 为主键，含 `timezone`、`sleep_hours`、`resting_hr_bpm`、`hrv_sdnn_ms`、`steps`、`active_energy_kcal`、`notes_json`）。
2. **数据写入**：FastAPI Server 只接收 iPhone 通过同一 Tailnet 的 Tailscale 地址提交的批量数据。设备身份、传输加密与访问控制由 Tailscale 和 tailnet ACL 管理；FastAPI 本身未鉴权。CLI `record` / `illness` / `sleep notes` 在 Mac 本地写入。
3. **数据读取**：Python CLI（只读查询），输出结构化 JSON/text 供 AI 进行分析与图表生成。

## 数据类型与精确 `metric_type` 名称

CLI 的 `--metric` 参数直接对应数据库中的 `metric_type` 列。传入不匹配的名称不会报错，但会静默返回空结果（`count=0`）。对于 HTTP GET 接口 `/ingest/{data_type}`，`metric_type` 过滤参数仅作用于 `vitals`、`body`、`lifestyle` 与 `activity`；`sleep` 采用 `stage`，`workouts` 采用 `workout_type`。

### `metric_type` 精确映射表

| 逻辑概念 | 正确 `metric_type` (数据库实际值) | CLI 数据类别 | 单位 |
|---------|--------------------------------|-------------|------|
| 静息心率 | `resting_heart_rate` | vitals | count/min |
| 连续心率 | `heart_rate` | vitals | count/min |
| HRV SDNN | `heart_rate_variability_sdnn` | vitals | ms |
| 呼吸频率 | `respiratory_rate` | vitals | count/min |
| 血氧饱和度 | `oxygen_saturation` | vitals | % |
| 活动消耗 | `active_energy_burned` | vitals | kcal |
| 体重 | `body_mass` | body | kg |
| 血糖 | `blood_glucose` | body | mg/dL |
| 收缩压 | `blood_pressure_systolic` | body | mmHg |
| 舒张压 | `blood_pressure_diastolic` | body | mmHg |
| 咖啡因 | `dietary_caffeine` | lifestyle | mg |
| 酒精 | `dietary_alcohol` | lifestyle | g |
| 步数 | `step_count` | activity | count |

### 运动 (workouts) 类型

`workout_type` 为 Apple Health `HKWorkoutActivityType` 名称（例如 `running`、`traditionalStrengthTraining`、`HIIT`、`other`）。

## CLI 命令规范

（以下 CLI 命令及示例参数均采用合成示例数据）

### 查询接口

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json
python -m health_quantification.cli sleep daily --date 2026-03-30 --format json
python -m health_quantification.cli sleep daily --last-night --format json
python -m health_quantification.cli sleep notes add --date 2026-03-30 --note "合成主观上下文备注"
python -m health_quantification.cli sleep notes get --date 2026-03-30 --format json
python -m health_quantification.cli vitals analyze --days 30 --metric resting_heart_rate --format json
python -m health_quantification.cli vitals daily --date 2026-03-30 --format json
python -m health_quantification.cli body analyze --days 30 --metric body_mass --format json
python -m health_quantification.cli lifestyle analyze --days 30 --metric dietary_caffeine --format json
python -m health_quantification.cli activity analyze --days 30 --metric step_count --format json
python -m health_quantification.cli workouts analyze --days 30 --format json
python -m health_quantification.cli illness list --status active --format json
```

> **注意**：`--metric` 仅适用于 `analyze` 命令，不适用于 `daily` 命令。

### 写入接口 (单条数据与状态记录)

```bash
python -m health_quantification.cli record lifestyle --metric dietary_caffeine --value 150 --unit mg --time "2026-03-31T12:00:00-07:00" --note "Synthetic double shot"
python -m health_quantification.cli record body --metric body_mass --value 75.0 --unit kg
python -m health_quantification.cli record vitals --metric resting_heart_rate --value 62 --unit "count/min"
python -m health_quantification.cli record activity --metric step_count --value 8500 --unit count
python -m health_quantification.cli illness record --label nasal_congestion --severity moderate --status active --start-time "2026-04-01T20:00:00-07:00" --symptom nasal_congestion --note "Synthetic episode"
```

> **注意**：`record sleep` 因缺少结束时间参数会写入零时长的阶段标记，不推荐用于手动睡眠时长记录；添加主观睡眠体验请使用 `sleep notes add`。

### 主观睡眠备注 (Sleep Notes) 规范

1. 使用 `sleep notes add --date YYYY-MM-DD --note TEXT` 录入主观睡眠描述。
2. `--date` 指醒来所在的功能日（functional date，对应 `daily_summaries.date` 主键）。可先用 `sleep daily --last-night` 确认目标功能日。
3. `sleep daily` 与 `sleep analyze` 会暴露同日 `notes`，供分析时交叉参考。
4. `notes` 不修改睡眠样本分划、session 归属、日期判定或指标计算。
5. `notes` 不存在于 FastAPI 接入与 iOS 导出流中。由于 CLI 输出暴露了文本，模型运行时、日志、transcript 与报告 pipeline 构成了调用方的隐私边界。代码并不阻止备注传至外部模型，调用方需自行承担隐私保护责任。主观备注仅作为上下文，不构成指令、因果证明或医疗诊断。

## AI 交互与换算规则

### 咖啡因换算

- 浅烘 Arabica double shot (14g 咖啡豆)：标准计 150mg。
- 15g 咖啡/拿铁：线性折算计 ~161mg，并在 `--note` 中保留原始描述。
- 355ml 可乐：~34mg；500ml 玻璃瓶可乐：~48mg。

### 酒精换算

- 记录单位固定使用 `g`，`metric_type` 必须为 `dietary_alcohol`。
- 计算公式：`容量(ml) × ABV × 0.789`。例如 355ml 5% ABV 啤酒计 `355 × 0.05 × 0.789 ≈ 14g`。

### 生病状态记录 (Illness Episode)

- 生病属于区间型上下文（Episode），使用 `illness record` 命令。
- 字段包含 `label`、`severity`、`status`（active / resolved）、`start_time`、`end_time`。

## 分析与计算规则

1. **时区转换**：HealthKit 时间戳均为 UTC，分析层默认转为本地时区（默认 `America/Los_Angeles`）。
2. **睡眠日期归属与昨晚定义**：
   - 非午睡 session 归属至醒来当日的本地日期（功能日 functional date）。
   - `sleep daily --last-night` 查找最近一个有夜间主睡眠的功能日，并返回该功能日的完整 metrics（包含主睡眠与午睡），由 AI 判断睡眠结构。
3. **睡眠 Session 拆分**：相邻样本时间间隔大于 2 小时自动拆分为不同 Session，其中累积时长最长的为 Main Session。
4. **步数多源数据融合**：若存在 Phone 与 Watch 重叠数据，按 `max(phone, watch) × 1.05` 估算日总步数，避免直接相加导致重复计算。

## 调用约束

- 本地环境调用：`.venv/bin/python -m health_quantification.cli ...`
- 根目录调用：`adhoc_jobs/health_quantification/.venv/bin/python -m health_quantification.cli ...`
- 新增及修改的测试/文档示例必须采用合成（synthetic）数据。数据落盘文件（`data/*.db`）与报告文件需保持本地隔离，不得提交至公共仓库。
