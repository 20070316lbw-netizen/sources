"""A 股交易日历, 数据源: BaoStock。

输出: [date, is_open], 每个自然日一行, is_open 表示当天是否为 A 股交易日。
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from sources.cn import _baostock

DateLike = str | date | datetime

CALENDAR_COLUMNS = ["date", "is_open"]


def get_cn_trade_calendar(start: DateLike, end: DateLike | None = None) -> pd.DataFrame:
    """抓取 [start, end] 区间(两端都含)的 A 股交易日历。

    Args:
        start: 起始日期, 如 "2015-01-01"。
        end: 结束日期, 默认今天。

    Returns:
        DataFrame, 列为 [date, is_open], 按 date 排序。

    Raises:
        BaostockError: 登录或查询失败。
    """
    start_str = pd.Timestamp(start).strftime("%Y-%m-%d")
    end_str = pd.Timestamp(end).strftime("%Y-%m-%d") if end is not None else None

    with _baostock.session():
        raw = _baostock.query("query_trade_dates", start_date=start_str, end_date=end_str)

    if raw.empty:
        return pd.DataFrame(columns=CALENDAR_COLUMNS)

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["calendar_date"]),
            "is_open": raw["is_trading_day"] == "1",
        }
    )
    return df.sort_values("date").reset_index(drop=True)
