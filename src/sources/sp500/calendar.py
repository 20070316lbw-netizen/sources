"""S&P 500 使用的 NYSE 交易日历。"""
from __future__ import annotations

from datetime import date, datetime

import exchange_calendars as xcals
import pandas as pd

DateLike = str | date | datetime

CALENDAR_COLUMNS = ["date", "is_open"]


def get_trade_calendar(start: DateLike, end: DateLike | None = None) -> pd.DataFrame:
    """返回 [start, end] 区间每天是否为 NYSE 交易日。

    Args:
        start: 起始日期, 如 ``"2020-01-01"``。
        end: 结束日期, 默认今天。

    Returns:
        DataFrame, 列为 [date, is_open], 每个自然日一行并按日期排序。
    """
    start_date = pd.Timestamp(start).normalize()
    end_date = (
        pd.Timestamp(end).normalize() if end is not None else pd.Timestamp.today().normalize()
    )
    if end_date < start_date:
        return pd.DataFrame(columns=CALENDAR_COLUMNS)

    dates = pd.date_range(start_date, end_date, freq="D")
    sessions = xcals.get_calendar("XNYS").sessions_in_range(start_date, end_date)
    session_dates = pd.DatetimeIndex(sessions).tz_localize(None).normalize()
    return pd.DataFrame(
        {
            "date": dates,
            "is_open": dates.isin(session_dates),
        }
    )
