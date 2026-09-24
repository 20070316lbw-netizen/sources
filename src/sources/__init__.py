"""sources: 量化数据抓取包

只负责从各数据源抓取原始数据, 并做字段级的初步清洗(改列名、转类型、丢弃
明显无效的行)。不做跨数据源的合并、不计算任何因子/指标——这些留给使用方,
或者未来独立出的存储层仓库。

公开 API:
    get_sp500_constituents           -- S&P 500 当前成分股 (数据源: Wikipedia)
    get_prices                       -- 历史行情 (数据源: yfinance)
    get_risk_free_rate               -- 无风险利率 (数据源: FRED, 通过 pandas-datareader)
    get_historical_sp500_constituents -- 任意历史时点的成分股名单(点时反推)
    get_all_historical_sp500_tickers  -- 全部曾进入过 S&P 500 的代码(含已剔除的)
    get_sp500_changelog              -- 历次增删变动明细
    update_cache_from_web            -- 刷新上面三个函数依赖的本地缓存

`sources.roe` 子模块额外提供 get_roe / get_roe_batch, 基于 SEC EDGAR 年报
计算净资产收益率, 需要设置环境变量 EDGAR_IDENTITY, 详见 README。

点时反推相关的函数依赖本地缓存, 首次使用需要先跑一次 update_cache_from_web();
缓存目录可用环境变量 SOURCES_DATA_DIR 指定。

A 股数据(数据源 BaoStock)在 `sources.cn` 子包里: get_cn_prices / get_cn_daily_bars
/ get_cn_trade_calendar / get_cn_stock_basic / get_cn_index_members 等, 详见其文档。
"""
from __future__ import annotations

from sources.constituents import get_sp500_constituents
from sources.constituents_changelog import (
    get_all_historical_sp500_tickers,
    get_historical_sp500_constituents,
    get_sp500_changelog,
    update_cache_from_web,
)
from sources.prices import get_prices
from sources.riskfree import get_risk_free_rate

__all__ = [
    "get_all_historical_sp500_tickers",
    "get_historical_sp500_constituents",
    "get_prices",
    "get_risk_free_rate",
    "get_sp500_changelog",
    "get_sp500_constituents",
    "update_cache_from_web",
]
