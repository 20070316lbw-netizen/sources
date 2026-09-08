from unittest.mock import patch

import pandas as pd
import pytest

from sources.riskfree import DEFAULT_SERIES, get_risk_free_rate

_EXPECTED_COLUMNS = ["date", "series", "value"]


def _fake_fred_frame(series: str) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=3, freq="D")
    return pd.DataFrame({series: [5.30, 5.31, float("nan")]}, index=dates)


@patch("sources.riskfree.pdr.DataReader")
def test_get_risk_free_rate_basic(mock_reader):
    mock_reader.return_value = _fake_fred_frame("DGS1MO")

    df = get_risk_free_rate(start="2024-01-01", end="2024-01-05")

    assert list(df.columns) == _EXPECTED_COLUMNS
    # 第三行 NaN 应该被丢弃
    assert len(df) == 2
    assert (df["series"] == "DGS1MO").all()


@patch("sources.riskfree.pdr.DataReader")
def test_multiple_series_are_concatenated(mock_reader):
    def side_effect(series, source, start, end):
        return _fake_fred_frame(series)

    mock_reader.side_effect = side_effect

    df = get_risk_free_rate(start="2024-01-01", series=["DGS1MO", "TB3MS"])

    assert set(df["series"]) == {"DGS1MO", "TB3MS"}


@patch("sources.riskfree.pdr.DataReader")
def test_one_series_fails_others_still_returned(mock_reader):
    def side_effect(series, source, start, end):
        if series == "BAD":
            raise RuntimeError("boom")
        return _fake_fred_frame(series)

    mock_reader.side_effect = side_effect

    df = get_risk_free_rate(start="2024-01-01", series=["DGS1MO", "BAD"])

    assert set(df["series"]) == {"DGS1MO"}


@patch("sources.riskfree.pdr.DataReader")
def test_empty_result_keeps_schema(mock_reader):
    mock_reader.return_value = pd.DataFrame()

    df = get_risk_free_rate(start="2024-01-01")

    assert df.empty
    assert list(df.columns) == _EXPECTED_COLUMNS


def test_get_risk_free_rate_rejects_empty_series():
    with pytest.raises(ValueError):
        get_risk_free_rate(start="2024-01-01", series=[])


def test_default_series_is_one_month_bill():
    assert DEFAULT_SERIES == ("DGS1MO",)
