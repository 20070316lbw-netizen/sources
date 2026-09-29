"""S&P 500 当前名单入口, 复用历史成分组件维护的统一缓存。"""
from __future__ import annotations

import pandas as pd

from sources.sp500.cache.changelog import load_current_constituents, update_cache_from_web

_COLUMNS = ["ticker", "name"]


def load_members(*, refresh: bool = False) -> pd.DataFrame:
    """读取缓存的当前 S&P 500 名单, 首次调用或 refresh=True 时刷新成分缓存。

    Args:
        refresh: 为 True 时忽略旧缓存并重新抓取名单。

    Returns:
        DataFrame, 列为 [ticker, name], 按 ticker 升序。
    """
    if refresh:
        update_cache_from_web()
    try:
        members = load_current_constituents()
    except FileNotFoundError:
        update_cache_from_web()
        members = load_current_constituents()
    return members[_COLUMNS].copy()
