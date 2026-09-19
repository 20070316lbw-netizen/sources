# sources

[![CI](https://github.com/20070316lbw-netizen/sources/actions/workflows/ci.yml/badge.svg)](https://github.com/20070316lbw-netizen/sources/actions/workflows/ci.yml)

个人量化数据抓取包, 准备原始数据。

**从各数据源抓取原始数据、做字段级初步清洗，并基于 SEC 年报计算 ROE**

基础数据模块负责改列名、转类型和丢弃明显无效的行，不做跨数据源合并或
本地存储。`roe` 模块额外提供净资产收益率计算。

## 安装

作为私有 GitHub 仓库，在其他项目里用 `uv add` 直接从 git 安装：

```bash
# 装最新 main
uv add "git+https://github.com/20070316lbw-netizen/sources.git"

# 推荐: 装一个打好 tag 的版本, 避免上游改动的影响
uv add "git+https://github.com/20070316lbw-netizen/sources.git@v0.1.0"
```

## 快速开始

```python
from sources import (
    get_sp500_constituents,
    get_prices,
    get_risk_free_rate,
)
from sources.roe import get_roe, get_roe_batch

# 当前 S&P 500 成分股: [ticker, name]
universe = get_sp500_constituents()

# 历史行情(长表): [date, ticker, open, high, low, close, adj_close, volume]
prices = get_prices(universe["ticker"].tolist()[:20], start="2020-01-01", end="2024-01-01")

# 无风险利率(长表): [date, series, value], 默认 FRED 一个月期国债利率
riskfree = get_risk_free_rate(start="2020-01-01", end="2024-01-01")

# 单家公司最近一年的 ROE, 需要先设置 EDGAR_IDENTITY, 见下方"环境变量"
roe = get_roe("AAPL")

# src/sources/map/first_50.py 中 50 只目标股票的 ROE
roe_50 = get_roe_batch()
```

## 环境变量

`get_roe` / `get_roe_batch` 依赖 SEC EDGAR, 需要通过环境变量设置调用方身份
标识——SEC 要求所有 sec.gov 请求都携带身份：

```bash
export EDGAR_IDENTITY="Your Name your@email.com"
```

如果没有设置的话会直接抛 `RuntimeError` 并提示怎么设置.

## 各数据源

| 模块 | 数据源 | 函数 | 备注 |
| --- | --- | --- | --- |
| `constituents` | Wikipedia | `get_sp500_constituents()` | 只有当前成分股；历史变更表暂未实现 |
| `prices` | Yahoo Finance (yfinance) | `get_prices(tickers, start, end)` | 支持单个或多个 ticker |
| `riskfree` | FRED (pandas-datareader) | `get_risk_free_rate(start, end)` | 默认抓一个月期国债利率(`DGS1MO`)，年化百分比原始口径，可通过 `series` 参数换成其他 FRED 序列 |
| `roe` | SEC EDGAR (edgartools) | `get_roe(ticker, years=1)` / `get_roe_batch()` | 默认计算 `first_50.py` 中的 50 只股票；批量模式下单只失败不会中断其余股票；需要设置 `EDGAR_IDENTITY` |

## ROE

计算口径：

```text
ROE = 净利润 / 平均股东权益
平均股东权益 = (期初股东权益 + 期末股东权益) / 2
```

净利润优先使用 `NetIncomeToCommonShareholders`，缺失时按年度退回
`NetIncome`；股东权益使用 `AllEquityBalance`。返回列如下：

| 列 | 含义 |
| --- | --- |
| `ticker` | 股票代码 |
| `period_end` | 财年截止日 |
| `net_income` | 当年净利润 |
| `beginning_equity` | 期初股东权益 |
| `ending_equity` | 期末股东权益 |
| `average_equity` | 平均股东权益 |
| `roe` | ROE 小数值，例如 `0.24` |
| `roe_percent` | ROE 百分比，例如 `24.0` |

## 开发

```bash
uv sync
uv run ruff check .
uv run pytest
```

测试全部通过 mock 隔离外部网络调用（Wikipedia / yfinance / EDGAR / FRED），不需要
真实网络也能跑；CI（见 `.github/workflows/ci.yml`）在 push/PR 到
`main`/`master` 时会跑同样这两步。
