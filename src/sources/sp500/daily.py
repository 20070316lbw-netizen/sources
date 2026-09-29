"""S&P 500 日频数据组合接口。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd

from sources.sp500.cache import load_members
from sources.sp500.calendar import get_trade_calendar
from sources.sp500.prices import get_prices
from sources.sp500.riskfree import get_risk_free_rate
from sources.sp500.sec import get_fundamentals, get_fundamentals_batch


class DailySp500:
    """面向 S&P 500 日频数据的组合接口, 默认使用缓存的当前成分股名单。"""

    def members(self) -> pd.DataFrame:
        """读取缓存的当前 S&P 500 名单。"""
        return load_members()

    def calendar(self, start: str | date, end: str | date | None = None) -> pd.DataFrame:
        """读取美股交易日历, 每个自然日标记是否为 NYSE 交易日。"""
        return get_trade_calendar(start=start, end=end)

    def prices(
        self,
        start: str | date | None = None,
        end: str | date | None = None,
        *,
        tickers: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """抓取日线行情; 未传 start 时默认请求最近十年。"""
        symbols = tickers if tickers is not None else self.members()["ticker"].tolist()
        start_date = start or (pd.Timestamp.today().normalize() - pd.DateOffset(years=10))
        return get_prices(symbols, start=start_date, end=end, interval="1d")

    def risk_free_rate(
        self,
        start: str | date,
        end: str | date | None = None,
        *,
        series: str = "DGS1MO",
    ) -> pd.DataFrame:
        """抓取 FRED 无风险利率序列, 默认使用一个月期国债利率。"""
        return get_risk_free_rate(start=start, end=end, series=series)

    def fundamentals(self, ticker: str, fields: Sequence[str] | None = None) -> pd.DataFrame:
        """抓取单家公司 SEC 标准化基本面, 每行保留对应申报日期。"""
        return get_fundamentals(ticker=ticker, fields=fields)

    def fundamentals_batch(
        self,
        tickers: Sequence[str],
        fields: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """批量抓取 SEC 基本面; 单只股票失败时继续处理其余标的。"""
        return get_fundamentals_batch(tickers=tickers, fields=fields)
