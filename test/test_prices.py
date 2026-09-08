from unittest.mock import patch

import pandas as pd
import pytest

from sources.prices import get_prices

_EXPECTED_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def _multi_ticker_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=2, freq="D")
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    columns = pd.MultiIndex.from_product([["AAPL", "MSFT"], fields])
    data = [[float(i * 10 + j) for j in range(len(columns))] for i in range(len(dates))]
    df = pd.DataFrame(data, index=dates, columns=columns)
    df.index.name = "Date"
    return df


def _single_ticker_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=2, freq="D")
    df = pd.DataFrame(
        {
            "Open": [1.0, 2.0],
            "High": [1.5, 2.5],
            "Low": [0.5, 1.5],
            "Close": [1.2, 2.2],
            "Adj Close": [1.1, 2.1],
            "Volume": [100, 200],
        },
        index=dates,
    )
    df.index.name = "Date"
    return df


@patch("sources.prices.yf.download")
def test_get_prices_multi_ticker_shape(mock_download):
    mock_download.return_value = _multi_ticker_frame()

    df = get_prices(["AAPL", "MSFT"], start="2024-01-01", end="2024-01-03")

    assert list(df.columns) == _EXPECTED_COLUMNS
    assert set(df["ticker"]) == {"AAPL", "MSFT"}
    assert len(df) == 4


@patch("sources.prices.yf.download")
def test_get_prices_single_ticker(mock_download):
    mock_download.return_value = _single_ticker_frame()

    df = get_prices("AAPL", start="2024-01-01")

    assert (df["ticker"] == "AAPL").all()
    assert len(df) == 2
    assert df["close"].tolist() == [1.2, 2.2]


@patch("sources.prices.yf.download")
def test_missing_ticker_in_response_is_skipped(mock_download):
    # 只返回 AAPL 的数据, 但请求了 AAPL 和 NOPE
    frame = _multi_ticker_frame()
    mock_download.return_value = frame[["AAPL"]]

    df = get_prices(["AAPL", "NOPE"], start="2024-01-01")

    assert set(df["ticker"]) == {"AAPL"}


@patch("sources.prices.yf.download")
def test_get_prices_empty_result_keeps_schema(mock_download):
    mock_download.return_value = pd.DataFrame()

    df = get_prices("NOPE", start="2024-01-01")

    assert df.empty
    assert list(df.columns) == _EXPECTED_COLUMNS


def test_get_prices_rejects_empty_tickers():
    with pytest.raises(ValueError):
        get_prices([], start="2024-01-01")
