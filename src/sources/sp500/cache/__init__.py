"""S&P 500 成员名单缓存。

缓存只保存当前名单快照, 不保存行情。默认目录可通过 ``SOURCES_DATA_DIR`` 覆盖。
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from sources.constituents import get_sp500_constituents

_COLUMNS = ["ticker", "name"]


def load_members(*, refresh: bool = False) -> pd.DataFrame:
    """读取缓存的当前 S&P 500 名单, 首次调用或 refresh=True 时从 Wikipedia 更新。

    Args:
        refresh: 为 True 时忽略旧缓存并重新抓取名单。

    Returns:
        DataFrame, 列为 [ticker, name], 按 ticker 升序。
    """
    path = _cache_path()
    if not refresh and path.exists():
        return pd.read_csv(path, dtype={"ticker": "string", "name": "string"})[_COLUMNS]

    members = get_sp500_constituents()[_COLUMNS]
    if not members.empty:
        path.parent.mkdir(parents=True, exist_ok=True)
        members.to_csv(path, index=False)
    return members


def _cache_path() -> Path:
    """返回 S&P 500 名单缓存文件路径。"""
    root = Path(os.environ.get("SOURCES_DATA_DIR", Path.home() / ".cache" / "sources"))
    return root / "sp500" / "members.csv"
