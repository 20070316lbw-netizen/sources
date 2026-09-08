from unittest.mock import patch, MagicMock

import pytest
import requests

from sources._http import get_with_retry


@patch("sources._http.time.sleep", return_value=None)
@patch("sources._http.requests.get")
def test_retries_on_5xx_then_succeeds(mock_get, mock_sleep):
    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = requests.HTTPError(response=MagicMock(status_code=503))

    ok_resp = MagicMock()
    ok_resp.raise_for_status.return_value = None

    mock_get.side_effect = [fail_resp, ok_resp]

    resp = get_with_retry("https://example.com", max_retries=3)

    assert resp is ok_resp
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


@patch("sources._http.requests.get")
def test_4xx_raises_immediately_without_retry(mock_get):
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.HTTPError(response=MagicMock(status_code=404))
    mock_get.return_value = resp

    with pytest.raises(requests.HTTPError):
        get_with_retry("https://example.com", max_retries=3)

    assert mock_get.call_count == 1


@patch("sources._http.time.sleep", return_value=None)
@patch("sources._http.requests.get")
def test_exhausts_retries_and_raises(mock_get, mock_sleep):
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.HTTPError(response=MagicMock(status_code=500))
    mock_get.return_value = resp

    with pytest.raises(requests.HTTPError):
        get_with_retry("https://example.com", max_retries=3)

    assert mock_get.call_count == 3
