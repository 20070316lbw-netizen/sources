"""旧路径到 sp500.sec.tickers 的兼容别名。"""
import sys

from sources.sp500.sec import tickers as _implementation

sys.modules[__name__] = _implementation
