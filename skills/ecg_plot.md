# ECG Plot

## 元数据

- 类型: Workflow
- 适用场景: 已经有 `ecg export` 写出的 JSON，需要按原始电压画 6 条 5 秒心电图，并核对点数、时间与电压是否完整
- 触发词: "ecg plot"、"画心电图"、"心电图网格"
- 项目路径: `adhoc_jobs/health_quantification/`

## 边界

这个命令只读一份已经导出的 JSON，不查询数据库，也不调用 `ecg export`。它不是诊断，不解释心律，不计算间期。

导出、入库和 iOS 采集仍走 [`health_quantification.md`](health_quantification.md)；本 skill 只负责对已经导出的单条记录绘图。

波形、完整性摘要和 PNG 都是私有产物。仓库内的输入输出只能放在 `data/` 下，并且写入路径必须已经被 gitignore，实际应使用 `data/exports/` 或 `data/raw/` 里的文件。不要把 PNG、完整性 JSON 或电压写进测试、文档或可追踪源码。
输出文件名须是新的路径；如果图或完整性报告已经存在，命令会拒绝覆盖。仓库外的输出路径不受本项目 `.gitignore` 保护，使用真实波形前须自行确认落点私有。

## 命令

matplotlib 是可选依赖。缺少时命令会失败并提示安装，不会把电压打到终端。

```bash
cd adhoc_jobs/health_quantification
uv pip install --python .venv/bin/python -e '.[plot]'
.venv/bin/python -m health_quantification.ecg_plot \
  --input data/exports/synthetic_ecg.json \
  --output data/exports/synthetic_ecg.png \
  --integrity-output data/exports/synthetic_ecg_integrity.json
```

标准输出只有状态、比例提示和路径。绘制前不打印电压样本、source id 或时间戳。测量范围只写进完整性 JSON。

## 图和核对

通过核对后才画 PNG。核对失败时仍写完整性 JSON，但不写 PNG，避免把缺样、截断或坏点画成一条看起来完整的曲线。

核对项：

- `voltage_count`、`returned_points`、`number_of_voltage_measurements` 与电压数组长度一致，`truncated` 为 false，`voltage_status` 为 complete
- 时间严格递增，间隔与 `sampling_frequency_hz` 一致
- 时间和电压都不是 null，也不是非有限数
- `voltage_unit` 为 V
- 全部样本落在 0 到 30 秒内。超出 6 条 5 秒窗口的点不会被裁掉，而是拒绝作图

图固定为 6 条 5 秒。时间网格是 25 mm/s，小格 0.04 秒，主格 0.2 秒。电压在放得下时用 10 mm/mV，小格 0.1 mV，主格 0.5 mV。放不下时降低显示比例，纵轴仍包住全部电压。不做滤波、平滑、归一化或裁剪。终端会提示该图只适合屏幕查看，不保证打印比例。
