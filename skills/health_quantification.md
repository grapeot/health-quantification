# Health Quantification Skill

## 元数据

- 类型: Workflow
- 适用场景: 需要读取、整理、汇总、分析或记录个人健康数据时
- 项目路径: `adhoc_jobs/health_quantification/`（从 workspace 根目录调用时自动解析）

## 目标

CLI 提供结构化数据接口（JSON/text）和写入接口（record + illness），AI 负责所有分析、可视化和报告生成。AI 基于原始数据自由决定分析角度、报告结构和输出格式。报告以 Markdown 输出到 `docs/reports/`，图表以 PNG 输出到 `docs/assets/`。

## 架构

以 SQLite 为中心的架构：

1. **SQLite 数据库**：唯一事实来源（single source of truth）
2. **数据源层**（多源整合）：HealthKit（iOS app）、AI 手动记录（CLI record）、第三方硬件（Fitbit、三星等）
3. **写入层**：FastAPI server（批量同步，iOS/硬件）+ CLI `record`（单条写入，AI/手动）
4. **分析层**：Python CLI（只读查询），输出 JSON/text；AI 做分析和报告生成

## 数据类型

| 类别 | CLI 查询 | CLI 写入 | Ingest Endpoint |
|------|---------|---------|----------------|
| sleep | `sleep analyze/daily` | `record sleep` | `/ingest/sleep` |
| vitals | `vitals analyze/daily` | `record vitals` | `/ingest/vitals` |
| body | `body analyze/daily` | `record body` | `/ingest/body` |
| lifestyle | `lifestyle analyze/daily` | `record lifestyle` | `/ingest/lifestyle` |
| activity | `activity analyze/daily` | `record activity` | `/ingest/activity` |
| workouts | `workouts analyze/daily` | — | `/ingest/workouts` |
| illness | `illness list` | `illness record` | — |

### vitals metric_type 完整列表

| metric_type | unit | 说明 |
|-------------|------|------|
| resting_heart_rate | count/min | 静息心率（每日 1-2 次） |
| heart_rate | count/min | 连续心率（~5-10 分钟采样，运动时更频繁） |
| heart_rate_variability_sdnn | ms | HRV SDNN（主要在睡眠中测量） |
| respiratory_rate | count/min | 呼吸频率 |
| oxygen_saturation | % | 血氧 |
| active_energy_burned | kcal | 活动消耗（连续采样） |

### workouts 字段

workout_type 为 Apple Health `HKWorkoutActivityType` 名称（如 `fitnessGaming`、`running`、`traditionalStrengthTraining`、`HIIT`、`other`）。

## 关键边界

- 真正逻辑只放在 `src/health_quantification/`
- `scripts/health_quant` 是稳定 wrapper，不写业务逻辑
- iOS 代码只负责 HealthKit 采集和 HTTP POST，不做分析
- 不把真实个人健康数据提交到 git
- `docs/working.md` 记录变更与踩坑结论
- HealthKit 时间戳是 UTC，分析时需转换到用户时区（默认 `America/Los_Angeles`）
- 分析直接读 SQLite，**不需要后端运行**。如果今天或昨天没有数据，提醒用户先打开 iOS app 同步

## CLI 合同

### 查询

```bash
python -m health_quantification.cli doctor config
python -m health_quantification.cli db init
python -m health_quantification.cli sleep analyze --days 30 --format json|text
python -m health_quantification.cli sleep daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli sleep daily --last-night --format json|text
python -m health_quantification.cli vitals analyze --days 30 --metric resting_heart_rate --format json|text
python -m health_quantification.cli vitals daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli body analyze --days 30 --metric body_mass --format json|text
python -m health_quantification.cli body daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli lifestyle analyze --days 30 --metric dietary_caffeine --format json|text
python -m health_quantification.cli lifestyle daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli activity analyze --days 30 --metric step_count --format json|text
python -m health_quantification.cli activity daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli vitals analyze --days 30 --metric heart_rate --format json|text
python -m health_quantification.cli vitals analyze --days 30 --metric active_energy_burned --format json|text
python -m health_quantification.cli workouts analyze --days 30 --format json|text
python -m health_quantification.cli workouts daily --date YYYY-MM-DD --format json|text
python -m health_quantification.cli illness list --status active|resolved|all --format json|text
```

