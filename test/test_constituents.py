from unittest.mock import MagicMock, patch

import pytest

from sources.constituents import get_sp500_constituents

FAKE_HTML = """
<table>
  <tr><th>Symbol</th><th>Security</th></tr>
  <tr><td>MMM</td><td>3M</td></tr>
  <tr><td>BRK.B</td><td>Berkshire Hathaway</td></tr>
</table>
"""


@patch("sources._http.requests.get")
def test_get_sp500_constituents_basic(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = FAKE_HTML
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    df = get_sp500_constituents()

    assert list(df.columns) == ["ticker", "name"]
    assert len(df) == 2


def test_ticker_dot_to_dash_conversion():
    mock_resp = MagicMock()
    mock_resp.text = FAKE_HTML
    mock_resp.raise_for_status.return_value = None

    with patch("sources._http.requests.get", return_value=mock_resp):
        df = get_sp500_constituents()

    # BRK.B 应该被转换成 BRK-B
    assert "BRK-B" in df["ticker"].values
    assert "BRK.B" not in df["ticker"].values


@patch("sources._http.requests.get")
def test_raises_on_http_error(mock_get):
    import requests

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
    mock_resp.raise_for_status.side_effect.response = None
    mock_get.return_value = mock_resp

    with pytest.raises(requests.HTTPError):
        get_sp500_constituents()
