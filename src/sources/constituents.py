"""成员股抓取, 对象: S&P 500

数据源:
    Wikipedia (S&P 500 current constituents)

页面的抓取与解析统一放在 sources._wikipedia 里, 这个模块只负责裁出对外承诺
的那两列。需要板块、纳入日期、CIK 等更多字段, 用
`sources._wikipedia.fetch_current_constituents()`; 需要历次增删明细或反推任
意历史时点的名单(避免幸存者偏差), 用 `sources.constituents_changelog`。
"""
from __future__ import annotations

import pandas as pd

from sources._wikipedia import fetch_current_constituents

_OUTPUT_COLUMNS = ["ticker", "name"]


def get_sp500_constituents() -> pd.DataFrame:
    """抓取当前 S&P 500 成分股名单。

    Returns:
        DataFrame, 列为 [ticker, name], 按 ticker 升序。ticker 已统一为大写,
        其中的 "." 已替换为 "-" (如 BRK.B -> BRK-B), 以匹配 yfinance/多数行
        情源的代码格式。
    """
    return fetch_current_constituents()[_OUTPUT_COLUMNS].copy()


if __name__ == "__main__":
    print(get_sp500_constituents())
