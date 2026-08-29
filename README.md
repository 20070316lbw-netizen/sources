# sources

个人量化研究用的数据源工具库：抓取 Yahoo 行情、S&P 500 成分股与 SEC EDGAR 基本面数据，统一整理成
`MultiIndex (Date, Ticker)` 的 DataFrame 并缓存到本地。只放在 GitHub 上，不发布到 PyPI，供其他研究项目以 git 依赖的方式引用。

| 子包 | 数据源 | 产出 |
| --- | --- | --- |
| `sources.universe` | 维基百科 S&P 500 列表 + SEC CIK 注册库交叉校验 | `data/sp500_ticker.csv` |
| `sources.yahoo` | yfinance 日线行情 | `data/sp500.parquet` |
| `sources.sec` | SEC EDGAR 10-K / 10-Q，含日频 Point-in-Time 对齐 | `data/sec/sp500_fundamentals_daily.parquet` |

## 本地开发

推荐用 `uv` 管理环境：

```bash
uv sync                                  # 装依赖
uv run pytest                            # 跑自动化测试 (不联网)
uv run ruff check .                       # 跑 lint
uv run python scripts/smoke_check.py     # 联网冒烟检查, 三条链路真跑一遍
```

`scripts/smoke_check.py` 会真的发请求并往 `data/` 写缓存，只在想验证外部接口是否还能用的时候手动跑；
CI 里跑的是 `tests/` 下不联网的单元测试。

## 在其他项目中引用

```bash
uv add git+https://github.com/20070316lbw-netizen/sources.git
# pip 用户：pip install git+https://github.com/20070316lbw-netizen/sources.git
```

建议固定到某个 commit 或 tag，避免 `main` 更新后被引用方意外拉到不兼容的改动：

```bash
uv add git+https://github.com/20070316lbw-netizen/sources.git@<commit-or-tag>
```

安装后按子包导入：

```python
from sources.universe import fetch_sp500_universe, load_sp500_list, load_cached_universe
from sources.yahoo import fetch_prices, save_prices, load_prices
from sources.sec import fetch_sec, fetch_filing_metrics, to_daily_pit, load_fundamentals
from sources.error import QuantLabError, DataFetchError, YahooFetchError, EdgarFetchError

symbols = load_sp500_list()                        # 读/写 data/sp500_ticker.csv
prices = fetch_prices(symbols=symbols, start="2020-01-01", end="2026-08-20")
save_prices(prices)                                # 落到 data/sp500.parquet

daily_pit = fetch_sec(symbols=symbols, limit=8)    # 日频 PIT 基本面, 可直接与 prices 对齐
```

顶层 `import sources` 不做 re-export，这样只用 universe 的调用方不会被迫加载 yfinance 和 edgartools。

## 配置

`sources.sec` 与 `universe` 的 CIK 交叉校验都要请求 SEC，SEC 要求 User-Agent 里带真实姓名和邮箱。
复制 `.env.example` 为 `.env` 并填上自己的身份信息（`.env` 已在 `.gitignore` 中）：

```bash
cp .env.example .env
```

## 关于路径参数

所有读写文件的函数（`load_cached_universe` / `load_sp500_list` / `save_prices` / `load_prices` /
`save_fundamentals` / `load_fundamentals` / `fetch_sec` 的 `save_path`）都接受 `path` 参数，
默认值是 **相对路径**，如 `"data/sp500_ticker.csv"`，以调用方进程的当前工作目录为起点
（即从项目根目录 `uv run python xxx.py` 时，就是调用方自己的 `data/`）。

包内刻意不基于 `Path(__file__)` 派生任何路径——作为 git 依赖装到别人项目里之后，包的安装位置
和调用方的项目目录是两回事，用安装位置拼出来的路径在调用方那边没有意义。想放别处随时传
`path=...` 覆盖。
