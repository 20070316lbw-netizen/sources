"""成员股抓取, 对象: S&P 500

数据源：
    Wikipedia (S&P 500 current constituents)

若要做历史成分股(避免幸存者偏差), Wikipedia 同页面下方还有一张
"Selected changes to the list of S&P 500 components" 表，
记录了历次增删记录，可结合本表反推任意历史时点的名单。(暂未实现,
留给下游或后续版本)
"""
from __future__ import annotations

import pandas as pd
from io import StringIO
from loguru import logger

from sources._http import get_with_retry


def get_sp500_constituents() -> pd.DataFrame:
    """抓取当前 S&P 500 成分股名单。

    Returns:
        DataFrame, 列为 [ticker, name]; ticker 中的 "." 已替换为 "-"
        (如 BRK.B -> BRK-B), 以匹配 yfinance/多数行情源的代码格式。
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    logger.info(f"Fetching S&P 500 constituents from {url}")

    resp = get_with_retry(url)

    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    df = df.rename(columns={"Symbol": "ticker", "Security": "name"})
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    return df[["ticker", "name"]]


if __name__ == "__main__":
    df = get_sp500_constituents()
    print(df)
