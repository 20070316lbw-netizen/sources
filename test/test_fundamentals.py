from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from sources.fundamentals import DEFAULT_CONCEPTS, get_fundamentals, get_fundamentals_batch

_EXPECTED_COLUMNS = [
    "ticker",
    "concept",
    "period_start",
    "period_end",
    "duration_days",
    "numeric_value",
    "fiscal_period",
    "fiscal_year",
]


@pytest.fixture(autouse=True)
def _edgar_identity(monkeypatch):
    monkeypatch.setenv("EDGAR_IDENTITY", "Test User test@example.com")


def _fake_time_series() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "period_start": [pd.Timestamp("2023-01-01")],
            "period_end": [pd.Timestamp("2023-12-31")],
            "duration_days": [364],
            "numeric_value": [1000.0],
            "fiscal_period": ["FY"],
            "fiscal_year": [2023],
        }
    )


@patch("edgar.set_identity")
@patch("edgar.Company")
def test_get_fundamentals_basic(mock_company_cls, mock_set_identity):
    mock_facts = MagicMock()
    mock_facts.time_series.side_effect = lambda concept, periods=20: _fake_time_series()
    mock_company = MagicMock()
    mock_company.get_facts.return_value = mock_facts
    mock_company_cls.return_value = mock_company

    df = get_fundamentals("AAPL", concepts=("StockholdersEquity",))

    mock_set_identity.assert_called_once()
    assert list(df.columns) == _EXPECTED_COLUMNS
    assert len(df) == 1
    assert df.loc[0, "concept"] == "StockholdersEquity"
    assert df.loc[0, "ticker"] == "AAPL"


@patch("edgar.set_identity")
@patch("edgar.Company")
def test_missing_concept_is_skipped_not_fatal(mock_company_cls, mock_set_identity):
    mock_facts = MagicMock()
    mock_facts.time_series.return_value = pd.DataFrame()
    mock_company = MagicMock()
    mock_company.get_facts.return_value = mock_facts
    mock_company_cls.return_value = mock_company

    df = get_fundamentals("AAPL", concepts=("NotARealConcept",))

    assert df.empty
    assert list(df.columns) == _EXPECTED_COLUMNS


@patch("edgar.set_identity")
@patch("edgar.Company")
def test_company_not_found_returns_empty(mock_company_cls, mock_set_identity):
    import edgar

    mock_company_cls.side_effect = edgar.CompanyNotFoundError("XXXX")

    df = get_fundamentals("XXXX")

    assert df.empty


def test_missing_identity_env_raises(monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)

    with pytest.raises(RuntimeError):
        get_fundamentals("AAPL")


@patch("edgar.set_identity")
@patch("edgar.Company")
def test_batch_skips_failed_ticker_but_keeps_others(mock_company_cls, mock_set_identity):
    def side_effect(ticker):
        if ticker == "BAD":
            raise RuntimeError("boom")
        mock_facts = MagicMock()
        mock_facts.time_series.side_effect = lambda concept, periods=20: _fake_time_series()
        mock_company = MagicMock()
        mock_company.get_facts.return_value = mock_facts
        return mock_company

    mock_company_cls.side_effect = side_effect

    df = get_fundamentals_batch(["AAPL", "BAD"], concepts=("StockholdersEquity",))

    assert set(df["ticker"]) == {"AAPL"}


def test_default_concepts_cover_book_value_inputs():
    assert "StockholdersEquity" in DEFAULT_CONCEPTS
    assert "CommonStockSharesOutstanding" in DEFAULT_CONCEPTS
