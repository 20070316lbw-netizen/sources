"""A 股日线行情抓取, 数据源: BaoStock。

输出两种长表, 每行是一个 (ticker, date):
    - get_cn_prices: 列与美股 sources.get_prices 完全一致
      [date, ticker, open, high, low, close, adj_close, volume],
      下游(liudb 的 prices 表、minibacktest)不用改就能直接吃;
    - get_cn_daily_bars: 在上面基础上多出 A 股特有的交易状态字段
      [amount, pre_close, turnover, pct_chg, is_suspended, is_st],
      用于之后构建可交易掩码(停牌/ST/涨跌停)。

复权口径:
    - open/high/low/close/pre_close 是**不复权**价格;
    - adj_close 是 BaoStock 的**后复权**收盘价。选后复权而不是前复权, 是因为
      前复权每次除权都会改写全部历史价格, 增量入库时旧数据会跟着失效;
      后复权的历史值不变, 按 (ticker, date) 覆盖写入是安全的, 算出的收益率
      与前复权相同。

初步清洗:
    - 代码统一为 `600519.SH` 格式(见 sources.cn.codes);
    - date 转为不带时区的时间戳; 数值列强制转数值, BaoStock 的空字符串变 NaN;
    - 丢弃 close 缺失的行; 停牌日保留(BaoStock 停牌日 close 等于前收、
      volume 为 0), 由 is_suspended 标出, 方便下游构造掩码;
    - 单只股票抓取失败只记录 warning 并跳过, 不影响批次里的其他股票。

单位: volume 为股, amount 为元, turnover(换手率)与 pct_chg(涨跌幅)为百分数。
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

PRICE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
STATUS_COLUMNS = ["amount", "pre_close", "turnover", "pct_chg", "is_suspended", "is_st"]
BAR_COLUMNS = PRICE_COLUMNS + STATUS_COLUMNS

_RAW_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,turn,tradestatus,pctChg,isST"
_RENAME = {"preclose": "pre_close", "turn": "turnover", "pctChg": "pct_chg"}
_NUMERIC_COLUMNS = [
    "open", "high", "low", "close", "adj_close", "volume",
    "amount", "pre_close", "turnover", "pct_chg",
]

# BaoStock adjustflag: 1 后复权, 2 前复权, 3 不复权
_ADJ_NONE = "3"
_ADJ_BACKWARD = "1"


def get_cn_daily_bars(
    tickers: str | Sequence[str],
    start: DateLike,
    end: DateLike | None = None,
) -> pd.DataFrame:
    """抓取一批 A 股的日线行情(含交易状态), 返回清洗后的长表。

    每只股票发两次请求: 一次不复权行情 + 状态字段, 一次后复权收盘价。

    Args:
        tickers: 单个代码或代码列表, 如 "600519.SH" 或 ["600519.SH", "000001.SZ"]。
        start: 起始日期(含), 如 "2020-01-01"。
        end: 结束日期(**含**, 与 BaoStock 及 liudb 读取口径一致; 注意美股
            get_prices 的 end 是不含的); 默认到今天。

    Returns:
        DataFrame, 列为 BAR_COLUMNS, 按 (ticker, date) 排序。is_suspended /
        is_st 是可空布尔列。找不到数据时返回保留列结构的空 DataFrame。

    Raises:
        ValueError: tickers 为空或含无法识别的代码。
        BaostockError: 登录失败。
    """
    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
    if not ticker_list:
        raise ValueError("tickers 不能为空")
    ticker_list = [normalize_ticker(t) for t in ticker_list]

    start_str = _date_str(start)
    end_str = _date_str(end) if end is not None else ""
    logger.info(
        f"Fetching A-share daily bars for {len(ticker_list)} ticker(s) "
        f"from {start_str} to {end_str or 'today'}"
    )

    frames = []
    with _baostock.session():
        for i, ticker in enumerate(ticker_list, 1):
            try:
                frame = _fetch_single(ticker, start_str, end_str)
            except BaostockError as exc:
                logger.warning(f"{ticker}: 抓取失败, 跳过 ({exc})")
                continue
            if frame.empty:
                logger.warning(f"{ticker}: BaoStock 无数据, 跳过")
                continue
            frames.append(frame)
            if i % 50 == 0:
                logger.info(f"已抓取 {i}/{len(ticker_list)} 只")

    if not frames:
        return _empty_frame(BAR_COLUMNS)

    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["ticker", "date"]).reset_index(drop=True)


def get_cn_prices(
    tickers: str | Sequence[str],
    start: DateLike,
    end: DateLike | None = None,
) -> pd.DataFrame:
    """抓取 A 股日线, 只返回与美股 get_prices 一致的列。

    参数与 get_cn_daily_bars 相同; 返回列为
    [date, ticker, open, high, low, close, adj_close, volume],
    close 不复权、adj_close 后复权。需要停牌/ST 等状态字段时请直接用
    get_cn_daily_bars, 避免重复请求。
    """
    return get_cn_daily_bars(tickers, start, end)[PRICE_COLUMNS]


def _fetch_single(ticker: str, start: str, end: str) -> pd.DataFrame:
    code = to_baostock_code(ticker)
    raw = _baostock.query(
        "query_history_k_data_plus", code, _RAW_FIELDS,
        start_date=start, end_date=end, frequency="d", adjustflag=_ADJ_NONE,
    )
    if raw.empty:
        return raw

    adj = _baostock.query(
        "query_history_k_data_plus", code, "date,close",
        start_date=start, end_date=end, frequency="d", adjustflag=_ADJ_BACKWARD,
    ).rename(columns={"close": "adj_close"})

    df = raw.rename(columns=_RENAME).drop(columns=["code"])
    df = df.merge(adj[["date", "adj_close"]], on="date", how="left")
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = ticker

    df[_NUMERIC_COLUMNS] = df[_NUMERIC_COLUMNS].apply(pd.to_numeric, errors="coerce")
    df["is_suspended"] = _flag(df["tradestatus"], true_value="0")
    df["is_st"] = _flag(df["isST"], true_value="1")

    before = len(df)
    df = df.dropna(subset=["close"])
    if dropped := before - len(df):
        logger.debug(f"{ticker}: 丢弃 {dropped} 行 close 缺失的记录")

    return df[BAR_COLUMNS]


def _flag(col: pd.Series, *, true_value: str) -> pd.Series:
    """把 BaoStock 的 "0"/"1" 字符串转成可空布尔列, 空字符串 -> <NA>。"""
    return col.map(lambda v: pd.NA if v in ("", None) else v == true_value).astype("boolean")


def _date_str(value: DateLike) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)
