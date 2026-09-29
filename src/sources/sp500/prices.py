"""S&P 500 行情组件, 复用 yfinance 抓取与标准化实现。"""
from sources.prices import get_prices

__all__ = ["get_prices"]
