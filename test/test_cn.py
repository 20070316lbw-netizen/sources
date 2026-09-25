"""sources.cn 的单元测试: 用假的 baostock 模块替身, 不走网络。"""
from __future__ import annotations

import pandas as pd
import pytest

from sources.cn import (
    BaostockError,
    _baostock,
    get_cn_daily_bars,
    get_cn_index_members,
    get_cn_index_members_history,
    get_cn_intraday_bars,
    get_cn_prices,
    get_cn_stock_basic,
    get_cn_trade_calendar,
    normalize_ticker,
    session,
)
from sources.cn.codes import from_baostock_code, to_baostock_code
from sources.cn.intraday import INTRADAY_COLUMNS

_PRICE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


class FakeResult:
    """模拟 baostock.data.resultset.ResultData 的最小接口(按页返回)。"""

    def __init__(self, fields, pages, error_code="0", error_msg="success", fail_on_page=None):
        self.fields = fields
        self._pages = [list(p) for p in pages] or [[]]
        self._page = 0
        self._row = 0
        self.error_code = error_code
        self.error_msg = error_msg
        self._fail_on_page = fail_on_page

    def next(self):
        if self._row < len(self._pages[self._page]):
            return True
        if self._page + 1 >= len(self._pages):
            return False
        if self._fail_on_page == self._page + 1:
            self.error_code = "10002007"
            self.error_msg = "网络接收错误"
            return False
        self._page += 1
        self._row = 0
        return self.next()

    def get_row_data(self):
        row = self._pages[self._page][self._row]
        self._row += 1
        return row


class FakeBaostock:
    def __init__(self):
        self.logins = 0
        self.logouts = 0
        self.api_key = None
        self.login_code = "0"
        self.calls: list[tuple[str, tuple, dict]] = []
        self.responses: dict[str, object] = {}

    def login(self):
        self.logins += 1
        return FakeResult([], [], error_code=self.login_code, error_msg="bad login")

    def logout(self):
        self.logouts += 1

    def set_API_key(self, key):
        self.api_key = key

    def __getattr__(self, name):
        if not name.startswith("query_"):
            raise AttributeError(name)

        def _call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            resp = self.responses[name]
            return resp(*args, **kwargs) if callable(resp) else resp

        return _call


@pytest.fixture
def fake_bs(monkeypatch):
    fake = FakeBaostock()
    monkeypatch.setattr(_baostock, "bs", fake)
    monkeypatch.delenv(_baostock.API_KEY_ENV_VAR, raising=False)
    return fake


# ---------------------------------------------------------------- codes

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("600519.SH", "600519.SH"),
        ("600519.sh", "600519.SH"),
        ("sh.600519", "600519.SH"),
        ("SZ000001", "000001.SZ"),
        ("000001", "000001.SZ"),
        ("300750", "300750.SZ"),
        ("688981", "688981.SH"),
        ("430047", "430047.BJ"),
        (" 000300.SH ", "000300.SH"),
    ],
)
def test_normalize_ticker(raw, expected):
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["AAPL", "60051", "600519.HK", "", "7000001"])
def test_normalize_ticker_rejects_garbage(raw):
    with pytest.raises(ValueError):
        normalize_ticker(raw)


def test_baostock_code_roundtrip():
    assert to_baostock_code("600519.SH") == "sh.600519"
    assert to_baostock_code("000001") == "sz.000001"
    assert from_baostock_code("sz.000001") == "000001.SZ"


# ---------------------------------------------------------------- session / query

def test_session_nested_logs_in_once(fake_bs):
    with session(), session():
        pass
    assert fake_bs.logins == 1
    assert fake_bs.logouts == 1


def test_session_uses_api_key_env(fake_bs, monkeypatch):
    monkeypatch.setenv(_baostock.API_KEY_ENV_VAR, "bs-xyz")
    with session():
        pass
    assert fake_bs.api_key == "bs-xyz"