### 写入（AI 手动记录 / 对话触发）

```bash
python -m health_quantification.cli record lifestyle --metric dietary_caffeine --value 57 --unit mg --time "2026-03-31T12:00:00-07:00" --note "Costco Mexican Coke 500ml"
python -m health_quantification.cli record body --metric body_mass --value 75.5 --unit kg
python -m health_quantification.cli record vitals --metric resting_heart_rate --value 62 --unit "count/min"
python -m health_quantification.cli record activity --metric step_count --value 8500 --unit count
python -m health_quantification.cli record sleep --metric asleep_core --value 2 --unit stage --time "2026-03-31T22:30:00Z"
python -m health_quantification.cli illness record --label nasal_congestion --severity moderate --status active --start-time "2026-04-01T20:00:00-07:00" --symptom nasal_congestion --progression "2026-04-02: severe congestion" --note "Still sick"
```

`--time` 默认当前 UTC 时间。`--source` 默认 `ai_manual`。`--note` 存入 metadata。

`illness record` 用于记录区间型上下文，不要把生病硬塞进 `record lifestyle` 之类的 numeric sample。`illness` 记录的 canonical shape 是 episode：`label`、`severity`、`status`、`start_at`、`end_at`、`notes`、`metadata`（如 symptoms / progression）。

## AI 记录工作流

当用户提到健康相关事件时（如"我刚喝了杯咖啡"、"今天体重 74.5kg"、"我这两天在生病"），AI 应：

1. **识别意图**：这是一个需要记录的健康事件
2. **引导补全细节**：确认品牌、容量、时间、具体数值等
3. **查表换算**：从知识库或网上获取营养数据（咖啡因含量、卡路里等）
4. **选择正确写入面**：单点数值/样本走 CLI `record`；区间型 illness context 走 CLI `illness record`
5. **确认反馈**：告知用户已记录的数值和来源

### Illness episode 记录规则

- 生病是**区间型 context**，不是单个 metric，也不是 daily boolean。
- 优先记录 episode 的开始时间；结束前保持 `status=active` 且 `end_at=null`。
- 症状列表放 `--symptom`，病程变化放 `--progression`，主观补充说明放 `--note`。
- 如果用户只给了模糊标签，`label` 可以先用自由文本（如 `nasal_congestion`、`flu_like`、`unknown`），不要为了 taxonomy 过早复杂化。
- 后续恢复时，用同一个 `source_id` 或上层更新逻辑把 episode 标成 `resolved` 并补 `end_at`。

### 示例对话

用户："我刚喝了瓶可乐"
AI："帮你记录一下。确认几个细节：
- 哪种可乐？普通可口可乐（34mg/355ml）还是墨西哥可乐（Costco 500ml 玻璃瓶装，约 48mg 咖啡因）？
- 大概什么时间喝的？"

用户："墨西哥可乐，Costco 买的，12 点左右"
AI：记录完成。墨西哥可乐 500ml，约 48mg 咖啡因，时间 12:00 PT。

### 遇到新物品

当用户提到的食物/饮料不在知识库中时：

1. 上网搜集营养数据（优先 USDA、产品官网、权威营养数据库）
2. 向用户确认数据后，添加到知识库
3. 后续相同物品直接查表，不再重复搜集

## 知识库

常见食品/饮料的咖啡因含量参考（持续扩展）：

