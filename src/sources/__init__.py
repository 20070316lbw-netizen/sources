"""sources: 量化数据抓取包

只负责从各数据源抓取原始数据, 并做字段级的初步清洗(改列名、转类型、丢弃
明显无效的行)。不做跨数据源的合并、不计算任何因子/指标, 也不做任何形式的
本地存储或缓存——这些留给使用方, 或者未来独立出的存储层仓库。

公开 API:
    get_sp500_constituents  -- S&P 500 现有成分股 (数据源: Wikipedia)
    get_prices              -- 历史行情 (数据源: yfinance)
    get_risk_free_rate      -- 无风险利率 (数据源: FRED, 通过 pandas-datareader)

`sources.roe` 子模块额外提供 get_roe / get_roe_batch, 基于 SEC EDGAR 年报
计算净资产收益率, 需要设置环境变量 EDGAR_IDENTITY, 详见 README。
"""
from __future__ import annotations

from sources.constituents import get_sp500_constituents
from sources.prices import get_prices
from sources.riskfree import get_risk_free_rate

__all__ = [
    "get_prices",
    "get_risk_free_rate",
    "get_sp500_constituents",
]
