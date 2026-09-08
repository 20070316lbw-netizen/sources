"""sources: 量化数据抓取包

只负责从各数据源抓取原始数据, 并做字段级的初步清洗(改列名、转类型、丢弃
明显无效的行)。不做跨数据源的合并、不计算任何因子/指标, 也不做任何形式的
本地存储或缓存——这些留给使用方, 或者未来独立出的存储层仓库。

公开 API:
    get_sp500_constituents  -- S&P 500 现有成分股 (数据源: Wikipedia)
    get_prices              -- 历史行情 (数据源: yfinance)
    get_fundamentals        -- 单公司财务概念时间序列 (数据源: SEC EDGAR,
                                需要设置环境变量 EDGAR_IDENTITY)
    get_fundamentals_batch  -- get_fundamentals 的批量版本
"""
from __future__ import annotations

from sources.constituents import get_sp500_constituents
from sources.fundamentals import get_fundamentals, get_fundamentals_batch
from sources.prices import get_prices

__all__ = [
    "get_sp500_constituents",
    "get_prices",
    "get_fundamentals",
    "get_fundamentals_batch",
]
