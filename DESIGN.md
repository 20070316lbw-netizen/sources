# 架构设计

记录这个包的定位和几个关键设计取舍，方便以后自己（或协作者）回来看的时候
知道"为什么长这样"。

## 定位：只做抓取 + 初步清洗

这个仓库的范围明确收窄为：**从数据源拿到原始数据，做字段级的初步清洗，
返回一个 schema 固定的 DataFrame**。

明确不做的事，留给下游（未来独立的存储/处理仓库，或调用方自己）：

- 跨数据源的合并/对齐（比如把 prices 和 fundamentals 按日期 join 起来）
- 任何因子/指标计算（收益率、账面市值比、SMB/HML 分组……）
- 本地存储、缓存、增量更新
- 复杂的数据质量修复（缺口填补、极端值处理、幸存者偏差修正）

之所以在这条线上切，是因为"抓取"和"存储/加工"的生命周期、变更频率、
测试方式都不一样：抓取模块的正确性主要靠 mock 外部接口来验证；存储层
则要考虑 schema 演进、增量更新、多进程写入这些完全不同的问题。混在一个
仓库里会让两边的测试和依赖都变得更重。

## 模块布局

```
src/sources/
    __init__.py       公开 API 的唯一入口, 只做 re-export, 不写业务逻辑
    _http.py          自己发 requests 请求的模块共用的重试/UA 逻辑
                       (含 sec_identity_headers, sec.gov 请求共用)
    constituents.py   S&P 500 成分股 (Wikipedia, 直接用 requests)
    prices.py         历史行情 (yfinance, 库自己管理 HTTP)
    fundamentals.py   SEC EDGAR 基本面 (edgartools, 库自己管理 HTTP)
    riskfree.py        无风险利率 (FRED, 通过 pandas-datareader)
    listings.py        交易所归属 (SEC company_tickers_exchange.json, 直接用 requests)
```

`_http.py` 只服务于我们自己直接发起的 `requests` 调用（目前只有
`constituents.py`）。`yfinance` 和 `edgartools` 都有自己的 HTTP 客户端和
重试策略，不应该也没办法套用同一层——所以新增数据源时先看它是不是"自己
包一层 requests"，是的话才用 `_http.get_with_retry`。

新增一个数据源时的约定：

1. 一个模块对应一个数据源，文件名就是数据源的领域名（不是库名）。
2. 模块顶部的 docstring 三段式：数据源是什么、输出 schema 是什么、
   "不做的事"列出来——这样以后自己看代码不用猜边界在哪。
3. 公开函数只做一件事：给定明确的参数（ticker/日期范围/概念名……），
   返回一个 DataFrame，没有隐藏的全局配置或副作用（网络请求本身除外）。
4. 单个标的/概念失败不应该让整批调用失败：记录 `logger.warning` 然后跳过，
   除非是"参数错误"这种调用方需要立刻知道的问题（这类直接 raise）。
5. 在 `__init__.py` 里显式 re-export，形成稳定的公开 API 面；模块内部的
   私有函数/常量用下划线前缀，不暴露。

## 为什么函数都是"存储无关"的

所有公开函数都是纯函数：给参数、返回 DataFrame，不读写磁盘、不依赖全局
状态（`EDGAR_IDENTITY` 这种必需的环境变量除外）。这是故意的——存储方式
还没定（可能是 parquet、可能是 duckdb、也可能直接进数据库），现在锁定
任何一种都可能是错的。

保持函数纯粹意味着以后那个存储层仓库可以直接在外面包一层缓存/持久化
装饰器或包装函数，比如：

```python
# 未来某个存储层仓库里, 而不是这个仓库里
def cached_get_prices(*args, cache_path, **kwargs):
    if cache_path.exists():
        return pd.read_parquet(cache_path)
    df = sources.get_prices(*args, **kwargs)
    df.to_parquet(cache_path)
    return df
```

而不需要改动这个仓库里的任何一行代码。

## 输出 schema 而不是"贴着源头返回"

三个模块都不是简单地把数据源的原始响应转成 DataFrame 就返回，而是转成一个
本包内固定的长表 schema（列名、类型都统一）。这样下游代码不需要知道某一列
数据到底来自 Wikipedia 的表格、yfinance 的 MultiIndex 列，还是 edgartools
的 `time_series()` 输出——它们的字段命名风格完全不同，统一在这一层做掉，
下游只认本包定义的 schema。

代价是：数据源升级/换源时，需要在对应模块内部改，但对外的函数签名和返回
schema保持不变（除非确实需要新增字段）。这是有意的权衡。

## 打包与发布（供 `uv add` 引用）

- 用 git 直接安装：`uv add "git+https://github.com/<user>/sources.git"`。
- **建议给每次要在下游项目里用的版本打 tag**（`git tag v0.1.0 && git push --tags`），
  下游用 `uv add "...@v0.1.0"` 锁定，避免这边改了东西下游项目"悄悄"跟着变。
  `uv.lock` 里记录的是 commit hash，所以哪怕不打 tag 也是可复现的，但打 tag
  更方便人读、方便回滚。
- 已经去掉了 `[project.scripts]` 和 `main()` 这个 CLI 入口——这是一个库，
  不是一个命令行工具，保留一个印 "Hello from sources!" 的入口点只会让
  `__init__.py` 的职责变得不清晰。

## 已知的待定项 / 暂不处理

记在这里免得以后忘了是"暂时不做"还是"忘了做"：

- **历史 S&P 500 成分股**：Wikipedia 页面上还有一张历次增删记录表，可以
  反推任意历史时点的名单（避免用当前名单回测导致的幸存者偏差）。现在只抓了
  当前名单，历史变更表解析起来麻烦一些，先不做。
- **`pandas-datareader` 现在被 `riskfree.py` 用来抓 FRED 无风险利率**；
  抓 Ken French 官方因子数据（Ken French Data Library）当 benchmark 对照，
  还没做，后续需要的话可以加。
- **包名 `sources` 比较通用**：作为 `from sources import ...` 的顶层模块名，
  如果以后某个下游项目同时依赖了另一个也叫 `sources` 的包，会冲突。现在
  只有自己在用，先不改；真要改的话趁早（改了之后所有下游项目的 import 都要
  跟着改）。
