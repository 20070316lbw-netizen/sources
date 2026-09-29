# sources

`sources` 是一个量化数据抓取包，提供 S&P 500 和 A 股的日频、小时频行情接口，以及成员名单、交易日历和相关市场数据组件。当前版本为 **0.1.1**。

## 0.1.1

- 按市场组织底层组件，并提供 `DailySp500`、`HourSp500`、`DailyAShare`、`HourAShare` 四个组合接口。
- 增加 S&P 500 交易日历，以及分开的 `update_sp500_members()`、`update_ashare_members()` 手动名单更新入口。
- 保留旧模块导入路径兼容；A 股小时线清洗行为保持原有口径。

## 安装

```bash
uv add "sources @ git+https://github.com/20070316lbw-netizen/sources.git@v0.1.1"
```

## 快速开始

```python
from sources import DailyAShare, DailySp500, HourAShare, HourSp500

sp500 = DailySp500()
sp500_members = sp500.members()  # 读取本地缓存的当前 S&P 500 成员
sp500_prices = sp500.prices()  # 默认抓取成员股最近十年的日线
sp500_calendar = sp500.calendar("2025-01-01", "2025-01-31")

ashare = DailyAShare()
ashare_prices = ashare.prices(start="2025-01-01", end="2025-01-31")
ashare_calendar = ashare.calendar("2025-01-01", "2025-01-31")

ashare_hourly = HourAShare()
hour_bars = ashare_hourly.prices(start="2025-01-01", end="2025-01-31")  # BaoStock 60 分钟线

sp500_hourly = HourSp500()
hour_prices = sp500_hourly.prices(start="2025-01-01", end="2025-01-31")  # yfinance 小时线
```

四个组合类默认从成员名单缓存读取代码。调用方可通过 `tickers` 参数显式指定代码，避免使用默认名单。

## 手动更新成员名单

名单读取与名单更新是独立操作。缓存缺失时，读取方法会尝试初始化；需要手动更新时分别调用：

```python
from sources import update_ashare_members, update_sp500_members

sp500_members = update_sp500_members()  # 从 Wikipedia 更新当前及历史成分缓存
ashare_members = update_ashare_members()  # 从 BaoStock 更新沪深 300 成分缓存
```

A 股更新函数可传入 `index`，目前支持 `"hs300"` 和 `"000300.SH"`。缓存不会自动过期，请在需要时手动更新。设置 `SOURCES_DATA_DIR` 可指定 A 股缓存目录和 S&P 500 历史缓存目录；未设置时，A 股名单写入 `~/.cache/sources/ashare/`，S&P 500 历史数据使用包内 `sp500/cache/changelog/data/`。

## 接口说明

| 接口 | 主要方法 |
| --- | --- |
| `DailySp500` | `members()`、`prices()`、`calendar()`、`risk_free_rate()`、`fundamentals()`、`fundamentals_batch()` |
| `HourSp500` | `members()`、`prices()`、`calendar()` |
| `DailyAShare` | `members()`、`prices()`、`bars()`、`calendar()`、`stock_basic()` |
| `HourAShare` | `members()`、`prices()` |

`DailySp500.prices()` 未指定 `start` 时默认请求最近十年。`HourSp500.prices()` 使用 yfinance 小时频数据，其可用历史范围受 Yahoo Finance 限制。A 股小时类固定抓取 BaoStock 60 分钟线，底层 `get_intraday_bars()` 仍支持 5、15、30、60 分钟频率。

美股交易日历使用 XNYS 交易所日历。`calendar(start, end)` 返回区间内每个自然日的 `date` 和 `is_open` 两列；`end` 默认是今天。

## 数据与限制

- 行情结果由调用方接收，本包不持久化行情数据。
- S&P 500 默认使用当前成员名单回抓历史价格，仍存在幸存者偏差；十年回溯范围不能消除该偏差。
- S&P 500 日线可用范围受 Yahoo Finance 数据限制，个别代码可能无数据；批量抓取会跳过无数据标的并返回其他结果。
- A 股默认成员名单为沪深 300 快照；历史行情和分钟线的字段清洗行为沿用 BaoStock 实现。
- 旧版 `sources.cn`、`sources.prices`、`sources.riskfree`、`sources.sec` 等导入路径保留兼容。新项目建议从 `sources`、`sources.ashare` 和 `sources.sp500` 导入。

## 开发

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
```

0.1.1 发布前检查：全套 133 项测试通过，Ruff 检查通过。2026-09-29 对成员名单更新、两地日历、日线/小时线、A 股日线附加字段、证券资料、FRED 利率和 SEC 基本面做了短区间真实调用，均成功返回数据。
