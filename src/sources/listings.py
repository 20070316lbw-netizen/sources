"""交易所归属信息抓取, 数据源: SEC (company_tickers_exchange.json)

主要目的是为按 NYSE 分位点分组(经典 FF 因子构造法)准备原始输入——每个
ticker 挂在哪个交易所。

使用前提:
    必须设置环境变量 EDGAR_IDENTITY(与 fundamentals.py 共用), SEC 要求
    所有 sec.gov 请求携带身份标识, 见 sources._http.sec_identity_headers。

输出: 长表(long format), 每行是一个 ticker 的挂牌记录, 列固定为
[ticker, cik, name, exchange]。

初步清洗:
    - 列名统一为小写 snake_case
    - exchange 为空字符串的记录(SEC 该字段本身允许为空, 常见于未在传统
      交易所挂牌的 filer)统一转成缺失值, 而不是保留空字符串
    - 传入 tickers 但在 SEC 名单里找不到的, 只记录 warning 并跳过, 不中断

不做的事(留给下游仓库/使用方):
    - 判断某个 exchange 是否等价于经典 FF 方法里的 "NYSE"(比如 NYSE
      American/NYSE Arca 是否算, 由调用方按自己的口径决定)
    - 不落盘、不缓存
"""
from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from loguru import logger

from sources._http import get_with_retry, sec_identity_headers

_LISTINGS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

_OUTPUT_COLUMNS = ["ticker", "cik", "name", "exchange"]


def get_exchange_listings(tickers: str | Sequence[str] | None = None) -> pd.DataFrame:
    """抓取 SEC 维护的 ticker -> 交易所映射。

    Args:
        tickers: 单个 ticker、ticker 列表, 或 None(默认)抓取 SEC 公布的
            全部挂牌记录, 不做筛选。

    Returns:
        DataFrame, 列为 [ticker, cik, name, exchange]。tickers 全部找不到
        或 SEC 未返回数据时, 返回保留列结构的空 DataFrame。

    Raises:
        RuntimeError: 未设置 EDGAR_IDENTITY 环境变量。
    """
    logger.info(f"Fetching exchange listings from {_LISTINGS_URL}")

    resp = get_with_retry(_LISTINGS_URL, headers=sec_identity_headers())
    payload = resp.json()

    fields = payload.get("fields", [])
    data = payload.get("data", [])
    if not fields or not data:
        logger.warning("SEC 未返回任何交易所挂牌数据")
        return _empty_frame()

    df = pd.DataFrame(data, columns=fields)
    df = df.rename(columns={"cik": "cik", "name": "name", "ticker": "ticker", "exchange": "exchange"})
    df["exchange"] = df["exchange"].replace("", pd.NA)
    df = df[_OUTPUT_COLUMNS]

    if tickers is not None:
        ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
        found = set(df["ticker"]) & set(ticker_list)
        missing = [t for t in ticker_list if t not in found]
        if missing:
            logger.warning(f"以下 ticker 不在 SEC 交易所名单中, 跳过: {missing}")
        df = df[df["ticker"].isin(ticker_list)].reset_index(drop=True)

    return df


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_OUTPUT_COLUMNS)


if __name__ == "__main__":
    df = get_exchange_listings(["AAPL", "MSFT"])
    print(df)
