from __future__ import annotations 

from pathlib import Path
import pandas as pd
import yfinance as yf
from loguru import logger

from sources.error import YahooFetchError


def fetch_prices(
    *,
    symbol: list[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> pd.DataFrame:
    """抓取价格数据, 返回整理成长表格式的 df (MultiIndex: Date, Ticker)"""
    try:
        price = yf.download(tickers=symbol, start=start, end=end, auto_adjust=False)
    except Exception as exc:
        raise YahooFetchError(f"yfinance 抓取过程中发生异常: {exc}") from exc

    if price is None or price.empty:
        raise YahooFetchError("yfinance 返回了空数据或没有获取到股票数据")

    try:
        df = (
            price
            .stack(level="Ticker", future_stack=True)
            .sort_index()
        )
    except Exception as exc:
        raise YahooFetchError(f"数据格式重塑失败 (stack): {exc}") from exc

    df.index.names = ["Date", "Ticker"]  # type: ignore
    df.columns = df.columns.str.lower()  # type: ignore

    return df  # type: ignore


def save_prices(
    df: pd.DataFrame,
    *,
    path: Path | str,
) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path_obj)



