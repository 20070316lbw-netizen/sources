"""本包所有自定义异常。

层次结构::

    QuantLabError                 # 捕获它 = 捕获本包抛出的一切异常
    └── DataFetchError            # 所有"外部数据抓取失败"的根
        ├── WikiFetchError        # 维基百科 S&P 500 成分股页面
        ├── YahooFetchError       # yfinance 行情
        └── EdgarFetchError       # SEC EDGAR 财报
"""

from __future__ import annotations


class QuantLabError(Exception):
    """本包所有自定义异常的根。捕获它 = 捕获本包抛出的一切异常。"""


class DataFetchError(QuantLabError):
    """所有外部数据抓取相关异常的根。"""


class WikiFetchError(DataFetchError):
    """维基百科成分股页面请求或解析失败。"""


class YahooFetchError(DataFetchError):
    """yfinance 行情抓取失败, 或抓到的数据未通过质量校验。"""


class EdgarFetchError(DataFetchError):
    """SEC EDGAR 财报抓取或解析失败。

    两种构造方式:

    - ``EdgarFetchError("网络连接超时")`` —— 直接给一句错误描述;
    - ``EdgarFetchError("0000320193", status_code=404)`` —— 给 CIK 加 HTTP 状态码,
      消息会被自动拼成 "CIK 0000320193 抓取失败, 状态码 404"。
    """

    def __init__(self, message_or_cik: str = "", status_code: int | None = None) -> None:
        if status_code is not None:
            self.cik = message_or_cik
            self.status_code = status_code
            super().__init__(f"CIK {message_or_cik} 抓取失败, 状态码 {status_code}")
        else:
            self.cik = ""
            self.status_code = None
            super().__init__(message_or_cik)
