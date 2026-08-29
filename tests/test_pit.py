import pandas as pd
import pytest

from sources.sec.fetch import to_daily_pit


def test_to_daily_pit_empty_raises():
    """测试空 DataFrame 抛出 ValueError"""
    empty_df = pd.DataFrame()
    with pytest.raises(ValueError, match="输入的基本面数据为空"):
        to_daily_pit(empty_df)


def test_to_daily_pit_alignment_and_ffill():
    """测试 PIT 对齐与前向填充 (ffill)"""
    # 构造两支标的的模拟财报披露数据
    raw_data = pd.DataFrame(
        [
            {"date": "2024-01-02", "ticker": "AAPL", "revenue": 100.0,
             "net_income": 20.0, "form": "10-Q"},
            {"date": "2024-01-05", "ticker": "AAPL", "revenue": 110.0,
             "net_income": 25.0, "form": "10-Q"},
            {"date": "2024-01-02", "ticker": "MSFT", "revenue": 80.0,
             "net_income": 15.0, "form": "10-Q"},
        ]
    )

    trading_days = pd.date_range("2024-01-02", "2024-01-08", freq="D")
    daily_pit = to_daily_pit(raw_data, trading_days=trading_days)

    # 验证 MultiIndex 结构
    assert daily_pit.index.names == ["Date", "Ticker"]

    # 验证辅助字段已被剔除，保留数值指标
    assert "form" not in daily_pit.columns
    assert "revenue" in daily_pit.columns
    assert "net_income" in daily_pit.columns

    # 验证 AAPL 在 2024-01-02 到 2024-01-04 期间数值为 100.0 (ffill)
    idx_jan3_aapl = (pd.Timestamp("2024-01-03"), "AAPL")
    assert daily_pit.loc[idx_jan3_aapl, "revenue"] == 100.0

    # 验证 AAPL 在 2024-01-05 更新为 110.0
    idx_jan5_aapl = (pd.Timestamp("2024-01-05"), "AAPL")
    assert daily_pit.loc[idx_jan5_aapl, "revenue"] == 110.0
