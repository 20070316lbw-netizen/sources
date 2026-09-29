"""市场组合类的默认成员名单、频率选择和缓存行为。"""
from __future__ import annotations

import pandas as pd

from sources.ashare import daily as ashare_daily
from sources.ashare import hourly as ashare_hourly
from sources.sp500 import cache as sp500_cache
from sources.sp500 import daily as sp500_daily
from sources.sp500 import hourly as sp500_hourly


def test_daily_sp500_uses_cached_members_and_ten_year_daily_interval(monkeypatch):
    """S&P 500 日线默认使用缓存名单和日历年份计算的十年起点。"""
    calls = {}
    members = pd.DataFrame({"ticker": ["AAA", "BBB"], "name": ["A", "B"]})
    monkeypatch.setattr(sp500_daily, "load_members", lambda **kwargs: members)
    monkeypatch.setattr(
        sp500_daily,
        "get_prices",
        lambda tickers, **kwargs: calls.update(tickers=tickers, **kwargs) or pd.DataFrame(),
    )

    sp500_daily.DailySp500().prices()

    assert calls["tickers"] == ["AAA", "BBB"]
    assert calls["interval"] == "1d"
    assert calls["start"] == pd.Timestamp.today().normalize() - pd.DateOffset(years=10)


def test_hour_sp500_uses_cached_members_and_hourly_interval(monkeypatch):
    """S&P 500 小时线接口使用缓存名单并请求 yfinance 小时周期。"""
    calls = {}
    monkeypatch.setattr(
        sp500_hourly,
        "load_members",
        lambda **kwargs: pd.DataFrame({"ticker": ["AAA"], "name": ["A"]}),
    )
    monkeypatch.setattr(
        sp500_hourly,
        "get_prices",
        lambda tickers, **kwargs: calls.update(tickers=tickers, **kwargs) or pd.DataFrame(),
    )

    sp500_hourly.HourSp500().prices(start="2026-01-01")

    assert calls["tickers"] == ["AAA"]
    assert calls["interval"] == "1h"


def test_daily_ashare_uses_cached_members(monkeypatch):
    """A 股日线接口未传代码时使用缓存的指数成分名单。"""
    calls = {}
    monkeypatch.setattr(
        ashare_daily,
        "load_members",
        lambda **kwargs: pd.DataFrame({"ticker": ["600000.SH"]}),
    )
    monkeypatch.setattr(
        ashare_daily,
        "get_prices",
        lambda tickers, **kwargs: calls.update(tickers=tickers, **kwargs) or pd.DataFrame(),
    )

    ashare_daily.DailyAShare().prices(start="2026-01-01")

    assert calls["tickers"] == ["600000.SH"]
    assert calls["start"] == "2026-01-01"


def test_hour_ashare_uses_cached_members_and_sixty_minute_bars(monkeypatch):
    """A 股小时线接口使用缓存成分股并固定抓取 60 分钟 K 线。"""
    calls = {}
    monkeypatch.setattr(
        ashare_hourly,
        "load_members",
        lambda **kwargs: pd.DataFrame({"ticker": ["600000.SH"]}),
    )
    monkeypatch.setattr(
        ashare_hourly,
        "get_intraday_bars",
        lambda tickers, **kwargs: calls.update(tickers=tickers, **kwargs) or pd.DataFrame(),
    )

    ashare_hourly.HourAShare().prices(start="2026-01-01")

    assert calls["tickers"] == ["600000.SH"]
    assert calls["freq"] == "60"


def test_sp500_cache_refreshes_missing_historical_snapshot(monkeypatch):
    """S&P 500 当前名单缺失时刷新统一的历史成分缓存。"""
    calls = {"load": 0, "refresh": 0}
    members = pd.DataFrame({"ticker": ["AAA"], "name": ["A"], "cik": ["1"]})

    def load_current():
        calls["load"] += 1
        if calls["load"] == 1:
            raise FileNotFoundError
        return members

    monkeypatch.setattr(sp500_cache, "load_current_constituents", load_current)
    monkeypatch.setattr(
        sp500_cache,
        "update_cache_from_web",
        lambda: calls.update(refresh=calls["refresh"] + 1),
    )

    result = sp500_cache.load_members()

    assert calls == {"load": 2, "refresh": 1}
    assert result.to_dict("records") == [{"ticker": "AAA", "name": "A"}]