def test_session_login_failure_raises(fake_bs):
    fake_bs.login_code = "10001001"
    with pytest.raises(BaostockError, match="登录失败"), session():
        pass


def test_query_reads_all_pages(fake_bs):
    fake_bs.responses["query_trade_dates"] = FakeResult(
        ["calendar_date", "is_trading_day"],
        [[["2024-01-01", "0"], ["2024-01-02", "1"]], [["2024-01-03", "1"]]],
    )
    with session():
        df = _baostock.query("query_trade_dates")
    assert len(df) == 3


def test_query_raises_when_paging_fails(fake_bs):
    fake_bs.responses["query_trade_dates"] = FakeResult(
        ["calendar_date", "is_trading_day"],
        [[["2024-01-01", "0"]], [["2024-01-02", "1"]]],
        fail_on_page=1,
    )
    with session(), pytest.raises(BaostockError, match="网络接收错误"):
        _baostock.query("query_trade_dates")


# ---------------------------------------------------------------- prices

_RAW_FIELDS = [
    "date", "code", "open", "high", "low", "close", "preclose", "volume",
    "amount", "turn", "tradestatus", "pctChg", "isST",
]


def _raw_rows(code):
    return [
        ["2024-01-02", code, "10", "11", "9.5", "10.5", "10", "1000", "10500", "0.5", "1", "5.0",
         "0"],
        ["2024-01-03", code, "10.5", "10.5", "10.5", "10.5", "10.5", "0", "0", "", "0", "0", "0"],
        ["2024-01-04", code, "", "", "", "", "10.5", "", "", "", "1", "", "1"],
    ]


def _kline_response(failing=()):
    def respond(code, fields, *, start_date, end_date, frequency, adjustflag):
        if code in failing:
            return FakeResult([], [], error_code="10004011", error_msg="code err")
        if adjustflag == "1":
            return FakeResult(
                ["date", "close"],
                [[["2024-01-02", "105"], ["2024-01-03", "105"], ["2024-01-04", ""]]],
            )
        return FakeResult(_RAW_FIELDS, [_raw_rows(code)])

    return respond


def test_get_cn_daily_bars_cleans_and_merges(fake_bs):
    fake_bs.responses["query_history_k_data_plus"] = _kline_response()

    df = get_cn_daily_bars(["600519.SH", "sz.000001"], start="2024-01-01", end="2024-01-05")

    assert fake_bs.logins == 1
    assert set(df["ticker"]) == {"600519.SH", "000001.SZ"}
    # 第三行 close 为空被丢弃
    assert len(df) == 4
    row = df[(df["ticker"] == "600519.SH")].iloc[0]
    assert row["date"] == pd.Timestamp("2024-01-02")
    assert row["close"] == 10.5
    assert row["adj_close"] == 105
    assert row["pre_close"] == 10
    assert row["amount"] == 10500
    assert not row["is_suspended"]
    suspended = df[(df["ticker"] == "600519.SH")].iloc[1]
    assert suspended["is_suspended"]
    assert pd.isna(suspended["turnover"])
    # 请求的是不复权 + 后复权两次
    flags = {c[2]["adjustflag"] for c in fake_bs.calls}
    assert flags == {"1", "3"}
    assert fake_bs.calls[0][1][0] == "sh.600519"
    assert fake_bs.calls[0][2]["end_date"] == "2024-01-05"


def test_get_cn_prices_matches_us_schema(fake_bs):
    fake_bs.responses["query_history_k_data_plus"] = _kline_response()
    df = get_cn_prices("600519.SH", start="2024-01-01")
    assert list(df.columns) == _PRICE_COLUMNS
    assert df["ticker"].tolist() == ["600519.SH", "600519.SH"]


def test_failing_ticker_is_skipped(fake_bs):
    fake_bs.responses["query_history_k_data_plus"] = _kline_response(failing={"sz.000001"})
    df = get_cn_prices(["600519.SH", "000001.SZ"], start="2024-01-01")
    assert set(df["ticker"]) == {"600519.SH"}


