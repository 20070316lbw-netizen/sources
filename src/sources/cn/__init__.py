"""sources.cn: A 股数据抓取(数据源: BaoStock)

和美股部分一样只负责抓取与字段级清洗, 不做存储。代码统一为 `600519.SH`
格式, 日期统一为不带时区的时间戳。

公开 API:
    get_cn_prices                 -- 日线, 列与 sources.get_prices 一致(adj_close 为后复权)
    get_cn_daily_bars             -- 日线 + 成交额/前收/换手/涨跌幅/停牌/ST 标记
    get_cn_intraday_bars          -- 分钟线(5/15/30/60), ts 为 bar 结束时间; 个股/ETF, 无指数
    get_cn_trade_calendar         -- 交易日历
    get_cn_stock_basic            -- 证券基本资料(上市/退市日期, 含已退市)
    get_cn_index_members          -- 某一天的指数成分快照(目前只支持沪深300)
    get_cn_index_members_history  -- 按月等频率拼接的历史成分
    normalize_ticker              -- 代码格式统一

BaoStock 是进程级全局会话, 这些函数各自会登录/登出; 批量调用时可以用
`with session():` 包住, 只登录一次。不是线程安全的。
"""
from __future__ import annotations

from sources.cn._baostock import BaostockError, session
from sources.cn.codes import normalize_ticker
from sources.cn.index_members import get_cn_index_members, get_cn_index_members_history
from sources.cn.intraday import get_cn_intraday_bars
from sources.cn.prices import get_cn_daily_bars, get_cn_prices
from sources.cn.stock_basic import get_cn_stock_basic
from sources.cn.trade_calendar import get_cn_trade_calendar

__all__ = [
    "BaostockError",
    "get_cn_daily_bars",
    "get_cn_index_members",
    "get_cn_index_members_history",
    "get_cn_intraday_bars",
    "get_cn_prices",
    "get_cn_stock_basic",
    "get_cn_trade_calendar",
    "normalize_ticker",
    "session",
]
