"""个人量化数据源工具库。

三个子包各管一个数据源, 按需导入 (顶层不做 re-export, 避免 `import sources`
就把 yfinance / edgartools 这些重量级依赖全拉起来)::

    from sources.universe import fetch_sp500_universe, load_sp500_list
    from sources.yahoo import fetch_prices, save_prices, load_prices
    from sources.sec import fetch_sec, to_daily_pit, load_fundamentals
"""

__version__ = "0.1.0"
