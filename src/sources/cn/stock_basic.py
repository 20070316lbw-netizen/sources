"""A 股证券基本资料, 数据源: BaoStock。

输出: [ticker, name, list_date, delist_date, sec_type, is_listed]。
    - delist_date 未退市时为 NaT;
    - sec_type 取值 stock / index / other / convertible_bond / etf;
    - 覆盖已退市证券, 可用于判断"某天某只股票是否已上市", 避免幸存者偏差。
"""
from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from loguru import logger

from sources.cn import _baostock
from sources.cn.codes import from_baostock_code, to_baostock_code

STOCK_BASIC_COLUMNS = ["ticker", "name", "list_date", "delist_date", "sec_type", "is_listed"]

_SEC_TYPES = {"1": "stock", "2": "index", "3": "other", "4": "convertible_bond", "5": "etf"}


def get_cn_stock_basic(tickers: str | Sequence[str] | None = None) -> pd.DataFrame:
    """抓取 A 股证券基本资料。

    Args:
        tickers: 单个代码或代码列表; 默认 None 表示全部证券(含指数、ETF 等,
            需要只要股票时按 sec_type == "stock" 过滤)。

    Returns:
        DataFrame, 列为 STOCK_BASIC_COLUMNS, 按 ticker 排序。

    Raises:
        ValueError: 含无法识别的代码。
        BaostockError: 登录或查询失败。
    """
    if tickers is None:
        codes = [""]
    else:
        ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
        codes = [to_baostock_code(t) for t in ticker_list]

    with _baostock.session():
        frames = [_baostock.query("query_stock_basic", code=code) for code in codes]

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if raw.empty:
        logger.warning("BaoStock 未返回任何证券基本资料")
        return pd.DataFrame(columns=STOCK_BASIC_COLUMNS)

    df = pd.DataFrame(
        {
            "ticker": raw["code"].map(from_baostock_code),
            "name": raw["code_name"],
            "list_date": pd.to_datetime(raw["ipoDate"], errors="coerce"),
            "delist_date": pd.to_datetime(raw["outDate"], errors="coerce"),
            "sec_type": raw["type"].map(_SEC_TYPES).fillna("other"),
            "is_listed": raw["status"] == "1",
        }
    )
    return df.drop_duplicates("ticker").sort_values("ticker").reset_index(drop=True)
