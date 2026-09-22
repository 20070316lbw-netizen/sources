"""标普500历史成分股与变动日志模块。

通过回溯 Wikipedia 的成分股变动明细, 实现点时(Point-in-Time)成分股名单反推,
用于规避回测里的幸存者偏差。

首次使用需要先生成本地缓存:

    from sources.constituents_changelog import update_cache_from_web
    update_cache_from_web()

页面的抓取与解析复用 sources._wikipedia, 与 sources.constituents 是同一套
列名和清洗规则。
"""
from __future__ import annotations

from sources._wikipedia import fetch_sp500_tables

from .reconstructor import (
    DATA_DIR_ENV,
    UNIVERSE_COLUMNS,
    get_all_historical_sp500_tickers,
    get_historical_sp500_constituents,
    get_sp500_changelog,
    load_changelog,
    load_current_constituents,
    load_historical_universe,
    resolve_data_dir,
    update_cache_from_web,
)

__all__ = [
    "DATA_DIR_ENV",
    "UNIVERSE_COLUMNS",
    "fetch_sp500_tables",
    "get_all_historical_sp500_tickers",
    "get_historical_sp500_constituents",
    "get_sp500_changelog",
    "load_changelog",
    "load_current_constituents",
    "load_historical_universe",
    "resolve_data_dir",
    "update_cache_from_web",
]
