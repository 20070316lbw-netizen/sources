"""无风险利率抓取, 数据源: FRED (通过 pandas-datareader)

主要目的是为 MKT-RF(市场超额收益)因子准备无风险利率的原始输入。

输出: 长表(long format), 每行是 (series, date) 的一条记录, 列固定为
[date, series, value]。value 是 FRED 原始口径的年化利率(百分比), 具体
换算成哪个周期的收益率、用哪个期限的国债作代理, 留给下游决定。

初步清洗:
    - date 转换为不带时区的时间戳, 便于跨数据源按日期 join
    - 数值列强制转为数值类型, 非法值变 NaN 而不是抛异常
    - 丢弃 value 整行缺失的记录(节假日/数据未发布导致的空行)
    - 单个 series 抓取失败只记录 warning 并跳过, 不影响批次里的其他 series

不做的事(留给下游仓库/使用方):
    - 年化利率到月度/日度周期收益率的换算
    - 与市场收益率相减算 MKT-RF
    - 不同期限国债之间的选择/插值
    - 任何形式的本地存储/缓存
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

import pandas as pd
from loguru import logger
from pandas_datareader import data as pdr

DateLike = str | date | datetime

# 默认: 1个月期国债固定期限收益率(FRED: DGS1MO), 日频, 年化百分比
DEFAULT_SERIES: tuple[str, ...] = ("DGS1MO",)

_OUTPUT_COLUMNS = ["date", "series", "value"]


def get_risk_free_rate(
    start: DateLike,
    end: DateLike | None = None,
    series: str | Sequence[str] = DEFAULT_SERIES,
) -> pd.DataFrame:
    """抓取无风险利率, 默认取 FRED 一个月期国债利率(DGS1MO)。

    Args:
        start: 起始日期(含), 如 "2020-01-01"。
        end: 结束日期(含); 默认到今天(由 FRED 决定)。
        series: FRED 的 series id, 单个或多个, 如 "DGS1MO" 或
            ["DGS1MO", "TB3MS"]。不同 series 的频率、口径可能不同,
            由调用方自行选择、自行处理。

    Returns:
        DataFrame, 列为 [date, series, value], 按 (series, date) 排序。
        全部抓取失败或无数据时返回保留列结构的空 DataFrame。

    Raises:
        ValueError: series 为空。
    """
    series_list = [series] if isinstance(series, str) else list(series)
    if not series_list:
        raise ValueError("series 不能为空")

    logger.info(
        f"Fetching risk-free rate series {series_list} from {start} to {end or 'today'}"
    )

    frames = []
    for s in series_list:
        try:
            raw = pdr.DataReader(s, "fred", start, end)
        except Exception as e:  # noqa: BLE001 - 单个 series 失败不应影响其他 series
            logger.warning(f"{s}: 抓取失败, 跳过 ({e})")
            continue
        if raw is None or raw.empty:
            logger.warning(f"{s}: FRED 未返回任何数据, 跳过")
            continue
        frames.append(_clean_single(raw, s))

    if not frames:
        return _empty_frame()

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(["series", "date"]).reset_index(drop=True)
    return result


def _clean_single(raw: pd.DataFrame, series: str) -> pd.DataFrame:
    """把 pandas-datareader 返回的单 series 宽表整理成标准长表 schema。"""
    df = raw.reset_index()
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    if df["date"].dt.tz is not None:
        df["date"] = df["date"].dt.tz_localize(None)
    df["series"] = series
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[_OUTPUT_COLUMNS]

    before = len(df)
    df = df.dropna(subset=["value"])
    dropped = before - len(df)
    if dropped:
        logger.debug(f"{series}: 丢弃 {dropped} 行 value 缺失的记录")

    return df


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_OUTPUT_COLUMNS)


if __name__ == "__main__":
    df = get_risk_free_rate(start="2024-01-01", end="2024-02-01")
    print(df)
