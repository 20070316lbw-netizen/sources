"""兼容旧 ``sources.cn`` 导入路径的 A 股代码转换函数。"""
from sources.ashare.codes import from_baostock_code, normalize_ticker, to_baostock_code

__all__ = ["from_baostock_code", "normalize_ticker", "to_baostock_code"]
