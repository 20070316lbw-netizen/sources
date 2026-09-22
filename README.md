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
    get_all_historical_sp500_tickers,
    get_historical_sp500_constituents,
    get_prices,
    get_risk_free_rate,
    get_sp500_changelog,
    get_sp500_constituents,
    update_cache_from_web,
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

### 历史成分股(点时反推)

回测时用当前名单去跑历史会引入幸存者偏差。下面这组函数依赖一份本地缓存,
**首次使用先跑一次 `update_cache_from_web()`** (会抓 Wikipedia 并落盘):

```python
update_cache_from_web()                              # 生成/刷新本地缓存

get_historical_sp500_constituents("2020-01-01")      # 该时点的代码列表
get_historical_sp500_constituents(                   # 带名称/板块的 DataFrame
    "2020-01-01", return_type="dataframe"
)
get_all_historical_sp500_tickers()                   # 含已退市/已剔除的全部标的
get_sp500_changelog("2020-01-01", "2023-12-31")      # 区间内的增删明细(闭区间)
```

数据来自 Wikipedia 的 "Selected changes to the list of S&P 500 components"
表。**注意它是选择性记录、并不完整**, 越往前缺得越多: 近几年的反推结果可信度
较高, 时间越久远偏差越大。要做严肃的长周期回测, 该换 CRSP 之类的正式成分股
历史库。

## 环境变量

`get_roe` / `get_roe_batch` 依赖 SEC EDGAR, 需要通过环境变量设置调用方身份
标识——SEC 要求所有 sec.gov 请求都携带身份：

```bash
export EDGAR_IDENTITY="Your Name your@email.com"
```

如果没有设置的话会直接抛 `RuntimeError` 并提示怎么设置.

历史成分股缓存默认写在包内的 `src/sources/constituents_changelog/data/`。包被装
到只读目录(或希望多个项目共用一份缓存)时, 用 `SOURCES_DATA_DIR` 指定位置——
读和写走的是同一个解析函数, 设一次即可:

```bash
export SOURCES_DATA_DIR="$HOME/.cache/sources"
```

## 各数据源

| 模块 | 数据源 | 函数 | 备注 |
| --- | --- | --- | --- |
| `constituents` | Wikipedia | `get_sp500_constituents()` | 当前成分股名单 `[ticker, name]` |
| `constituents_changelog` | Wikipedia | `get_historical_sp500_constituents(as_of)` / `get_sp500_changelog()` / `get_all_historical_sp500_tickers()` | 点时反推历史名单, 规避幸存者偏差；依赖 `update_cache_from_web()` 生成的本地缓存 |
| `prices` | Yahoo Finance (yfinance) | `get_prices(tickers, start, end)` | 支持单个或多个 ticker |
| `riskfree` | FRED (pandas-datareader) | `get_risk_free_rate(start, end)` | 默认抓一个月期国债利率(`DGS1MO`)，年化百分比原始口径，可通过 `series` 参数换成其他 FRED 序列 |
| `roe` | SEC EDGAR (edgartools) | `get_roe(ticker, years=1)` / `get_roe_batch()` | 默认计算 `first_50.py` 中的 50 只股票；批量模式下单只失败不会中断其余股票；需要设置 `EDGAR_IDENTITY` |

## ROE

计算口径：

```text
ROE = 净利润 / 平均股东权益
平均股东权益 = (期初股东权益 + 期末股东权益) / 2
```

净利润与股东权益的会计科目按 `map/field_mapping_50.py` 里的优先级列表逐个尝试,
**优先选用单个科目就能覆盖全部年度的那一个**：不同科目对应不同会计口径(如母公司
口径的 `AllEquityBalance` vs 含少数股东权益的合并口径
`AllEquityBalanceIncludingMinorityInterest`)，期初取 A 口径、期末取 B 口径算出来
的 ROE 没有可比性。只有在没有任何单一科目覆盖全部年度时才按优先级拼接，并打
warning 提示该列是拼出来的。个别用非标科目的股票可以在 `TICKER_CONCEPT_MAPPING`
里单独指定优先级。返回列如下：

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

ruff 的规则集写死在 `pyproject.toml` 的 `[tool.ruff.lint]` 里、版本在
`pyproject.toml` 中锁了上界，CI 用 `uv sync --locked` 安装——三者一起保证本地和
CI 的 lint 结果一致，不会因为 ruff 升级默认规则集而突然全红。