def test_all_empty_keeps_schema(fake_bs):
    fake_bs.responses["query_history_k_data_plus"] = FakeResult(_RAW_FIELDS, [])
    df = get_cn_prices("600519.SH", start="2024-01-01")
    assert df.empty
    assert list(df.columns) == _PRICE_COLUMNS


def test_empty_tickers_raises():
    with pytest.raises(ValueError):
        get_cn_prices([], start="2024-01-01")


# ---------------------------------------------------------------- calendar / basic / index

def test_trade_calendar(fake_bs):
    fake_bs.responses["query_trade_dates"] = FakeResult(
        ["calendar_date", "is_trading_day"], [[["2024-01-02", "1"], ["2024-01-01", "0"]]]
    )
    df = get_cn_trade_calendar("2024-01-01", "2024-01-02")
    assert list(df.columns) == ["date", "is_open"]
    assert df["is_open"].tolist() == [False, True]
    assert fake_bs.calls[0][2] == {"start_date": "2024-01-01", "end_date": "2024-01-02"}


def test_stock_basic(fake_bs):
    fake_bs.responses["query_stock_basic"] = FakeResult(
        ["code", "code_name", "ipoDate", "outDate", "type", "status"],
        [[
            ["sh.600519", "贵州茅台", "2001-08-27", "", "1", "1"],
            ["sz.000024", "招商地产", "1993-06-07", "2015-12-30", "1", "0"],
            ["sh.000300", "沪深300", "2002-01-04", "", "2", "1"],
        ]],
    )
    df = get_cn_stock_basic()
    assert df["ticker"].tolist() == ["000024.SZ", "000300.SH", "600519.SH"]
    delisted = df.set_index("ticker").loc["000024.SZ"]
    assert delisted["delist_date"] == pd.Timestamp("2015-12-30")
    assert not delisted["is_listed"]
    assert pd.isna(df.set_index("ticker").loc["600519.SH", "delist_date"])
    assert df.set_index("ticker").loc["000300.SH", "sec_type"] == "index"


def test_stock_basic_per_ticker(fake_bs):
    fake_bs.responses["query_stock_basic"] = FakeResult(
        ["code", "code_name", "ipoDate", "outDate", "type", "status"],
        [[["sh.600519", "贵州茅台", "2001-08-27", "", "1", "1"]]],
    )
    get_cn_stock_basic("600519.SH")
    assert fake_bs.calls[0][2] == {"code": "sh.600519"}


def _hs300_response(date):
    return FakeResult(
        ["updateDate", "code", "code_name"],
        [[
            ["2024-06-17", "sz.000001", "平安银行"],
            ["2024-06-17", "sh.600519", "贵州茅台"],
        ]],
    )


def test_index_members_snapshot(fake_bs):
    fake_bs.responses["query_hs300_stocks"] = _hs300_response
    df = get_cn_index_members("hs300", "2024-07-01")
    assert list(df.columns) == ["index_code", "date", "ticker", "name", "update_date"]
    assert (df["index_code"] == "000300.SH").all()
    assert (df["date"] == pd.Timestamp("2024-07-01")).all()
    assert df["ticker"].tolist() == ["000001.SZ", "600519.SH"]
    assert fake_bs.calls[0][2] == {"date": "2024-07-01"}


def test_index_members_accepts_index_code(fake_bs):
    fake_bs.responses["query_hs300_stocks"] = _hs300_response
    assert not get_cn_index_members("000300.SH", "2024-07-01").empty


def test_index_members_unknown_index():
    with pytest.raises(ValueError, match="不支持的指数"):
        get_cn_index_members("zz1000")


def test_index_members_history(fake_bs):
    fake_bs.responses["query_hs300_stocks"] = _hs300_response
    df = get_cn_index_members_history("hs300", "2024-01-01", "2024-03-15")
    expected = pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])
    assert sorted(df["date"].unique()) == list(expected)
    assert len(df) == 6
    assert fake_bs.logins == 1


