"""S&P 500 小时频行情组合接口。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd

from sources.sp500.cache import load_members
from sources.sp500.calendar import get_trade_calendar
from sources.sp500.prices import get_prices


class HourSp500:
    """面向 S&P 500 小时频行情的组合接口, 默认使用缓存的当前成分股名单。"""

    def members(self) -> pd.DataFrame:
        """读取缓存的当前 S&P 500 名单。"""
        return load_members()

    def calendar(self, start: str | date, end: str | date | None = None) -> pd.DataFrame:
        """读取美股交易日历, 每个自然日标记是否为 NYSE 交易日。"""
        return get_trade_calendar(start=start, end=end)

    def prices(
        self,
        start: str | date,
        end: str | date | None = None,
        *,
        tickers: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """抓取小时线行情; 数据可用范围受 yfinance 对小时线历史长度的限制。"""
        symbols = tickers if tickers is not None else self.members()["ticker"].tolist()
        return get_prices(symbols, start=start, end=end, interval="1h")
