from sources.error import (
    DataFetchError,
    EdgarFetchError,
    QuantLabError,
    WikiFetchError,
    YahooFetchError,
)


def test_error_inheritance():
    """测试自定义异常体系继承结构"""
    assert issubclass(DataFetchError, QuantLabError)

    assert issubclass(WikiFetchError, DataFetchError)
    assert issubclass(YahooFetchError, DataFetchError)
    assert issubclass(EdgarFetchError, DataFetchError)


def test_edgar_fetch_error_with_status_code():
    """带 status_code 时, 消息应拼成 'CIK xxx 抓取失败, 状态码 xxx'"""
    err = EdgarFetchError("0000320193", status_code=404)
    assert err.cik == "0000320193"
    assert err.status_code == 404
    assert "0000320193" in str(err)
    assert "404" in str(err)


def test_edgar_fetch_error_plain_message():
    """不带 status_code 时, 按普通异常处理, cik 为空"""
    err = EdgarFetchError("网络连接超时")
    assert err.cik == ""
    assert err.status_code is None
    assert "网络连接超时" in str(err)
