# 测试策略

## 目标

这个项目的测试要同时验证三件事：第一，配置与存储层的默认 contract 可用；第二，library 和薄 CLI 的接缝稳定；第三，未来真实健康数据接入不会被默认误触发。

## Unit tests

unit tests 只覆盖纯逻辑，不依赖真实健康数据或原生 adapter：

- 默认配置解析
- SQLite schema 初始化
- 日级 summary 的默认结构
- daily card SVG 输出的关键字段

这层测试必须快，能在空仓状态下直接运行。

## Mocked integration tests

mocked integration tests 用临时目录或临时数据库验证端到端接缝：

- `db init` 能创建数据库文件和表结构
- `summary daily` 能输出稳定 JSON schema
- `artifact daily-card` 能写出 SVG 文件
- CLI 参数能正确传递给 library

这层测试不访问真实 HealthKit，不读取真实个人数据。

## Live integration tests

live integration tests 只保留骨架，用于未来验证真实 adapter：

- 能加载真实 native exporter 输出
- 能 ingest 一份真实 Apple Health snapshot
- 能把真实 observation 转成 summary 与 artifact

这层测试默认必须 skip。只有显式设置 `HEALTH_QUANT_ENABLE_LIVE_TESTS=1`，并且调用方确认数据来源安全时，才允许运行。

## 运行方式

默认：

```bash
.venv/bin/python -m pytest -v
```

显式 live：

```bash
HEALTH_QUANT_ENABLE_LIVE_TESTS=1 .venv/bin/python -m pytest -v -m live_integration
```

## 手工 smoke checks

每次重要改动后，至少检查：

```bash
.venv/bin/python -m health_quantification.cli doctor config
.venv/bin/python -m health_quantification.cli db init
.venv/bin/python -m health_quantification.cli summary daily --date 2026-03-30 --format json
.venv/bin/python -m health_quantification.cli artifact daily-card --date 2026-03-30 --output docs/assets/daily_card.svg
```

如果当前环境没有真实 native adapter 或真实健康数据，只做默认测试和这些 smoke checks。
