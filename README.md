# sources

[![CI](https://github.com/20070316lbw-netizen/sources/actions/workflows/ci.yml/badge.svg)](https://github.com/20070316lbw-netizen/sources/actions/workflows/ci.yml)

个人量化数据抓取包，为 Fama-French 三因子(FF3)复现准备原始数据。

**这个仓库只做一件事：从各数据源抓取原始数据，并做字段级的初步清洗**
（改列名、转类型、丢弃明显无效的行）。不做跨数据源合并、不计算任何因子
或指标、也不做任何形式的本地存储/缓存——这些留给使用方，或者以后独立
出去的存储层仓库。

## 安装

作为私有 GitHub 仓库，在其他项目里用 `uv add` 直接从 git 安装：

```bash
# 装最新 main
uv add "git+https://github.com/20070316lbw-netizen/sources.git"

# 推荐: 装一个打好 tag 的版本, 避免上游改动悄悄影响你的项目
uv add "git+https://github.com/20070316lbw-netizen/sources.git@v0.1.0"
```

## 快速开始

```python
from sources import get_sp500_constituents, get_prices, get_fundamentals

# 当前 S&P 500 成分股: [ticker, name]
universe = get_sp500_constituents()

# 历史行情(长表): [date, ticker, open, high, low, close, adj_close, volume]
prices = get_prices(universe["ticker"].tolist()[:20], start="2020-01-01", end="2024-01-01")

# 基本面(长表): [ticker, concept, period_start, period_end,
#               duration_days, numeric_value, fiscal_period, fiscal_year]
# 需要先设置 EDGAR_IDENTITY, 见下方"环境变量"
fundamentals = get_fundamentals("AAPL")
```

## 环境变量

`get_fundamentals` / `get_fundamentals_batch` 依赖 SEC EDGAR，SEC 要求调用方
提供身份标识，通过环境变量设置：

```bash
export EDGAR_IDENTITY="Your Name your@email.com"
```

不设置的话会直接抛 `RuntimeError` 并提示怎么设置，不会卡在交互式输入上。

## 各数据源

| 模块 | 数据源 | 函数 | 备注 |
| --- | --- | --- | --- |
| `constituents` | Wikipedia | `get_sp500_constituents()` | 只有当前成分股；历史变更表暂未实现 |
| `prices` | Yahoo Finance (yfinance) | `get_prices(tickers, start, end)` | 支持单个或多个 ticker |
| `fundamentals` | SEC EDGAR (edgartools) | `get_fundamentals(ticker)` / `get_fundamentals_batch(tickers)` | 默认抓 `StockholdersEquity` 和 `CommonStockSharesOutstanding`，可通过 `concepts` 参数覆盖 |

架构上的设计取舍和为什么这么分层，见 [DESIGN.md](DESIGN.md)。

## 开发

```bash
uv sync
uv run ruff check .
uv run pytest
```

测试全部通过 mock 隔离外部网络调用（Wikipedia / yfinance / EDGAR），不需要
真实网络也能跑；CI（见 `.github/workflows/ci.yml`）在 push/PR 到
`main`/`master` 时会跑同样这两步。
