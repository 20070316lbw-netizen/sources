"""sources.roe: 基于 sources.sec 标准化基本面计算年度 ROE(不访问网络)。"""
from __future__ import annotations

import pandas as pd
import pytest

import sources.roe as roe_module
import sources.sec.fields as fields_module
from sources.map.first_50 import tickers
from sources.roe import calculate_roe, get_roe, get_roe_batch
from sources.sec import parse_company_facts, standardize_facts


def _facts(companyfacts, ticker: str = "TEST") -> pd.DataFrame:
    return standardize_facts(
        parse_company_facts(companyfacts), ticker, ["net_income", "total_equity"]
    )


def test_calculate_roe_uses_same_10k_for_both_equity_ends(companyfacts):
    result = calculate_roe("test", _facts(companyfacts))

    assert result["period_end"].tolist() == [pd.Timestamp("2024-12-31"),
                                             pd.Timestamp("2023-12-31")]
    fy24 = result.iloc[0]
    assert fy24["ticker"] == "TEST"
    assert fy24["net_income"] == 500  # 10-K/A 里没有权益数据, 这一年仍以 K24 为准
    assert fy24["beginning_equity"] == 1000
    assert fy24["ending_equity"] == 1200
    assert fy24["average_equity"] == 1100
    assert fy24["roe"] == pytest.approx(500 / 1100)
    assert fy24["roe_percent"] == pytest.approx(50000 / 1100)

    fy23 = result.iloc[1]
    assert fy23["roe"] == pytest.approx(400 / 950)


def test_calculate_roe_ignores_quarterly_filings(companyfacts):
    result = calculate_roe("TEST", _facts(companyfacts))

    assert len(result) == 2
    assert result.columns.tolist() == roe_module._ROE_COLUMNS


def test_calculate_roe_prefers_latest_annual_filing_for_same_year(companyfacts):
    # 给 10-K/A 补上权益 -> 同一财年有两份"本年"申报, 取较新的那份
    equity = companyfacts["facts"]["us-gaap"]["StockholdersEquity"]["units"]["USD"]
    for end, val in (("2023-12-31", 1000), ("2024-12-31", 1180)):
        equity.append({"end": end, "val": val, "accn": "K24A", "fy": 2024, "fp": "FY",
                       "form": "10-K/A", "filed": "2025-04-01"})

    fy24 = calculate_roe("TEST", _facts(companyfacts)).iloc[0]

    assert fy24["net_income"] == 480
    assert fy24["ending_equity"] == 1180


def test_calculate_roe_respects_ticker_override(monkeypatch, companyfacts):
    monkeypatch.setattr(
        fields_module, "TICKER_FIELD_OVERRIDES", {"TEST": {"net_income": ("us-gaap:ProfitLoss",)}}
    )
    fy24 = calculate_roe("TEST", _facts(companyfacts)).iloc[0]

    assert fy24["net_income"] == 510


def test_calculate_roe_empty_when_no_equity(companyfacts):
    del companyfacts["facts"]["us-gaap"]["StockholdersEquity"]

    result = calculate_roe("TEST", _facts(companyfacts))

    assert result.empty
    assert result.columns.tolist() == roe_module._ROE_COLUMNS


def test_get_roe_fetches_and_calculates_one_year(mock_sec):
    result = get_roe("TEST")

    assert result[["ticker", "period_end"]].to_dict("records") == [
        {"ticker": "TEST", "period_end": pd.Timestamp("2024-12-31")}
    ]


def test_get_roe_multiple_years(mock_sec):
    assert len(get_roe("TEST", years=5)) == 2


def test_get_roe_rejects_bad_years():
    with pytest.raises(ValueError, match="years"):
        get_roe("TEST", years=0)


def test_get_roe_batch_skips_failed_ticker(mock_sec):
    result = get_roe_batch(["TEST", "UNKNOWN", "BRK-B"], show_progress=False)

    assert result["ticker"].tolist() == ["TEST", "BRK-B"]


def test_get_roe_batch_defaults_to_first_50(monkeypatch):
    requested: list[str] = []

    def fake_get_roe(ticker, years=1):
        requested.append(ticker)
        return pd.DataFrame([{"ticker": ticker, "period_end": pd.Timestamp("2024-12-31")}])

    monkeypatch.setattr(roe_module, "get_roe", fake_get_roe)
    result = get_roe_batch()

    assert requested == tickers
    assert result["ticker"].tolist() == tickers


def test_get_roe_batch_supports_show_progress_flag(mock_sec):
    assert get_roe_batch(["TEST"], show_progress=False)["ticker"].tolist() == ["TEST"]
    assert get_roe_batch(["TEST"], show_progress=True)["ticker"].tolist() == ["TEST"]


def test_first_50_contains_50_unique_tickers():
    assert len(tickers) == 50
    assert len(set(tickers)) == 50
