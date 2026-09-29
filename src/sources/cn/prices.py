"""兼容旧 ``sources.cn.prices`` 导入路径的 A 股日线接口。"""
from sources.ashare.prices import (
    BAR_COLUMNS,
    PRICE_COLUMNS,
    STATUS_COLUMNS,
    get_cn_daily_bars,
    get_cn_prices,
)

__all__ = ["BAR_COLUMNS", "PRICE_COLUMNS", "STATUS_COLUMNS", "get_cn_daily_bars", "get_cn_prices"]
