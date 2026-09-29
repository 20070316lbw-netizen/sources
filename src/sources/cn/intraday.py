"""兼容旧 ``sources.cn.intraday`` 导入路径的分钟线接口。"""
from sources.ashare.intraday import FREQUENCIES, INTRADAY_COLUMNS, get_cn_intraday_bars

__all__ = ["FREQUENCIES", "INTRADAY_COLUMNS", "get_cn_intraday_bars"]
