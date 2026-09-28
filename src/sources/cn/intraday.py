"""A 股分钟级 K 线抓取, 数据源: BaoStock。

输出长表, 每行是一个 (ticker, ts):
    [ts, ticker, open, high, low, close, adj_close, volume, amount]

时间戳约定:
    ts 是 **bar 的结束时间**, 不带时区。30 分钟线每个交易日 8 根:
    10:00 10:30 11:00 11:30 13:30 14:00 14:30 15:00。例如 10:00 那根覆盖
    9:30-10:00。回测里"在 ts 收盘后算信号, 下一根 bar 成交"就不会用到未来数据。
    BaoStock 原始 time 字段形如 "20260921100000000"(YYYYMMDDHHMMSS + 3 位毫秒)。

复权口径与日线(sources.cn.prices)一致:
    open/high/low/close 不复权; adj_close 是后复权收盘价(历史值不随除权改写,
    增量入库时按 (ticker, ts) 覆盖写入是安全的)。
    注意: BaoStock 对 ETF 不做复权, ETF 的 adj_close 恒等于 close, 详见
    sources.cn.prices 模块文档里的 "已知问题"。

交易所口径差异: 上交所 ETF 当天最后一根 bar 的 close(最后成交价)与日线的
    官方收盘价可能相差几个基点, 深交所一致。涨跌停、盯市请以日线收盘价 /
    次日 pre_close 为准。

覆盖范围(2026-09 实测, BaoStock 侧的限制, 不是本模块的问题):
    - 个股: 2020 年起;
    - ETF: 大多只有 2026 年起, 个别(如 159915)有零星更早的片段;
    - 指数: 没有分钟线, 查询成功但返回空。
    所以 ETF 需要每日增量抓取、自己积累历史。

单位: volume 为股(ETF 为份), amount 为元。amount / volume 即该 bar 的成交均价。
volume 为 0 的 bar 是真实存在的, 不是缺数据: 例如 QDII ETF(513100.SH)溢价过高时
    会被交易所盘中临时停牌, 当天 10:00 / 10:30 两根 bar 的成交量为 0。回测时这类
    bar 应视为不可成交。
单只证券抓取失败或无数据只记录 warning 并跳过, 不影响批次里的其他证券。
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

import pandas as pd
from loguru import logger

from sources.cn import _baostock
from sources.cn._baostock import BaostockError
from sources.cn.codes import normalize_ticker, to_baostock_code

DateLike = str | date | datetime

INTRADAY_COLUMNS = [
    "ts", "ticker", "open", "high", "low", "close", "adj_close", "volume", "amount",
]
FREQUENCIES = ("5", "15", "30", "60")

_RAW_FIELDS = "date,time,code,open,high,low,close,volume,amount"
_NUMERIC_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume", "amount"]

# BaoStock adjustflag: 1 后复权, 2 前复权, 3 不复权
_ADJ_NONE = "3"
_ADJ_BACKWARD = "1"


def get_cn_intraday_bars(
    tickers: str | Sequence[str],
    start: DateLike,
    end: DateLike | None = None,
    *,
    freq: str | int = "30",
) -> pd.DataFrame:
    """抓取一批 A 股证券(个股 / ETF)的分钟级 K 线, 返回清洗后的长表。

    每只证券发两次请求: 一次不复权 OHLCV, 一次后复权收盘价。

    Args:
        tickers: 单个代码或代码列表, 如 "510300.SH" 或 ["510300.SH", "600519.SH"]。
        start: 起始日期(含), 如 "2026-01-01"。按日期过滤, 不支持精确到分钟。
        end: 结束日期(**含**, 与日线口径一致); 默认到今天。
        freq: K 线周期(分钟), "5" / "15" / "30" / "60", 也接受整数。默认 "30"。

    Returns:
        DataFrame, 列为 INTRADAY_COLUMNS, 按 (ticker, ts) 排序。找不到数据时返回
        保留列结构的空 DataFrame。

    Raises:
        ValueError: tickers 为空、含无法识别的代码, 或 freq 不支持。
        BaostockError: 登录失败。
    """
    freq_str = _check_freq(freq)
    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
    if not ticker_list:
        raise ValueError("tickers 不能为空")
    ticker_list = [normalize_ticker(t) for t in ticker_list]

    start_str = _date_str(start)
    end_str = _date_str(end) if end is not None else ""
    logger.info(
        f"Fetching A-share {freq_str}m bars for {len(ticker_list)} ticker(s) "
        f"from {start_str} to {end_str or 'today'}"
    )

    frames = []
    with _baostock.session():
        for i, ticker in enumerate(ticker_list, 1):
            try:
                frame = _fetch_single(ticker, start_str, end_str, freq_str)
            except BaostockError as exc:
                logger.warning(f"{ticker}: 抓取失败, 跳过 ({exc})")
                continue
            if frame.empty:
                logger.warning(f"{ticker}: BaoStock 无 {freq_str} 分钟数据, 跳过")
                continue
            frames.append(frame)
            if i % 50 == 0:
                logger.info(f"已抓取 {i}/{len(ticker_list)} 只")

    if not frames:
        return pd.DataFrame(columns=INTRADAY_COLUMNS)

    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["ticker", "ts"]).reset_index(drop=True)


def _fetch_single(ticker: str, start: str, end: str, freq: str) -> pd.DataFrame:
    code = to_baostock_code(ticker)
    raw = _baostock.query(
        "query_history_k_data_plus", code, _RAW_FIELDS,
        start_date=start, end_date=end, frequency=freq, adjustflag=_ADJ_NONE,
    )
    if raw.empty:
        return raw

    adj = _baostock.query(
        "query_history_k_data_plus", code, "time,close",
        start_date=start, end_date=end, frequency=freq, adjustflag=_ADJ_BACKWARD,
    ).rename(columns={"close": "adj_close"})

    df = raw.merge(adj[["time", "adj_close"]], on="time", how="left")
    df["ts"] = _parse_time(df["time"])
    df["ticker"] = ticker
    df[_NUMERIC_COLUMNS] = df[_NUMERIC_COLUMNS].apply(pd.to_numeric, errors="coerce")

    before = len(df)
    df = df.dropna(subset=["ts", "close"])
    if dropped := before - len(df):
        logger.debug(f"{ticker}: 丢弃 {dropped} 行时间或 close 缺失的记录")

    return df[INTRADAY_COLUMNS]


def _parse_time(col: pd.Series) -> pd.Series:
    """"20260921100000000" -> Timestamp("2026-09-21 10:00:00"); 无法解析的变 NaT。"""
    return pd.to_datetime(col.str.slice(0, 14), format="%Y%m%d%H%M%S", errors="coerce")


def _check_freq(freq: str | int) -> str:
    freq_str = str(freq).strip()
    if freq_str not in FREQUENCIES:
        raise ValueError(f"不支持的 freq: {freq!r}, 可选 {list(FREQUENCIES)}")
    return freq_str


def _date_str(value: DateLike) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")
