"""A 股指数成分名单缓存。"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from sources.ashare.constituents import get_cn_index_members

_COLUMNS = ["index_code", "date", "ticker", "name", "update_date"]


def load_members(index: str = "hs300", *, refresh: bool = False) -> pd.DataFrame:
    """读取指定指数的成分名单缓存, 首次调用或 refresh=True 时从 BaoStock 更新。

    Args:
        index: 当前支持 ``hs300`` 或 ``000300.SH``。
        refresh: 为 True 时忽略旧缓存并重新抓取名单。

    Returns:
        DataFrame, 列为 [index_code, date, ticker, name, update_date]。
    """
    key = _index_key(index)
    path = _cache_path(key)
    if not refresh and path.exists():
        frame = pd.read_csv(path)
        frame["date"] = pd.to_datetime(frame["date"])
        frame["update_date"] = pd.to_datetime(frame["update_date"])
        return frame[_COLUMNS]

    members = get_cn_index_members(index=index)[_COLUMNS]
    if not members.empty:
        path.parent.mkdir(parents=True, exist_ok=True)
        members.to_csv(path, index=False)
    return members


def _index_key(index: str) -> str:
    """把支持的指数别名转换成安全的缓存文件名。"""
    normalized = index.strip().lower()
    if normalized in {"hs300", "000300.sh"}:
        return "hs300"
    raise ValueError(f"不支持的指数: {index!r}, 目前支持 ['hs300']")


def _cache_path(index: str) -> Path:
    """返回指定指数成分名单的缓存路径。"""
    root = Path(os.environ.get("SOURCES_DATA_DIR", Path.home() / ".cache" / "sources"))
    return root / "ashare" / f"{index}_members.csv"
