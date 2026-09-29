"""S&P 500 小时频行情组合接口。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd

from sources.sp500.cache import load_members
from sources.sp500.prices import get_prices


class HourSp500:
    """面向 S&P 500 小时频行情的组合接口, 默认使用缓存的当前成分股名单。"""

    def members(self, *, refresh: bool = False) -> pd.DataFrame:
        """读取当前 S&P 500 名单; refresh=True 时从 Wikipedia 刷新缓存。"""
        return load_members(refresh=refresh)

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
