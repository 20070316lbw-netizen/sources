from unittest.mock import MagicMock

import pandas as pd
import pytest

import sources.roe as roe_module
from sources.map.first_50 import tickers
from sources.roe import calculate_roe, get_roe, get_roe_batch


@pytest.fixture(autouse=True)
def _edgar_identity(monkeypatch):
    monkeypatch.setenv("EDGAR_IDENTITY", "Test User test@example.com")


def _income_statement() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "standard_concept": ["NetIncomeToCommonShareholders", "NetIncome"],
            "2024-12-31": [None, 120.0],
            "2023-12-31": [90.0, 100.0],
        }
    )


def _balance_sheet() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "standard_concept": ["AllEquityBalance"],
            "2024-12-31": [600.0],
            "2023-12-31": [400.0],
        }
    )


def _mock_edgar(monkeypatch, failing_ticker: str | None = None) -> list[str]:
    filings = MagicMock()
    filings.filter.return_value.head.return_value = filings
    filings.__len__.return_value = 2
    requested_tickers: list[str] = []

    def company_factory(ticker: str):
        requested_tickers.append(ticker)
        if ticker == failing_ticker:
            raise RuntimeError("SEC unavailable")
        company = MagicMock()
        company.get_filings.return_value = filings
        return company

    xbrls = MagicMock()
    xbrls.statements.income_statement.return_value.to_dataframe.return_value = (
        _income_statement()
    )
    xbrls.statements.balance_sheet.return_value.to_dataframe.return_value = (
        _balance_sheet()
    )

    monkeypatch.setattr(roe_module, "Company", company_factory)
    monkeypatch.setattr(roe_module.XBRLS, "from_filings", lambda _: xbrls)
    monkeypatch.setattr(roe_module, "set_identity", lambda _: None)
    return requested_tickers


def test_calculate_roe_uses_average_equity_and_period_fallback():
    result = calculate_roe("aapl", _income_statement(), _balance_sheet())

    assert result.loc[0, "ticker"] == "AAPL"
    assert result.loc[0, "net_income"] == 120.0
    assert result.loc[0, "average_equity"] == 500.0
    assert result.loc[0, "roe"] == 0.24
    assert result.loc[0, "roe_percent"] == 24.0


def test_get_roe_fetches_and_calculates_one_year(monkeypatch):
    _mock_edgar(monkeypatch)

    result = get_roe("AAPL")

    assert result[["ticker", "roe_percent"]].to_dict("records") == [
        {"ticker": "AAPL", "roe_percent": 24.0}
    ]


def test_get_roe_batch_skips_failed_ticker(monkeypatch):
    _mock_edgar(monkeypatch, failing_ticker="BAD")

    result = get_roe_batch(["AAPL", "BAD", "MSFT"])

    assert result["ticker"].tolist() == ["AAPL", "MSFT"]


def test_get_roe_batch_defaults_to_first_50(monkeypatch):
    requested_tickers = _mock_edgar(monkeypatch)

    result = get_roe_batch()

    assert requested_tickers == tickers
    assert result["ticker"].tolist() == tickers


def test_get_roe_requires_edgar_identity(monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY")

    with pytest.raises(RuntimeError, match="EDGAR_IDENTITY"):
        get_roe("AAPL")


def test_get_roe_batch_requires_identity_before_processing(monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY")

    with pytest.raises(RuntimeError, match="EDGAR_IDENTITY"):
        get_roe_batch([])


def test_first_50_contains_50_unique_tickers():
    assert len(tickers) == 50
    assert len(set(tickers)) == 50
