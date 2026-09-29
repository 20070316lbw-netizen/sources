"""S&P 500 数据组件及日频、小时频组合接口。"""
from sources.sp500.daily import DailySp500
from sources.sp500.hourly import HourSp500

__all__ = ["DailySp500", "HourSp500"]
