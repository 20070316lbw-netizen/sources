"""兼容旧 ``sources.cn.trade_calendar`` 导入路径的交易日历接口。"""
from sources.ashare.calendar import CALENDAR_COLUMNS, get_cn_trade_calendar

__all__ = ["CALENDAR_COLUMNS", "get_cn_trade_calendar"]
