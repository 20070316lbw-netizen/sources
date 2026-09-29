"""A 股日频数据组合接口。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd

from sources.ashare.cache import load_members
from sources.ashare.calendar import get_trade_calendar
from sources.ashare.prices import get_daily_bars, get_prices
from sources.ashare.stock_basic import get_stock_basic


class DailyAShare:
    """面向 A 股日频数据的组合接口, 默认使用缓存的沪深 300 成分名单。"""

    def members(self, *, refresh: bool = False, index: str = "hs300") -> pd.DataFrame:
        """读取指数成分名单; refresh=True 时从 BaoStock 刷新缓存。"""
        return load_members(index=index, refresh=refresh)

    def prices(
        self,
        start: str | date,
        end: str | date | None = None,
        *,
        tickers: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """抓取日线价格; 未传 tickers 时抓取缓存的沪深 300 成分股。"""
        symbols = tickers if tickers is not None else self.members()["ticker"].tolist()
        return get_prices(symbols, start=start, end=end)

    def bars(
        self,
        start: str | date,
        end: str | date | None = None,
        *,
        tickers: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """抓取含停牌、ST、成交额等状态字段的日线数据。"""
        symbols = tickers if tickers is not None else self.members()["ticker"].tolist()
        return get_daily_bars(symbols, start=start, end=end)

    def calendar(self, start: str | date, end: str | date | None = None) -> pd.DataFrame:
        """抓取 A 股交易日历。"""
        return get_trade_calendar(start=start, end=end)

    def stock_basic(self, tickers: str | Sequence[str] | None = None) -> pd.DataFrame:
        """读取 A 股证券资料, 包括上市和退市日期。"""
        return get_stock_basic(tickers=tickers)
