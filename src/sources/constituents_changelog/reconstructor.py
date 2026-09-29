"""兼容旧路径的 S&P 500 历史成分反推实现。"""
import sys

from sources.sp500.cache.changelog import reconstructor as _implementation

sys.modules[__name__] = _implementation
