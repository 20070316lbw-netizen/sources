"""兼容旧 ``sources.riskfree`` 导入路径的 FRED 利率组件。"""
import sys

from sources.sp500 import riskfree as _implementation

sys.modules[__name__] = _implementation
