# sources

[![CI](https://github.com/20070316lbw-netizen/sources/actions/workflows/ci.yml/badge.svg)](https://github.com/20070316lbw-netizen/sources/actions/workflows/ci.yml)

个人量化数据抓取包, 准备原始数据。

**从各数据源抓取原始数据、做字段级初步清洗；美股基本面直接请求 SEC 官方接口，带申报日期，可做点时(PIT)数据**

基础数据模块负责改列名、转类型和丢弃明显无效的行，不做跨数据源合并或
本地存储。`sec` 子包提供带申报日期的美股基本面, `roe` 模块在其上计算净资产收益率。

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

# 单家公司最近一年的 ROE(数据来自 SEC 10-K, 见下方"SEC 基本面")
roe = get_roe("AAPL")

# src/sources/map/first_50.py 中 50 只目标股票的 ROE
roe_50 = get_roe_batch()
```

### SEC 基本面(点时, 直接请求 SEC, 不依赖 edgartools)

```python
from sources.sec import FIELDS, get_fundamentals, get_fundamentals_batch

facts = get_fundamentals("AAPL")                         # 全部标准字段, 一次请求
facts = get_fundamentals("AAPL", ["revenue", "net_income", "total_equity"])
batch = get_fundamentals_batch(["AAPL", "MSFT", "BRK-B"])  # 单只失败只打 warning
old = get_fundamentals("TWTR", cik=1418091)              # 已退市: 直接给 CIK
```

数据源是 SEC 的 XBRL companyfacts 接口
(`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`), 一家公司一次
请求拿到 2009 年以来所有 10-K / 10-Q(含修订版)里的数值。返回长表, 一行是
"某份申报文件对某个期间报告的某个标准字段的值":

| 列 | 含义 |
| --- | --- |
| `ticker` / `cik` | 代码(原样, 如 `BRK-B`) / 10 位 CIK |
| `field` / `concept` | 标准字段名 / 实际命中的 XBRL 科目(如 `us-gaap:Revenues`) |
| `unit` | `USD` / `shares` / `USD/shares` |
| `period_start` / `period_end` | 期间起止; 时点型(资产负债表)的 `period_start` 为空 |
| `period_months` | 0 = 时点, 3 / 6 / 9 / 12 = 期间长度(52/53 周财年也归到这几档) |
| `value` | 数值 |
| `fy` / `fp` / `form` | **申报文件**的财年 / 期间 / 表单(不一定是这行数据本身的期间) |
| `accn` / `filed` | 文件号 / 申报日——点时查询就按 `filed` 做 as-of |
| `derived` | 是否为推导出来的单季值, 见下 |

要点:

- **所有版本都保留**: 同一期间在当期报告、之后作为比较期、重述时各出现一次,
  `accn`/`filed` 不同。存进 liudb 后按 `filed <= t` 取最新版本, 就是 t 时点
  真实能看到的数字。
- **标准字段**见 `sources.sec.FIELDS`(收入、毛利、营业利润、净利润、EPS、总资产、
  权益、现金、负债、经营现金流、资本开支、分红、回购等 25 个), 每个字段按优先级
  列了候选科目, 同一份文件内按优先级取一个。个股用非标科目时在
  `sources.sec.TICKER_FIELD_OVERRIDES` 里覆盖。
- **单季推导**: 10-Q 的现金流量表只有年初至今累计值, 10-K 只有全年值, 很多单季
  (Q4、现金流的 Q2/Q3)没有直接报告。对金额类字段用"本份文件的累计值 − 当时已知
  的上一个累计值"推出 3 个月值, `derived=True`, `filed` 沿用被减数所在文件,
  不引入未来数据。EPS、加权股数不推导。
- **ticker → CIK** 用 SEC 的 `company_tickers.json`, 只覆盖当前仍在申报的公司;
  已退市/被收购的传 `cik=`。控股重组换了申报主体的(Alphabet、迪士尼、
  ExxonMobil)前身 CIK 登记在 `sources.sec.PREDECESSOR_CIKS`, 会自动一并抓取。
- **限速**: SEC 上限每秒 10 次, 这里全局限在约每秒 8 次, 429 / 5xx 自动退避重试。
  S&P 500 全量约 500 次请求, 几分钟。

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

### A 股(沪深300 日线, 数据源 BaoStock)

```python
from sources.cn import (
    get_cn_daily_bars,
    get_cn_index_members,
    get_cn_index_members_history,
    get_cn_prices,
    get_cn_stock_basic,
    get_cn_trade_calendar,
    session,
)

hs300 = get_cn_index_members("hs300", "2024-07-01")          # 某天的成分快照
history = get_cn_index_members_history("hs300", "2015-01-01") # 月度快照拼成的历史成分

with session():  # 批量调用时只登录一次 BaoStock
    tickers = hs300["ticker"].tolist()                        # ['000001.SZ', ..., '600519.SH']
    prices = get_cn_prices(tickers, start="2020-01-01")      # 列与 get_prices 相同
    bars = get_cn_daily_bars(tickers, start="2020-01-01")    # 另含停牌/ST/成交额等
    calendar = get_cn_trade_calendar("2015-01-01")           # [date, is_open]
    basic = get_cn_stock_basic()                              # 上市/退市日期, 含已退市
```

约定:

- 代码统一为 `600519.SH` / `000001.SZ` / `430047.BJ`; 入参也接受 `sh.600519`、
  `600519`(按首位推断交易所; 指数代码请显式带后缀)。
- `close` 是**不复权**价, `adj_close` 是**后复权**价。选后复权是因为它的历史值
  不会随新的除权而变化, 增量入库安全; 算出的收益率与前复权一致。
- A 股函数的 `end` 是**闭区间**(含当天), 与 BaoStock、liudb 读取口径一致;
  美股 `get_prices` 的 `end` 沿用 yfinance 的开区间。
- 停牌日保留(`is_suspended=True`, close 等于前收, volume 为 0), 方便下游构造
  可交易掩码。volume 单位为股, amount 为元。
- BaoStock 是进程级全局会话, **不是线程安全的**, 不要多线程并发调用。

## 环境变量

SEC 要求所有 sec.gov 请求在 User-Agent 里带上调用方身份(名字 + 邮箱)。默认使用
`liu 20070316lbw@gmail.com`, 需要换成别的身份时设置:

```bash
export EDGAR_IDENTITY="Your Name your@email.com"
```

历史成分股缓存默认写在包内的 `src/sources/constituents_changelog/data/`。包被装
到只读目录(或希望多个项目共用一份缓存)时, 用 `SOURCES_DATA_DIR` 指定位置——
读和写走的是同一个解析函数, 设一次即可:

```bash
export SOURCES_DATA_DIR="$HOME/.cache/sources"
```

A 股部分默认匿名登录 BaoStock。如果申请了 API Key, 设置后会在登录前自动带上:

```bash
export BAOSTOCK_API_KEY="bs-..."
```

## 各数据源

| 模块 | 数据源 | 函数 | 备注 |
| --- | --- | --- | --- |
| `constituents` | Wikipedia | `get_sp500_constituents()` | 当前成分股名单 `[ticker, name]` |
| `constituents_changelog` | Wikipedia | `get_historical_sp500_constituents(as_of)` / `get_sp500_changelog()` / `get_all_historical_sp500_tickers()` | 点时反推历史名单, 规避幸存者偏差；依赖 `update_cache_from_web()` 生成的本地缓存 |
| `prices` | Yahoo Finance (yfinance) | `get_prices(tickers, start, end)` | 支持单个或多个 ticker |
| `riskfree` | FRED (pandas-datareader) | `get_risk_free_rate(start, end)` | 默认抓一个月期国债利率(`DGS1MO`)，年化百分比原始口径，可通过 `series` 参数换成其他 FRED 序列 |
| `sec` | SEC XBRL companyfacts | `get_fundamentals(ticker, fields)` / `get_fundamentals_batch(...)` / `get_company_facts(...)` | 标准化基本面长表, 带申报日期, 供 liudb 做点时数据 |
| `roe` | SEC XBRL companyfacts | `get_roe(ticker, years=1)` / `get_roe_batch()` | 基于 `sources.sec`; 默认计算 `first_50.py` 中的 50 只股票；批量模式下单只失败不会中断其余股票 |
| `cn.prices` | BaoStock | `get_cn_prices(tickers, start, end)` / `get_cn_daily_bars(...)` | A 股日线; 前者列同 `get_prices`, 后者多出停牌/ST/成交额/换手/涨跌幅 |
| `cn.index_members` | BaoStock | `get_cn_index_members(index, date)` / `get_cn_index_members_history(...)` | 指数成分快照, 目前只支持沪深300 |
| `cn.trade_calendar` | BaoStock | `get_cn_trade_calendar(start, end)` | A 股交易日历 |
| `cn.stock_basic` | BaoStock | `get_cn_stock_basic(tickers=None)` | 证券基本资料, 含上市/退市日期 |

## ROE

计算口径：

```text
ROE = 净利润 / 平均股东权益
平均股东权益 = (期初股东权益 + 期末股东权益) / 2
```

数据来自 `sources.sec`, 每个财年的净利润、期末权益、期初权益都取自**同一份
10-K**(10-K 的资产负债表同时列出本年末和上年末), 保证分子分母口径一致; 同一财年
有多份"本年"申报(如 10-K/A 重述)时取最新的。净利润优先取归母口径
`NetIncomeLoss`, 股东权益优先取归母口径 `StockholdersEquity`, 没有时才退到含
少数股东权益的合并口径; 期初/期末用了不同科目时会打 warning。个股可在
`sources.sec.TICKER_FIELD_OVERRIDES` 里指定科目。返回列如下：

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

测试全部通过 mock 隔离外部网络调用（Wikipedia / yfinance / SEC / FRED），不需要
真实网络也能跑；CI（见 `.github/workflows/ci.yml`）在 push/PR 到
`main`/`master` 时会跑同样这两步。

ruff 的规则集写死在 `pyproject.toml` 的 `[tool.ruff.lint]` 里、版本在
`pyproject.toml` 中锁了上界，CI 用 `uv sync --locked` 安装——三者一起保证本地和
CI 的 lint 结果一致，不会因为 ruff 升级默认规则集而突然全红。
