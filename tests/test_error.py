import pytest
from sources.error import (
    DataFetchError,
    EdgarFetchError,
    EdgarLoadError,
    PgsqlError,
    QuantLabError,
    SchemaInitializationError,
    UniverseLoadError,
    WikiFetchError,
    YahooFetchError,
    YahooLoadError,
)


def test_error_inheritance():
    """测试自定义异常体系继承结构"""
    # 根异常
    assert issubclass(DataFetchError, QuantLabError)
    assert issubclass(PgsqlError, QuantLabError)

    # 数据抓取类异常
    assert issubclass(WikiFetchError, DataFetchError)
    assert issubclass(YahooFetchError, DataFetchError)
    assert issubclass(EdgarFetchError, DataFetchError)

    # 存储入库类异常
    assert issubclass(SchemaInitializationError, PgsqlError)
    assert issubclass(UniverseLoadError, PgsqlError)
    assert issubclass(YahooLoadError, PgsqlError)
    assert issubclass(EdgarLoadError, PgsqlError)


def test_edgar_fetch_error_format():
    """测试 EdgarFetchError 错误信息格式化"""
    err = EdgarFetchError("0000320193", status_code=404)
    assert err.cik == "0000320193"
    assert err.status_code == 404
    assert "0000320193" in str(err)
    assert "404" in str(err)

    msg_err = EdgarFetchError("网络连接超时")
    assert msg_err.cik == ""
    assert msg_err.status_code is None
    assert "网络连接超时" in str(msg_err)