# ---------------------------------------------------------------- intraday

_INTRADAY_FIELDS = ["date", "time", "code", "open", "high", "low", "close", "volume", "amount"]


def _intraday_response(failing=(), empty=()):
    def respond(code, fields, *, start_date, end_date, frequency, adjustflag):
        if code in failing:
            return FakeResult([], [], error_code="10004011", error_msg="code err")
        if code in empty:
            return FakeResult(_INTRADAY_FIELDS, [])
        if adjustflag == "1":
            return FakeResult(
                ["time", "close"],
                [[["20260921100000000", "46.0"], ["20260921103000000", "45.9"]]],
            )
        return FakeResult(_INTRADAY_FIELDS, [[
            ["2026-09-21", "20260921103000000", code, "4.599", "4.607", "4.594", "4.596",
             "35722100", "164313754.0"],
            ["2026-09-21", "20260921100000000", code, "4.586", "4.614", "4.586", "4.598",
             "234271620", "1079208294.0"],
            ["2026-09-21", "bad", code, "1", "1", "1", "1", "1", "1"],
            ["2026-09-21", "20260921110000000", code, "", "", "", "", "", ""],
        ]])

    return respond


def test_intraday_cleans_and_merges(fake_bs):
    fake_bs.responses["query_history_k_data_plus"] = _intraday_response()

    df = get_cn_intraday_bars("sh.510300", start="2026-09-21", end="2026-09-21")

    assert list(df.columns) == INTRADAY_COLUMNS
    # "bad" 时间与 close 为空的两行被丢弃; 乱序输入按 ts 排好
    assert df["ts"].tolist() == pd.to_datetime(
        ["2026-09-21 10:00:00", "2026-09-21 10:30:00"]
    ).tolist()
    first = df.iloc[0]
    assert first["ticker"] == "510300.SH"
    assert first["close"] == 4.598
    assert first["adj_close"] == 46.0
    assert first["volume"] == 234271620
    assert first["amount"] == 1079208294.0
    # 不复权 + 后复权两次请求, 频率透传
    assert {c[2]["adjustflag"] for c in fake_bs.calls} == {"1", "3"}
    assert {c[2]["frequency"] for c in fake_bs.calls} == {"30"}
    assert fake_bs.calls[0][1][0] == "sh.510300"
    assert fake_bs.calls[0][2]["end_date"] == "2026-09-21"


def test_intraday_accepts_int_freq(fake_bs):
    fake_bs.responses["query_history_k_data_plus"] = _intraday_response()
    get_cn_intraday_bars("510300.SH", start="2026-09-21", freq=60)
    assert {c[2]["frequency"] for c in fake_bs.calls} == {"60"}


@pytest.mark.parametrize("freq", ["d", "1", "120", 45])
def test_intraday_rejects_bad_freq(freq):
    with pytest.raises(ValueError, match="不支持的 freq"):
        get_cn_intraday_bars("510300.SH", start="2026-09-21", freq=freq)


def test_intraday_skips_failing_and_empty(fake_bs):
    fake_bs.responses["query_history_k_data_plus"] = _intraday_response(
        failing={"sz.159915"}, empty={"sh.000300"},
    )
    df = get_cn_intraday_bars(
        ["510300.SH", "159915.SZ", "000300.SH"], start="2026-09-21",
    )
    assert set(df["ticker"]) == {"510300.SH"}
    assert fake_bs.logins == 1


def test_intraday_all_empty_keeps_schema(fake_bs):
    fake_bs.responses["query_history_k_data_plus"] = FakeResult(_INTRADAY_FIELDS, [])
    df = get_cn_intraday_bars("000300.SH", start="2026-09-21")
    assert df.empty
    assert list(df.columns) == INTRADAY_COLUMNS


def test_intraday_empty_tickers_raises():
    with pytest.raises(ValueError):
        get_cn_intraday_bars([], start="2026-09-21")
