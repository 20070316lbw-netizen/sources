"""兼容旧 ``sources.cn.stock_basic`` 导入路径的证券资料接口。"""
from sources.ashare.stock_basic import STOCK_BASIC_COLUMNS, get_cn_stock_basic

__all__ = ["STOCK_BASIC_COLUMNS", "get_cn_stock_basic"]