| 物品 | 规格 | 咖啡因 | 来源 |
|------|------|--------|------|
| 浅烘 Arabica double shot | 14g beans | ~150mg | 自行计算 |
| 墨西哥可乐 | 500ml 玻璃瓶 | ~48mg | Wikipedia / Caffeine Informer |
| 普通可口可乐 | 355ml | 34mg | Wikipedia |
| 健怡可乐（无咖啡因版） | 355ml | 0mg | 产品标签 |

## 分析与报告

AI 完全控制分析过程。典型工作流：

1. 调用 CLI 获取 JSON 数据
2. 基于数据自由分析（趋势、异常、对比、交叉关联等）
3. 生成可视化：使用 matplotlib 或调用 `artifacts/report.py` 生成 PNG 图表
4. 撰写 Markdown 报告，图片引用使用相对路径

### 用户偏好

用户有很强的机器学习和统计学背景。分析报告中：
- 可以使用精确的统计语言（偏相关系数、confidence interval、回归系数等）
- 包含最关键的数值 evidence，但不要堆砌所有统计结果
- 如果需要新的可视化，可以用 sub-agent 并行生成
- 数据不放进报告，只放结论和洞察

## 分析经验

- **相关性分析比单独看均值更有价值**。多维度交叉分析优先于单维度描述性统计。
- **Phase 2 的 `analyze` 需要指定 `--metric`**（如 `--metric resting_heart_rate`），不像 sleep 可以直接 `analyze --days 30`。workouts 的 `analyze` 不需要 `--metric`。
- **步数数据的处理**：CLI 返回的是每条记录的值，需要自己按天聚合（avg × count）得到日总步数。
- **HRV 的 Apple Watch 局限**：主要在睡眠中测量，短睡眠日数据可能不准确。
- **可视化用 matplotlib 直接画**比 `artifacts/report.py` 更灵活。
- **sleep 的 daily 分析中**：`total_sleep_hours` 包含主睡眠 + 午睡，`nap_hours` 单独报告午睡时长。bedtime/wake_time 只从主睡眠计算。

## 从不同目录调用

- **从项目目录** (`adhoc_jobs/health_quantification/`): 直接用 `.venv/bin/python -m health_quantification.cli ...`
- **从 workspace 根目录**: 用 `adhoc_jobs/health_quantification/.venv/bin/python -m health_quantification.cli ...`，或先 `cd` 到项目目录

## 已知限制

- Apple Watch 午睡追踪精度低，通常只有 1 条 `asleep_unspecified`
- `dietaryAlcohol` 用 raw value workaround，未经真机验证
- iOS ATS 使用 `NSAllowsArbitraryLoads`（个人项目 + Tailscale 加密内网）

## 踩坑记录（重要！）

### 时区与日期归属

- **所有 HealthKit 时间戳都是 UTC**。SQLite 里存的也是 UTC。
- **CLI 分析层（metrics.py、sleep.py）已经做了本地时区转换**：`_to_local_date()` 将 UTC 时间戳转为本地日期。vitals、activity、workouts、lifestyle、body 的 `analyze/daily` 都是正确的。
- **直接查数据库时不要用 UTC 日期判断"今天"**。例如 UTC 3/31 01:48 在 PT 是 3/30 18:48（昨天），直接 SQL 查 `date(start_at) = '2026-03-31'` 会把昨天的数据也拉出来。做分析时应该用 CLI 而不是直接查 DB。

### 睡眠日期归属与"昨晚睡得怎么样"

**这是最容易出错的地方。** sleep 的日期归属用 session 的 bedtime 日期（session 中最早 `start_at` 的本地日期），不是 `end_at` 的本地日期。一次 22:00 入睡、07:00 醒来的跨午夜睡眠，整个 session 归到 22:00 那天的日期上。

**"昨晚"的定义（严格约定）**：用户说"昨晚睡得怎么样"时，指的是**昨天晚上 8 点以后开始、今天早上结束的那一次夜间主睡眠**。不包括当天凌晨的补觉、白天的午睡、或更早的睡眠 session。

