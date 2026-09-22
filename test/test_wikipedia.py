from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from sources._wikipedia import (
    CHANGE_COLUMNS,
    CONSTITUENT_COLUMNS,
    fetch_current_constituents,
    fetch_sp500_tables,
)

# 第一张是干扰表(页面顶部的信息框), 用来验证「按内容认表」而不是按下标取表。
DECOY_TABLE = """
<table>
  <tr><th>Foundation</th><th>Value</th></tr>
  <tr><td>March 4, 1957</td><td>S&P Dow Jones Indices</td></tr>
</table>
"""

CURRENT_TABLE = """
<table>
  <tr>
    <th>Symbol</th><th>Security</th><th>GICS Sector</th>
    <th>GICS Sub-Industry</th><th>Headquarters Location</th>
    <th>Date added</th><th>CIK</th><th>Founded</th>
  </tr>
  <tr>
    <td>MMM</td><td>3M</td><td>Industrials</td><td>Conglomerates</td>
    <td>Saint Paul, Minnesota</td><td>1957-03-04</td><td>66740</td><td>1902</td>
  </tr>
  <tr>
    <td>BRK.B[1]</td><td>Berkshire Hathaway</td><td>Financials</td><td>Multi-Sector</td>
    <td>Omaha, Nebraska</td><td>February 16, 2010</td><td>1067983</td><td>1839</td>
  </tr>
</table>
"""

CHANGES_TABLE = """
<table>
  <tr>
    <th rowspan="2">Date</th>
    <th colspan="2">Added</th>
    <th colspan="2">Removed</th>
    <th rowspan="2">Reason</th>
  </tr>
  <tr><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th></tr>
  <tr>
    <td>January 22, 2024</td><td>SMCI</td><td>Super Micro</td>
    <td>WHR</td><td>Whirlpool</td><td>Market cap change</td>
  </tr>
  <tr>
    <td>October 2, 2023</td><td>BX</td><td>Blackstone</td>
    <td>LNC</td><td>Lincoln National</td><td>Market cap change</td>
  </tr>
  <tr>
    <td>not a date</td><td>FOO</td><td>Foo Inc</td>
    <td></td><td></td><td>Bad row</td>
  </tr>
</table>
"""

FULL_PAGE = DECOY_TABLE + CURRENT_TABLE + CHANGES_TABLE


def _patch_response(html: str):
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status.return_value = None
    return patch("sources._http.requests.get", return_value=resp)


def test_current_table_schema_and_ticker_normalization():
    with _patch_response(FULL_PAGE):
        df_current = fetch_current_constituents()

    assert list(df_current.columns) == CONSTITUENT_COLUMNS
    # 按内容认表: 跳过了顶部的干扰表
    assert df_current["ticker"].tolist() == ["BRK-B", "MMM"]
    # 脚注 [1] 被剥掉, 点号换成横杠
    assert "BRK.B" not in df_current["ticker"].tolist()
    assert df_current.loc[0, "sector"] == "Financials"
    # 两种日期写法都能解析成 datetime
    assert df_current["date_added"].tolist() == [
        pd.Timestamp("2010-02-16"),
        pd.Timestamp("1957-03-04"),
    ]


def test_changes_table_flattens_two_level_header():
    with _patch_response(FULL_PAGE):
        _, df_changes = fetch_sp500_tables()

    assert list(df_changes.columns) == CHANGE_COLUMNS
    # 日期解析不了的那行被丢弃
    assert len(df_changes) == 2
    # 按日期降序
    assert df_changes["date"].tolist() == [
        pd.Timestamp("2024-01-22"),
        pd.Timestamp("2023-10-02"),
    ]
    assert df_changes.loc[0, "added_ticker"] == "SMCI"
    assert df_changes.loc[0, "removed_ticker"] == "WHR"
    assert df_changes.loc[0, "reason"] == "Market cap change"


def test_empty_cells_become_empty_string_not_nan():
    with _patch_response(FULL_PAGE):
        _, df_changes = fetch_sp500_tables()

    # 反推逻辑靠 `if row.added_ticker` 判空, 不能出现 "nan" 字符串
    assert not df_changes["added_ticker"].str.lower().isin(["nan", "none"]).any()
    assert not df_changes["removed_ticker"].str.lower().isin(["nan", "none"]).any()


def test_fetch_current_constituents_tolerates_missing_changes_table():
    # 只有当前成分股表时, 取名单不应该被另一张表的缺失拖累
    with _patch_response(DECOY_TABLE + CURRENT_TABLE):
        df_current = fetch_current_constituents()

    assert len(df_current) == 2


def test_raises_when_no_table_matches_schema():
    with _patch_response(DECOY_TABLE), pytest.raises(ValueError, match="当前成分股"):
        fetch_current_constituents()
