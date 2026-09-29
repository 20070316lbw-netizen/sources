"""兼容旧 ``sources.prices`` 导入路径的 Yahoo Finance 行情组件。"""
import sys

from sources.sp500 import prices as _implementation

sys.modules[__name__] = _implementation
