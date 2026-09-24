"""A 股指数成分股, 数据源: BaoStock。

目前只支持沪深300(BaoStock 另外还有上证50、中证500, 需要时在 _INDEXES 里加一行)。

输出: [index_code, date, ticker, name, update_date]
    - index_code: 指数代码, 统一为 `000300.SH` 格式(便于将来与指数行情 join);
    - date: 查询日期, 即"截至这一天的成分快照";
    - update_date: BaoStock 给出的该版成分名单的生效/更新日期。

按月取快照(get_cn_index_members_history)就能得到按时点的历史成分,
避免拿"今天的沪深300"去回测历史带来的幸存者偏差。
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from loguru import logger

from sources.cn import _baostock
from sources.cn.codes import from_baostock_code

DateLike = str | date | datetime

INDEX_MEMBER_COLUMNS = ["index_code", "date", "ticker", "name", "update_date"]

# 别名 -> (标准指数代码, BaoStock 查询方法)
_INDEXES = {
    "hs300": ("000300.SH", "query_hs300_stocks"),
}
_ALIASES = {code: alias for alias, (code, _) in _INDEXES.items()}


def get_cn_index_members(index: str = "hs300", date: DateLike | None = None) -> pd.DataFrame:
    """抓取某一天的指数成分快照。

    Args:
        index: 指数, "hs300" 或 "000300.SH"。
        date: 查询日期, 默认今天。

    Returns:
        DataFrame, 列为 INDEX_MEMBER_COLUMNS, 按 ticker 排序。

    Raises:
        ValueError: 不支持的指数。
        BaostockError: 登录或查询失败。
    """
    index_code, method = _resolve(index)
    snapshot = pd.Timestamp(date if date is not None else pd.Timestamp.today()).normalize()

    with _baostock.session():
        raw = _baostock.query(method, date=snapshot.strftime("%Y-%m-%d"))

    if raw.empty:
        logger.warning(f"{index_code}: {snapshot.date()} 无成分数据")
        return pd.DataFrame(columns=INDEX_MEMBER_COLUMNS)

    df = pd.DataFrame(
        {
            "index_code": index_code,
            "date": snapshot,
            "ticker": raw["code"].map(from_baostock_code),
            "name": raw["code_name"],
            "update_date": pd.to_datetime(raw["updateDate"]),
        }
    )
    return df.sort_values("ticker").reset_index(drop=True)


def get_cn_index_members_history(
    index: str = "hs300",
    start: DateLike = "2015-01-01",
    end: DateLike | None = None,
    *,
    freq: str = "MS",
) -> pd.DataFrame:
    """按固定频率取一串成分快照, 拼成历史成分长表。

    Args:
        index: 指数, "hs300" 或 "000300.SH"。
        start: 第一个快照日期(含)。
        end: 最后一个快照日期上限(含), 默认今天。
        freq: pandas 日期频率, 默认 "MS"(每月第一天)。沪深300 每半年调一次样,
            月度快照足够覆盖, 也不会漏掉临时调整太久。

    Returns:
        DataFrame, 列为 INDEX_MEMBER_COLUMNS, 按 (date, ticker) 排序。
    """
    dates = pd.date_range(start=start, end=end or pd.Timestamp.today(), freq=freq)
    frames = []
    with _baostock.session():
        for snapshot in dates:
            frame = get_cn_index_members(index, snapshot)
            if not frame.empty:
                frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=INDEX_MEMBER_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _resolve(index: str) -> tuple[str, str]:
    key = index.strip()
    key = _ALIASES.get(key.upper(), key.lower())
    if key not in _INDEXES:
        raise ValueError(f"不支持的指数: {index!r}, 目前支持 {sorted(_INDEXES)}")
    return _INDEXES[key]
