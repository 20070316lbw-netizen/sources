"""
维基百科标普500成分股及历史增删记录解析器。
"""
import re
from typing import Tuple
import pandas as pd

from src.sources._http import get_with_retry

# 维基百科标普500成分股页面地址
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def fetch_wikipedia_tables(url: str = WIKI_URL, timeout: int = 15) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    抓取并解析维基百科页面中的当前标普500表格 Table 0 以及历史成分股变动表格 Table 1
    使用 sources._http 提供的统一 HTTP 客户端发起请求。

    Args:
        url: 维基百科页面URL, 默认为官方标普500词条页面。
        timeout: 网络请求超时时间（秒）。

    返回:
        (df_current, df_changes) 元组:
            - df_current: 当前标普500成分股DataFrame 包含symbol, name, sector, sub_industry, date_added 
            - df_changes: 历次增删变动明细DataFrame 包含date, added_symbol, added_name, removed_symbol, removed_name, reason
    """
    resp = get_with_retry(url, timeout=timeout)
    html = resp.text

    tables = pd.read_html(html)
    t0 = tables[0]
    t1 = tables[1]

    # 解析当前成分股（Table 0）
    curr_records = []
    for _, row in t0.iterrows():
        sym = str(row.iloc[0]).strip().replace(".", "-")
        name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        sector = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else ""
        sub_ind = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else ""
        date_added = str(row.iloc[5]).strip() if len(row) > 5 and pd.notna(row.iloc[5]) else ""
        curr_records.append({
            "symbol": sym,
            "name": name,
            "sector": sector,
            "sub_industry": sub_ind,
            "date_added": date_added,
        })
    df_current = pd.DataFrame(curr_records)

    # 解析成分股变动明细（Table 1: Selected changes to the list of S&P 500 components）
    changes_records = []
    for _, row in t1.iterrows():
        raw_date = str(row.iloc[0]).strip()
        # 提取规范日期（如 "January 22, 2024" 或 "2024-01-22"）
        m = re.search(r"([A-Za-z]+\s+\d{1,2},\s+\d{4})", raw_date)
        if m:
            dt = pd.to_datetime(m.group(1)).strftime("%Y-%m-%d")
        else:
            try:
                dt = pd.to_datetime(raw_date).strftime("%Y-%m-%d")
            except Exception:
                continue

        # 代码标准化：点替换为横杠，如 BRK.B -> BRK-B
        add_sym = str(row.iloc[1]).strip().replace(".", "-") if pd.notna(row.iloc[1]) else ""
        add_name = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        rem_sym = str(row.iloc[3]).strip().replace(".", "-") if pd.notna(row.iloc[3]) else ""
        rem_name = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
        reason = str(row.iloc[5]).strip() if len(row) > 5 and pd.notna(row.iloc[5]) else ""

        if add_sym.lower() in ("nan", "none", ""):
            add_sym = ""
        if rem_sym.lower() in ("nan", "none", ""):
            rem_sym = ""

        changes_records.append({
            "date": dt,
            "added_symbol": add_sym,
            "added_name": add_name,
            "removed_symbol": rem_sym,
            "removed_name": rem_name,
            "reason": reason,
        })

    df_changes = pd.DataFrame(changes_records)
    df_changes["dt"] = pd.to_datetime(df_changes["date"])
    # 按时间降序排列（最近变动排在最前）
    df_changes = df_changes.sort_values("dt", ascending=False).reset_index(drop=True)
    df_changes = df_changes.drop(columns=["dt"])

    return df_current, df_changes
