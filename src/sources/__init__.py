"""sources: 量化数据抓取包。

只负责从各数据源抓取原始数据, 并做字段级的初步清洗(改列名、转类型、丢弃
明显无效的行)。不做跨数据源的合并、不计算任何因子/指标——这些留给使用方,
或者未来独立出的存储层仓库。

公开 API:
    DailySp500 / HourSp500           -- S&P 500 日频和小时频组合接口
    get_sp500_constituents           -- S&P 500 当前成分股 (数据源: Wikipedia)
    get_prices                       -- 历史行情 (数据源: yfinance)
    get_risk_free_rate               -- 无风险利率 (数据源: FRED, 通过 pandas-datareader)
    get_historical_sp500_constituents -- 任意历史时点的成分股名单(点时反推)
    get_all_historical_sp500_tickers  -- 全部曾进入过 S&P 500 的代码(含已剔除的)
    get_sp500_changelog              -- 历次增删变动明细
    update_cache_from_web            -- 刷新上面三个函数依赖的本地缓存

`sources.sec` 子包直接请求 SEC 的 XBRL companyfacts 接口, 提供带申报日期的
标准化基本面(get_fundamentals / get_fundamentals_batch), 供 liudb 做点时数据;
`sources.roe` 在其上计算年度 ROE(get_roe / get_roe_batch)。SEC 身份标识默认
"liu 20070316lbw@gmail.com", 可用环境变量 EDGAR_IDENTITY 覆盖, 详见 README。

点时反推相关的函数依赖本地缓存, 首次使用需要先跑一次 update_cache_from_web();
缓存目录可用环境变量 SOURCES_DATA_DIR 指定。
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
from sources.sp500 import DailySp500, HourSp500
from sources.sp500 import constituents as constituents
from sources.sp500 import prices as prices
from sources.sp500 import riskfree as riskfree
from sources.sp500.cache import update_members as update_sp500_members
from sources.sp500.calendar import get_trade_calendar as get_sp500_trade_calendar

__all__ = [
    "DailySp500",
    "HourSp500",
    "get_all_historical_sp500_tickers",
    "get_historical_sp500_constituents",
    "get_prices",
    "get_risk_free_rate",
    "get_sp500_changelog",
    "get_sp500_constituents",
    "get_sp500_trade_calendar",
    "update_cache_from_web",
    "update_sp500_members",
]