具体规则：
- "昨晚睡得怎么样" → 用 `sleep daily --last-night`，但**只看 main session 的指标**（bedtime、wake_time、deep/core/rem），忽略 `total_sleep_hours` 和 `nap_hours`（那里面混了同一天其他 session）
- 如果 main session 的 bedtime 在 20:00 之前，说明它可能不是昨晚的睡眠，需要人工判断
- "今天到现在怎么样" → vitals/lifestyle/activity 用 `--date 今天`，睡眠部分用 `--last-night` 的 main session
- **不要**把 `total_sleep_hours` 当作"昨晚睡了多久"，它包含了同一天所有 session（凌晨补觉 + 午睡 + 夜间主睡眠）
- **不要**直接用 SQL 查 `date(end_at)` 来做日期归属，因为会把跨午夜睡眠劈成两半

CLI 合同：
```bash
# 查昨晚的睡眠（推荐）
python -m health_quantification.cli sleep daily --last-night --format json
# 注意：返回的 total_sleep_hours 包含当天所有 session，bedtime/wake_time/deep/core/rem 只反映 main session

# 查某天的全部睡眠（含午睡）
python -m health_quantification.cli sleep daily --date 2026-03-31 --format json
```

### 睡眠分析

- **主睡眠与午睡已通过 session segmentation 分离**：同一天的 samples 按时间 gap（>2h）拆分为多个 session，asleep 时间最长的为主睡眠，其余为午睡。
- `total_sleep_hours` = 主睡眠 + 午睡。bedtime/wake_time/stage_hours 只从主睡眠计算。
- **bedtime/wake_time 的计算**：bedtime 只从 start_hour >= 16 的 sample 中取（傍晚/晚上），wake_time 只从 start_hour <= 12 的 sample 中取（清晨/上午）。如果 session 没有 evening sample（凌晨入睡），bedtime fallback 到 session 最早的 start_at。
- 纯午睡日（没有过夜睡眠）`has_nap=True` 但 `nap_hours=0.0`（因为唯一 session 就是 main session）。

### 睡眠窗口与 Vitals 交叉分析（重要踩坑！）

**绝对不要用 `GROUP BY date(start_at, '-7 hours')` 来生成 sleep window。** 这种写法会把跨午夜的两晚合并成一个 24 小时的巨大窗口（比如 3/27 07:06 到 3/28 07:12），导致白天清醒时间的 vital 被错误地标记为"sleep"。

正确做法是使用 session splitting 逻辑（和 `sleep.py` 的 `_split_into_sessions` 一致）：

1. 从 `sleep_samples` 取所有样本，按 `start_at` 排序
2. 相邻样本 gap > 2 小时则拆分为新 session
3. 过滤掉过短（<3h）和过长（>12h）的 session
4. 每个 session 的 `(min(start_at), max(end_at))` 才是真正的睡眠窗口

**反例（错误）**：
```sql
-- ❌ 会产生 24h 巨大窗口，sleep/awake 分类完全错乱
SELECT MIN(start_at), MAX(end_at)
FROM sleep_samples
GROUP BY date(start_at, '-7 hours')
```

**正例（正确）**：在 Python 中做 session splitting，过滤后用 timestamp range 做 `is_sleep()` 判断。直接写 SQL 无法可靠实现 session splitting。

### 配置与部署

- **`config.py` 的 `db_path` 使用绝对路径**（基于 `__file__` 解析项目根目录），不依赖 cwd。环境变量 `HEALTH_QUANT_DB_PATH` 可以覆盖。
- **CLI 和 FastAPI server 读写同一个 DB 文件**。远端（Tailscale）就是本机，SSH 只是连接 localhost。不存在"两个独立数据库"的情况。
- **pm2 重启后新代码才生效**。改了 Python 代码后需要 `pm2 restart health-quant-backend`。
- **iOS app 需要重新编译部署到真机才能获取新数据类型**。模拟器 build 不等于真机上有新代码。
