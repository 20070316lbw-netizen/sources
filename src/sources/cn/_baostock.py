"""让旧 BaoStock 导入路径指向新的市场组件模块实例。"""
import sys

from sources.ashare import _baostock as _implementation

sys.modules[__name__] = _implementation
