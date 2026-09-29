"""S&P 500 当前名单入口, 复用历史成分组件维护的统一缓存。"""
from __future__ import annotations

import pandas as pd

from sources.sp500.cache.changelog import load_current_constituents, update_cache_from_web

_COLUMNS = ["ticker", "name"]


def load_members() -> pd.DataFrame:
    """读取缓存的当前 S&P 500 名单, 缓存缺失时初始化历史成分缓存。

    Returns:
        DataFrame, 列为 [ticker, name], 按 ticker 升序。
    """
    try:
        members = load_current_constituents()
    except FileNotFoundError:
        update_cache_from_web()
        members = load_current_constituents()
    return members[_COLUMNS].copy()


def update_members() -> pd.DataFrame:
    """从 Wikipedia 手动更新当前及历史 S&P 500 成分缓存并返回当前名单。"""
    update_cache_from_web()
    return load_members()
