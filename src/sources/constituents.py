"""兼容旧 ``sources.constituents`` 导入路径的 S&P 500 成分组件。"""
import sys

from sources.sp500 import constituents as _implementation

sys.modules[__name__] = _implementation
