"""兼容旧 ``sources.sec`` 导入路径的 SEC 基本面组件。"""
from sources.sp500.sec import *  # noqa: F403
from sources.sp500.sec import __all__ as __all__
from sources.sp500.sec import _client as _client
from sources.sp500.sec import companyfacts as companyfacts
from sources.sp500.sec import fields as fields
from sources.sp500.sec import fundamentals as fundamentals
from sources.sp500.sec import tickers as tickers
