"""A 股小时频数据组合接口。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd

from sources.ashare.cache import load_members
from sources.ashare.intraday import get_intraday_bars


class HourAShare:
    """面向 A 股小时频数据的组合接口, 实际调用 BaoStock 60 分钟线。"""

    def members(self, *, index: str = "hs300") -> pd.DataFrame:
        """读取缓存的指数成分名单。"""
        return load_members(index=index)

    def prices(
        self,
        start: str | date,
        end: str | date | None = None,
        *,
        tickers: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """抓取 60 分钟线; 未传 tickers 时抓取缓存的沪深 300 成分股。"""
        symbols = tickers if tickers is not None else self.members()["ticker"].tolist()
        return get_intraday_bars(symbols, start=start, end=end, freq="60")
