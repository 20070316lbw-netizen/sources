# sources

`sources` 是一个量化数据抓取包，提供 S&P 500 的日频、小时频行情接口，以及成员名单、交易日历和相关市场数据组件。当前版本为 **0.1.1**。

> 本分支已移除 A 股(BaoStock)相关的抓取接口与组合类，只保留 S&P 500 / SEC / FRED 数据源。

## 0.1.1

- 按市场组织底层组件，并提供 `DailySp500`、`HourSp500` 两个组合接口。
- 增加 S&P 500 交易日历，以及 `update_sp500_members()` 手动名单更新入口。
- 保留旧模块导入路径兼容。

## 安装

```bash
uv add "sources @ git+https://github.com/20070316lbw-netizen/sources.git@v0.1.1"
```

## 快速开始

```python
from sources import DailySp500, HourSp500

sp500 = DailySp500()
sp500_members = sp500.members()  # 读取本地缓存的当前 S&P 500 成员
sp500_prices = sp500.prices()  # 默认抓取成员股最近十年的日线
sp500_calendar = sp500.calendar("2025-01-01", "2025-01-31")

sp500_hourly = HourSp500()
hour_prices = sp500_hourly.prices(start="2025-01-01", end="2025-01-31")  # yfinance 小时线
```

两个组合类默认从成员名单缓存读取代码。调用方可通过 `tickers` 参数显式指定代码，避免使用默认名单。

## 手动更新成员名单

名单读取与名单更新是独立操作。缓存缺失时，读取方法会尝试初始化；需要手动更新时调用：

```python
from sources import update_sp500_members

sp500_members = update_sp500_members()  # 从 Wikipedia 更新当前及历史成分缓存
```

缓存不会自动过期，请在需要时手动更新。设置 `SOURCES_DATA_DIR` 可指定 S&P 500 历史缓存目录；未设置时使用包内 `sp500/cache/changelog/data/`。

## 接口说明

| 接口 | 主要方法 |
| --- | --- |
| `DailySp500` | `members()`、`prices()`、`calendar()`、`risk_free_rate()`、`fundamentals()`、`fundamentals_batch()` |
| `HourSp500` | `members()`、`prices()`、`calendar()` |

`DailySp500.prices()` 未指定 `start` 时默认请求最近十年。`HourSp500.prices()` 使用 yfinance 小时频数据，其可用历史范围受 Yahoo Finance 限制。

美股交易日历使用 XNYS 交易所日历。`calendar(start, end)` 返回区间内每个自然日的 `date` 和 `is_open` 两列；`end` 默认是今天。

## 数据与限制

- 行情结果由调用方接收，本包不持久化行情数据。
- S&P 500 默认使用当前成员名单回抓历史价格，仍存在幸存者偏差；十年回溯范围不能消除该偏差。
- S&P 500 日线可用范围受 Yahoo Finance 数据限制，个别代码可能无数据；批量抓取会跳过无数据标的并返回其他结果。
- 旧版 `sources.prices`、`sources.riskfree`、`sources.sec` 等导入路径保留兼容。新项目建议从 `sources` 和 `sources.sp500` 导入。

## 开发

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
```

0.1.1 发布前检查：全套 90 项测试通过，Ruff 检查通过。2026-09-29 对成员名单更新、交易日历、日线/小时线、FRED 利率和 SEC 基本面做了短区间真实调用，均成功返回数据。
