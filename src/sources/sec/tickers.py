"""ticker -> CIK 映射(数据源: SEC company_tickers.json)。

SEC 的所有 XBRL 接口都按 CIK(10 位, 左侧补零)索引。映射表只覆盖**当前仍在
申报**的公司: 已退市/被收购的历史成分股查不到, 这种情况请直接传 CIK。

同一个 ticker 的历史还可能分散在多个 CIK 下: 公司做控股架构重组时会换一个新的
申报主体(如 2015 年 Google Inc. -> Alphabet, 2019 年迪士尼收购福克斯, 2026 年
ExxonMobil), 映射表只指向新主体。已知的前身 CIK 登记在 PREDECESSOR_CIKS 里,
`get_ciks` 会一并返回, 遇到新案例往里加即可。

SEC 的 ticker 写法与 yfinance 一致, 用短横线(BRK-B); Wikipedia 的 BRK.B 这类
写法会先统一成短横线再查。
"""
from __future__ import annotations

import functools

import pandas as pd

from sources.sec._client import sec_get_json

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_TICKER_COLUMNS = ["ticker", "cik", "name"]

# ticker -> 前身申报主体的 CIK(按时间从早到晚); 键用 SEC 写法(短横线)
PREDECESSOR_CIKS: dict[str, tuple[str, ...]] = {
    "GOOGL": ("0001288776",),  # Google Inc., 2015 年重组为 Alphabet 之前
    "GOOG": ("0001288776",),
    "DIS": ("0001001039",),    # 老迪士尼(TWDC Enterprises 18), 2019 年之前
    "XOM": ("0000034088",),    # Exxon Mobil Corporation, 2026 年控股重组之前
}


def normalize_sec_ticker(ticker: str) -> str:
    """统一成 SEC 的写法: 大写, 去空白, '.' 换成 '-'。"""
    return ticker.strip().upper().replace(".", "-")


def format_cik(cik: int | str) -> str:
    """CIK 统一成 10 位左侧补零的字符串, 如 320193 -> '0000320193'。"""
    digits = str(cik).strip()
    if not digits.isdigit():
        raise ValueError(f"不是合法的 CIK: {cik!r}")
    return digits.zfill(10)


@functools.cache
def _load_ticker_table() -> pd.DataFrame:
    payload = sec_get_json(COMPANY_TICKERS_URL)
    rows = [
        {
            "ticker": normalize_sec_ticker(item["ticker"]),
            "cik": format_cik(item["cik_str"]),
            "name": item["title"],
        }
        for item in payload.values()
    ]
    # 同一 ticker 理论上只对应一个 CIK; 保险起见保留第一条(SEC 按市值排序)
    return pd.DataFrame(rows, columns=_TICKER_COLUMNS).drop_duplicates("ticker")


def get_sec_tickers(refresh: bool = False) -> pd.DataFrame:
    """返回 SEC 的 ticker 映射表 [ticker, cik, name]; 同一进程内只下载一次。

    Args:
        refresh: True 时丢弃进程内缓存, 重新下载。
    """
    if refresh:
        _load_ticker_table.cache_clear()
    return _load_ticker_table().copy()


def get_cik(ticker_or_cik: str | int) -> str:
    """把 ticker 或 CIK 解析成 10 位 CIK。

    纯数字的输入直接当 CIK 处理(不查表), 方便给已退市的公司直接传 CIK。

    Raises:
        ValueError: ticker 不在 SEC 映射表里。
    """
    text = str(ticker_or_cik).strip()
    if text.isdigit():
        return format_cik(text)

    table = _load_ticker_table()
    hit = table.loc[table["ticker"].eq(normalize_sec_ticker(text)), "cik"]
    if hit.empty:
        raise ValueError(
            f"SEC 映射表里找不到 {text!r}; 已退市/改名的公司请直接传 CIK"
        )
    return str(hit.iloc[0])


def get_ciks(ticker: str) -> list[str]:
    """ticker 当前 CIK 加上登记过的前身 CIK(从早到晚, 当前的在最后)。

    纯数字输入视为单个 CIK, 原样返回。
    """
    text = str(ticker).strip()
    if text.isdigit():
        return [format_cik(text)]
    predecessors = PREDECESSOR_CIKS.get(normalize_sec_ticker(text), ())
    return [*predecessors, get_cik(text)]
