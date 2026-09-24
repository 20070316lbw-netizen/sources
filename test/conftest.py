"""共享夹具: 一份手工构造的 SEC companyfacts JSON(日历年财年的虚构公司)。

时间线(全部为虚构数据):
    K23  10-K    filed 2024-02-10  FY2023, 比较期 FY2022
    Q124 10-Q    filed 2024-05-01  Q1 2024
    Q224 10-Q    filed 2024-08-01  Q2 2024(利润表有单季 + 累计, 现金流只有累计)
    Q324 10-Q    filed 2024-11-01  Q3 2024
    K24  10-K    filed 2025-02-10  FY2024, 比较期 FY2023
    K24A 10-K/A  filed 2025-04-01  重述 FY2024 净利润
    E8K  8-K     filed 2024-04-20  零星 XBRL 事实, 应被表单过滤掉
"""
from __future__ import annotations

import pytest

_FILINGS = {
    "K23": ("10-K", "2024-02-10", 2023, "FY"),
    "Q124": ("10-Q", "2024-05-01", 2024, "Q1"),
    "Q224": ("10-Q", "2024-08-01", 2024, "Q2"),
    "Q324": ("10-Q", "2024-11-01", 2024, "Q3"),
    "K24": ("10-K", "2025-02-10", 2024, "FY"),
    "K24A": ("10-K/A", "2025-04-01", 2024, "FY"),
    "E8K": ("8-K", "2024-04-20", 2024, "Q1"),
}


def _fact(accn: str, end: str, val: float, start: str | None = None) -> dict:
    form, filed, fy, fp = _FILINGS[accn]
    item = {"end": end, "val": val, "accn": accn, "fy": fy, "fp": fp, "form": form, "filed": filed}
    if start is not None:
        item["start"] = start
    return item


def build_companyfacts() -> dict:
    net_income = [
        _fact("K23", "2022-12-31", 300, "2022-01-01"),
        _fact("K23", "2023-12-31", 400, "2023-01-01"),
        _fact("Q124", "2023-03-31", 90, "2023-01-01"),
        _fact("Q124", "2024-03-31", 110, "2024-01-01"),
        _fact("Q224", "2024-06-30", 120, "2024-04-01"),
        _fact("Q224", "2024-06-30", 230, "2024-01-01"),
        _fact("Q324", "2024-09-30", 130, "2024-07-01"),
        _fact("Q324", "2024-09-30", 360, "2024-01-01"),
        _fact("K24", "2023-12-31", 400, "2023-01-01"),
        _fact("K24", "2024-12-31", 500, "2024-01-01"),
        _fact("K24A", "2024-12-31", 480, "2024-01-01"),
        _fact("E8K", "2024-03-31", 999, "2024-01-01"),
    ]
    profit_loss = [_fact("K24", "2024-12-31", 510, "2024-01-01")]
    ocf = [
        _fact("Q124", "2024-03-31", 50, "2024-01-01"),
        _fact("Q224", "2024-06-30", 110, "2024-01-01"),
        _fact("Q324", "2024-09-30", 180, "2024-01-01"),
        _fact("K24", "2024-12-31", 260, "2024-01-01"),
    ]
    equity = [
        _fact("K23", "2022-12-31", 900),
        _fact("K23", "2023-12-31", 1000),
        _fact("K24", "2023-12-31", 1000),
        _fact("K24", "2024-12-31", 1200),
    ]
    shares = [_fact("K24", "2025-01-31", 50)]
    return {
        "cik": 1234,
        "entityName": "Test Corp",
        "facts": {
            "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": shares}}},
            "us-gaap": {
                "NetIncomeLoss": {"units": {"USD": net_income}},
                "ProfitLoss": {"units": {"USD": profit_loss}},
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": ocf}},
                "StockholdersEquity": {"units": {"USD": equity}},
                "UnrelatedConcept": {"units": {"USD": [_fact("K24", "2024-12-31", 1)]}},
            },
        },
    }


@pytest.fixture
def companyfacts() -> dict:
    return build_companyfacts()


@pytest.fixture
def mock_sec(monkeypatch, companyfacts):
    """把 sec_get_json 换成本地假数据: ticker 表 + companyfacts, 记录请求过的 URL。"""
    import sources.sec.companyfacts as cf_module
    import sources.sec.tickers as tickers_module

    requested: list[str] = []
    ticker_table = {
        "0": {"cik_str": 1234, "ticker": "TEST", "title": "Test Corp"},
        "1": {"cik_str": 1067983, "ticker": "BRK-B", "title": "Berkshire"},
    }

    def fake_get_json(url: str, **_):
        requested.append(url)
        if url.endswith("company_tickers.json"):
            return ticker_table
        if "CIK0000009999" in url:
            raise RuntimeError("SEC unavailable")
        return build_companyfacts()

    monkeypatch.setattr(cf_module, "sec_get_json", fake_get_json)
    monkeypatch.setattr(tickers_module, "sec_get_json", fake_get_json)
    tickers_module._load_ticker_table.cache_clear()
    yield requested
    tickers_module._load_ticker_table.cache_clear()
