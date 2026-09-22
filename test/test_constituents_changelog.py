import datetime

import pandas as pd
import pytest

from sources._wikipedia import CHANGE_COLUMNS, CONSTITUENT_COLUMNS
from sources.constituents_changelog import (
    DATA_DIR_ENV,
    get_all_historical_sp500_tickers,
    get_historical_sp500_constituents,
    get_sp500_changelog,
    load_changelog,
    resolve_data_dir,
    update_cache_from_web,
)
from sources.constituents_changelog import reconstructor as reconstructor_module


def _current() -> pd.DataFrame:
    """当前名单: AAA / BBB / DDD。"""
    frame = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "DDD"],
            "name": ["Alpha", "Beta", "Delta"],
            "sector": ["Tech", "Tech", "Energy"],
            "sub_industry": ["Software", "Hardware", "Oil"],
            "date_added": pd.to_datetime(["2010-01-01", "2022-06-01", "2023-03-01"]),
            "cik": ["1", "2", "3"],
        }
    )
    return frame[CONSTITUENT_COLUMNS]


def _changes() -> pd.DataFrame:
    """三条变动, 覆盖「先入后出再入」的交叉情形:

        2021-05-10  CCC 纳入,  ZZZ 剔除
        2022-06-01  BBB 纳入,  CCC 剔除
        2023-03-01  DDD 纳入
    """
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-03-01", "2022-06-01", "2021-05-10"]),
            "added_ticker": ["DDD", "BBB", "CCC"],
            "added_name": ["Delta", "Beta", "Gamma"],
            "removed_ticker": ["", "CCC", "ZZZ"],
            "removed_name": ["", "Gamma", "Zeta"],
            "reason": ["IPO", "Market cap change", "Acquired"],
        }
    )
    return frame[CHANGE_COLUMNS]


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """用假数据在 tmp_path 里造一份缓存, 并把默认缓存目录指过去。"""
    monkeypatch.setattr(
        reconstructor_module,
        "fetch_sp500_tables",
        lambda: (_current(), _changes()),
    )
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    update_cache_from_web()
    return tmp_path


def test_resolve_data_dir_priority(tmp_path, monkeypatch):
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path / "from_env"))
    # 显式入参优先于环境变量
    assert resolve_data_dir(tmp_path / "explicit") == tmp_path / "explicit"
    assert resolve_data_dir() == tmp_path / "from_env"


def test_update_cache_writes_parquet_and_csv(cache_dir):
    for stem in ("sp500_current", "sp500_changelog", "sp500_historical_universe"):
        assert (cache_dir / f"{stem}.parquet").exists()
        assert (cache_dir / f"{stem}.csv").exists()


def test_cache_roundtrip_keeps_datetime_dtype(cache_dir):
    # CSV 存的是文本, 读回来必须还原成 datetime, 否则日期比较会退化成字符串比较
    assert pd.api.types.is_datetime64_any_dtype(load_changelog()["date"])

    (cache_dir / "sp500_changelog.parquet").unlink()  # 强制走 CSV 分支
    assert pd.api.types.is_datetime64_any_dtype(load_changelog()["date"])


def test_no_as_of_returns_current_list(cache_dir):
    assert get_historical_sp500_constituents() == ["AAA", "BBB", "DDD"]


def test_rewind_undoes_changes_after_as_of(cache_dir):
    # 2022-01-01: DDD/BBB 尚未纳入; CCC 当时还在(2022-06-01 才被剔除)
    assert get_historical_sp500_constituents("2022-01-01") == ["AAA", "CCC"]

    # 2021-01-01: 再往回一步, CCC 也还没进来, ZZZ 还在
    assert get_historical_sp500_constituents("2021-01-01") == ["AAA", "ZZZ"]


def test_as_of_day_changes_count_as_effective(cache_dir):
    # 当天发生的变动视为已生效: 2022-06-01 当天 BBB 已进、CCC 已出
    assert get_historical_sp500_constituents("2022-06-01") == ["AAA", "BBB"]


def test_date_and_datetime_give_same_result(cache_dir):
    expected = get_historical_sp500_constituents("2022-01-01")
    assert get_historical_sp500_constituents(datetime.date(2022, 1, 1)) == expected
    # 带时分秒的 datetime 会被 normalize 掉, 不该改变结果
    assert (
        get_historical_sp500_constituents(datetime.datetime(2022, 1, 1, 23, 59))
        == expected
    )


def test_dataframe_return_type_carries_metadata(cache_dir):
    frame = get_historical_sp500_constituents("2022-01-01", return_type="dataframe")

    assert frame["ticker"].tolist() == ["AAA", "CCC"]
    assert frame.loc[0, "name"] == "Alpha"
    # CCC 只出现在变动表里, 名称从 added_name 补上, 且标记为已不在指数中
    assert frame.loc[1, "name"] == "Gamma"
    assert bool(frame.loc[1, "currently_active"]) is False
    assert frame["as_of"].tolist() == [pd.Timestamp("2022-01-01")] * 2


def test_symbols_is_accepted_as_alias(cache_dir):
    assert get_historical_sp500_constituents(
        "2022-01-01", return_type="symbols"
    ) == get_historical_sp500_constituents("2022-01-01", return_type="tickers")


def test_invalid_return_type_raises(cache_dir):
    with pytest.raises(ValueError, match="return_type"):
        get_historical_sp500_constituents("2022-01-01", return_type="symbol")


def test_invalid_as_of_raises(cache_dir):
    with pytest.raises(ValueError, match="无法解析为日期"):
        get_historical_sp500_constituents("not a date")


def test_historical_universe_covers_delisted_tickers(cache_dir):
    # 退市/被剔除的 CCC、ZZZ 也在历史宇宙里, 这正是规避幸存者偏差要的
    assert get_all_historical_sp500_tickers() == ["AAA", "BBB", "CCC", "DDD", "ZZZ"]


def test_changelog_filter_is_inclusive_on_both_ends(cache_dir):
    frame = get_sp500_changelog("2021-05-10", "2022-06-01")

    assert frame["date"].tolist() == [
        pd.Timestamp("2022-06-01"),
        pd.Timestamp("2021-05-10"),
    ]


def test_changelog_filter_accepts_datetime_without_shifting_boundary(cache_dir):
    # 旧实现用字符串比较, datetime 会带上 " 00:00:00" 导致起止两端行为不一致
    start = datetime.datetime(2021, 5, 10, 12, 0)
    end = datetime.datetime(2022, 6, 1, 12, 0)

    assert len(get_sp500_changelog(start, end)) == 2


def test_missing_cache_raises_with_actionable_message(tmp_path, monkeypatch):
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path / "empty"))

    with pytest.raises(FileNotFoundError, match="update_cache_from_web"):
        get_historical_sp500_constituents()
