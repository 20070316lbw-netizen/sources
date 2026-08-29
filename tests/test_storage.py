from pathlib import Path

import pandas as pd
import pytest

from sources.sec.fetch import save_fundamentals
from sources.sec.load import load_fundamentals
from sources.yahoo.fetch import save_prices
from sources.yahoo.load import load_prices


def test_prices_save_and_load(tmp_path: Path):
    """测试价格数据的保存与加载 (包含 str 与 Path 路径兼容)"""
    file_path = tmp_path / "test_prices.parquet"

    # 构造 MultiIndex 测试数据
    idx = pd.MultiIndex.from_tuples(
        [("2024-01-02", "AAPL"), ("2024-01-02", "MSFT")],
        names=["Date", "Ticker"],
    )
    df = pd.DataFrame({"close": [180.0, 370.0], "volume": [1000, 2000]}, index=idx)

    # 保存 (使用 str 路径)
    save_prices(df, path=str(file_path))
    assert file_path.exists()

    # 加载 (使用 Path 路径)
    loaded_df = load_prices(path=file_path)
    pd.testing.assert_frame_equal(df, loaded_df)


def test_prices_load_not_found(tmp_path: Path):
    """测试价格数据文件不存在时抛出 FileNotFoundError"""
    non_existent = tmp_path / "does_not_exist.parquet"
    with pytest.raises(FileNotFoundError):
        load_prices(path=non_existent)


def test_fundamentals_save_and_load(tmp_path: Path):
    """测试基本面数据的保存与加载"""
    file_path = tmp_path / "test_fund.parquet"

    idx = pd.MultiIndex.from_tuples(
        [("2024-01-02", "AAPL")],
        names=["Date", "Ticker"],
    )
    df = pd.DataFrame({"revenue": [100.0], "net_income": [20.0]}, index=idx)

    save_fundamentals(df, path=file_path)
    assert file_path.exists()

    loaded_df = load_fundamentals(path=str(file_path))
    pd.testing.assert_frame_equal(df, loaded_df)


def test_fundamentals_load_not_found(tmp_path: Path):
    """测试基本面数据文件不存在时抛出 FileNotFoundError"""
    non_existent = tmp_path / "does_not_exist_fund.parquet"
    with pytest.raises(FileNotFoundError):
        load_fundamentals(path=non_existent)
