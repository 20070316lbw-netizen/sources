from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from sources.listings import get_exchange_listings

_EXPECTED_COLUMNS = ["ticker", "cik", "name", "exchange"]

_FAKE_PAYLOAD = {
    "fields": ["cik", "name", "ticker", "exchange"],
    "data": [
        [320193, "Apple Inc.", "AAPL", "Nasdaq"],
        [789019, "MICROSOFT CORP", "MSFT", "Nasdaq"],
        [1018724, "AMAZON COM INC", "AMZN", ""],
    ],
}


@pytest.fixture(autouse=True)
def _edgar_identity(monkeypatch):
    monkeypatch.setenv("EDGAR_IDENTITY", "Test User test@example.com")


@patch("sources.listings.get_with_retry")
def test_get_exchange_listings_basic(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _FAKE_PAYLOAD
    mock_get.return_value = mock_resp

    df = get_exchange_listings()

    assert list(df.columns) == _EXPECTED_COLUMNS
    assert len(df) == 3
    # User-Agent 应该带上身份标识
    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["User-Agent"] == "Test User test@example.com"


@patch("sources.listings.get_with_retry")
def test_empty_exchange_becomes_missing(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _FAKE_PAYLOAD
    mock_get.return_value = mock_resp

    df = get_exchange_listings()

    amzn_row = df[df["ticker"] == "AMZN"].iloc[0]
    assert pd.isna(amzn_row["exchange"])


@patch("sources.listings.get_with_retry")
def test_filters_to_requested_tickers(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _FAKE_PAYLOAD
    mock_get.return_value = mock_resp

    df = get_exchange_listings(["AAPL", "NOPE"])

    assert set(df["ticker"]) == {"AAPL"}


@patch("sources.listings.get_with_retry")
def test_single_ticker_string(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _FAKE_PAYLOAD
    mock_get.return_value = mock_resp

    df = get_exchange_listings("MSFT")

    assert list(df["ticker"]) == ["MSFT"]


@patch("sources.listings.get_with_retry")
def test_empty_payload_keeps_schema(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"fields": [], "data": []}
    mock_get.return_value = mock_resp

    df = get_exchange_listings()

    assert df.empty
    assert list(df.columns) == _EXPECTED_COLUMNS


def test_missing_identity_env_raises(monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)

    with pytest.raises(RuntimeError):
        get_exchange_listings()
