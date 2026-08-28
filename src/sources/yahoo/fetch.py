from __future__ import annotations 

from pathlib import Path
import time

import pandas as pd
import yfinance as yf
from loguru import logger

from sources.error import YahooFetchError
from sources.universe.load import load_sp500_list
from sources.config import YAHOO_CACHE_PATH


def fetch_prices(
    *,
    symbols: list[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    batch_size: int = 50,
    threads: bool = False,
    pause: float = 1.0,
    max_missing_ratio: float = 0.2,
) -> pd.DataFrame:
    """抓取价格数据, 返回整理成长表格式的 df (MultiIndex: Date, Ticker)

    分批 (batch_size) 顺序抓取, 而不是一次性对全部 ticker 发起大并发请求:
    yfinance 内部用一个共享的本地 sqlite 文件 (~/Library/Caches/py-yfinance/tkr-tz.db)
    缓存每支 ticker 的时区信息, 一次性起几百个线程同时读写这个文件很容易触发
    `sqlite3.OperationalError: unable to open database file` (常见于 macOS 默认
    fd/连接数限制被打满), 出错的 ticker 不会中断整体流程, 而是被 yfinance 悄悄填成
    NaN —— 这也是之前拿到"全 NaN"数据但没报错的原因。默认 threads=False 完全避免了
    这个并发场景; 如果确认环境没问题、想要更快, 可以传 threads=True 并适当调高
    `ulimit -n`。
    """
    frames: list[pd.DataFrame] = []

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        logger.info(f"抓取第 {i // batch_size + 1} 批 ({len(batch)} 支): {batch[0]}..{batch[-1]}")

        try:
            price = yf.download(
                tickers=batch, start=start, end=end, auto_adjust=False, threads=threads
            )
        except Exception as exc:
            raise YahooFetchError(f"yfinance 抓取过程中发生异常 (batch {i}): {exc}") from exc

        if price is None or price.empty:
            logger.warning(f"batch {i} 返回空数据, 跳过: {batch}")
            continue

        try:
            df_batch = price.stack(level="Ticker", future_stack=True).sort_index()
        except Exception as exc:
            raise YahooFetchError(f"数据格式重塑失败 (stack), batch {i}: {exc}") from exc

        frames.append(df_batch) # type: ignore

        if pause and i + batch_size < len(symbols):
            time.sleep(pause)

    if not frames:
        raise YahooFetchError("yfinance 所有批次均未获取到数据")

    df = pd.concat(frames).sort_index()
    df.index.names = ["Date", "Ticker"]  # type: ignore
    df.columns = df.columns.str.lower()  # type: ignore

    # 数据质量校验: 某支 ticker 如果所有价格列全是 NaN, 大概率是抓取失败 (而不是真的没数据),
    # 不能悄悄写入缓存 —— 之前的 bug 就是这里没做校验, 全 NaN 的结果被当成正常数据存了下来。
    price_cols = [c for c in ("close", "adj close") if c in df.columns]
    check_col = price_cols[0] if price_cols else df.columns[0]
    all_nan_by_ticker = df[check_col].isna().groupby(level="Ticker").all()
    bad_tickers = all_nan_by_ticker[all_nan_by_ticker].index.tolist()

    if bad_tickers:
        ratio = len(bad_tickers) / len(symbols)
        msg = f"{len(bad_tickers)}/{len(symbols)} 支 ticker 的价格数据全部为空: {bad_tickers}"
        if ratio > max_missing_ratio:
            raise YahooFetchError(f"{msg} (超过 {max_missing_ratio:.0%} 的容忍阈值, 拒绝写入缓存)")
        logger.warning(msg)

    return df


def save_prices(
    df: pd.DataFrame,
    *,
    path: Path | str,
) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path_obj)


if __name__ == "__main__":
    tickers = load_sp500_list()
    df = fetch_prices(symbols=tickers, start="2020-01-01", end="2026-08-20")
    save_prices(df, path=YAHOO_CACHE_PATH)
