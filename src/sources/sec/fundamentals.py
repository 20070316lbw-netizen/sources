"""旧路径到 sp500.sec.fundamentals 的兼容别名。"""
import sys

from sources.sp500.sec import fundamentals as _implementation

sys.modules[__name__] = _implementation
