"""标普500历史成分股点时(Point-in-Time)反推引擎。

思路: 以「当前成分股名单」为基准, 按时间**倒序**把发生在目标时点之后的增删
记录逐条撤销, 还原出该时点的名单。

    - 目标时点之后才被纳入的 -> 当时还不在指数里 -> 剔除
    - 目标时点之后被剔除的   -> 当时还在指数里   -> 补回

数据来自 Wikipedia 那张 "Selected changes to the list of S&P 500 components"
表 —— 注意它是**选择性**记录、并不完整, 越往前缺得越多。所以本模块反推出的
名单近几年可信度较高, 时间越久远偏差越大; 要做严肃的历史回测, 该换 CRSP 之
类的正式成分股历史库。

缓存: 抓下来的三张表落到本地 data/ 目录(Parquet + CSV 各存一份)。目录由
resolve_data_dir() 统一决定, **读写共用同一套规则**, 默认是包内的 data/, 可
用环境变量 SOURCES_DATA_DIR 覆盖(包被装到只读目录时尤其需要)。
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path

import pandas as pd
from loguru import logger

from sources._wikipedia import fetch_sp500_tables

DataDirLike = str | os.PathLike[str]
DateLike = str | datetime.date | datetime.datetime

#: 覆盖缓存目录的环境变量名
DATA_DIR_ENV = "SOURCES_DATA_DIR"

#: 历史宇宙表(所有曾出现过的标的)的输出 schema
UNIVERSE_COLUMNS = [
    "ticker",
    "name",
    "sector",
    "sub_industry",
    "currently_active",
    "first_added_date",
    "last_added_date",
    "last_removed_date",
]

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"

_CURRENT_STEM = "sp500_current"
_CHANGELOG_STEM = "sp500_changelog"
_UNIVERSE_STEM = "sp500_historical_universe"

# 落盘后需要还原成时间类型的列。Parquet 自带类型, CSV 存的是文本, 统一在
# 读取时再解析一遍, 保证两条路径拿到的 dtype 一致。
_DATE_COLUMNS = frozenset(
    {"date", "date_added", "first_added_date", "last_added_date", "last_removed_date"}
)

# "symbols" 是旧名字, 留作别名, 语义同 "tickers"
_RETURN_TYPES = frozenset({"tickers", "symbols", "dataframe"})


def resolve_data_dir(data_dir: DataDirLike | None = None) -> Path:
    """决定缓存目录, 优先级: 显式入参 > 环境变量 > 包内 data/。

    读和写都走这一个函数, 避免出现「写到 A、读的却是 B」。
    """
    if data_dir is not None:
        return Path(data_dir).expanduser()
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return _DEFAULT_DATA_DIR


def load_current_constituents(data_dir: DataDirLike | None = None) -> pd.DataFrame:
    """从本地缓存加载当前标普500成分股名单。"""
    return _load_data_file(_CURRENT_STEM, data_dir)


def load_changelog(data_dir: DataDirLike | None = None) -> pd.DataFrame:
    """从本地缓存加载标普500历次增删变动日志。"""
    return _load_data_file(_CHANGELOG_STEM, data_dir)


def load_historical_universe(data_dir: DataDirLike | None = None) -> pd.DataFrame:
    """从本地缓存加载全部曾进入过标普500的标的及其元数据。"""
    return _load_data_file(_UNIVERSE_STEM, data_dir)


def update_cache_from_web(data_dir: DataDirLike | None = None) -> Path:
    """从 Wikipedia 抓取最新表格并刷新本地缓存(Parquet + CSV)。

    Args:
        data_dir: 缓存写入目录; 默认走 resolve_data_dir() 的解析结果。

    Returns:
        实际写入的目录, 方便调用方确认落到了哪儿。
    """
    target_dir = resolve_data_dir(data_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    df_current, df_changes = fetch_sp500_tables()
    df_universe = _build_universe(df_current, df_changes)

    for stem, frame in (
        (_CURRENT_STEM, df_current),
        (_CHANGELOG_STEM, df_changes),
        (_UNIVERSE_STEM, df_universe),
    ):
        frame.to_parquet(target_dir / f"{stem}.parquet", index=False)
        frame.to_csv(target_dir / f"{stem}.csv", index=False)

    logger.info(
        f"缓存已更新至 {target_dir}: "
        f"{len(df_current)} 只当前成分股 / {len(df_changes)} 条变动 / "
        f"{len(df_universe)} 只历史标的"
    )
    return target_dir


def get_historical_sp500_constituents(
    as_of: DateLike | None = None,
    return_type: str = "tickers",
    data_dir: DataDirLike | None = None,
) -> list[str] | pd.DataFrame:
    """反推指定历史时点的标普500成分股名单。

    Args:
        as_of: 目标时点, 如 "2020-01-01" / datetime.date; 传 None 表示直接
            返回当前最新名单。当天发生的变动视为**已生效**(即 as_of 收盘后
            的名单)。
        return_type: "tickers"(默认, 返回排序后的代码列表)、"symbols"(旧
            名字, 等价于 "tickers")或 "dataframe"(带名称、板块等元数据)。
        data_dir: 缓存目录, 默认走 resolve_data_dir()。

    Returns:
        按字母序排列的代码列表, 或带元数据的 DataFrame。

    Raises:
        ValueError: return_type 取值非法, 或 as_of 解析不出日期。
        FileNotFoundError: 本地缓存不存在, 需要先跑 update_cache_from_web()。
    """
    if return_type not in _RETURN_TYPES:
        raise ValueError(
            f"return_type 只能是 {sorted(_RETURN_TYPES)} 之一, 收到: {return_type!r}"
        )

    tickers = set(load_current_constituents(data_dir)["ticker"])
    target = _to_timestamp(as_of) if as_of is not None else None

    if target is not None:
        tickers = _rewind(tickers, load_changelog(data_dir), target)

    sorted_tickers = sorted(tickers)
    if return_type != "dataframe":
        return sorted_tickers
    return _describe(sorted_tickers, target, data_dir)


def get_all_historical_sp500_tickers(data_dir: DataDirLike | None = None) -> list[str]:
    """返回缓存里全部曾进入过标普500的股票代码(含已退市/已剔除的)。"""
    return sorted(load_historical_universe(data_dir)["ticker"].unique().tolist())


def get_sp500_changelog(
    start_date: DateLike | None = None,
    end_date: DateLike | None = None,
    data_dir: DataDirLike | None = None,
) -> pd.DataFrame:
    """返回标普500增删变动日志, 可按起止日期过滤(两端均为闭区间)。

    Args:
        start_date: 起始日期(含), 如 "2020-01-01"; None 表示不设下界。
        end_date: 截止日期(含), 如 "2023-12-31"; None 表示不设上界。
        data_dir: 缓存目录, 默认走 resolve_data_dir()。

    Returns:
        变动明细 DataFrame, 按 date 降序。
    """
    df_changes = load_changelog(data_dir)
    if start_date is not None:
        df_changes = df_changes[df_changes["date"] >= _to_timestamp(start_date)]
    if end_date is not None:
        df_changes = df_changes[df_changes["date"] <= _to_timestamp(end_date)]
    return (
        df_changes.sort_values("date", ascending=False, kind="stable")
        .reset_index(drop=True)
    )


def _load_data_file(stem: str, data_dir: DataDirLike | None) -> pd.DataFrame:
    """优先读 Parquet, 不可用时回退 CSV。"""
    directory = resolve_data_dir(data_dir)
    parquet_path = directory / f"{stem}.parquet"
    csv_path = directory / f"{stem}.csv"

    if parquet_path.exists():
        try:
            return _restore_dates(pd.read_parquet(parquet_path))
        except Exception as error:  # noqa: BLE001 - 文件损坏/缺引擎时退回 CSV
            logger.warning(f"读取 {parquet_path} 失败, 回退 CSV ({error})")

    if csv_path.exists():
        return _restore_dates(pd.read_csv(csv_path))

    raise FileNotFoundError(
        f"未找到缓存文件 {parquet_path} 或 {csv_path}; "
        f"请先执行 update_cache_from_web() 生成, "
        f"或用环境变量 {DATA_DIR_ENV} 指向已有的缓存目录"
    )


def _restore_dates(frame: pd.DataFrame) -> pd.DataFrame:
    """把日期列统一还原成 datetime64, 让比较走真正的时间语义而不是字符串。"""
    for column in _DATE_COLUMNS & set(frame.columns):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


def _to_timestamp(value: DateLike) -> pd.Timestamp:
    """把各种日期写法归一成当天零点的 Timestamp。

    normalize() 很关键: datetime.datetime 是 datetime.date 的子类, 不抹掉时
    分秒的话, 同一天的边界比较会出现「start_date 少一天、end_date 多一天」
    的不一致。
    """
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        raise ValueError(f"无法解析为日期: {value!r}")
    return pd.Timestamp(timestamp).normalize()


def _rewind(
    tickers: set[str],
    df_changes: pd.DataFrame,
    target: pd.Timestamp,
) -> set[str]:
    """把发生在 target 之后的增删逐条撤销, 得到 target 时点的名单。

    必须按时间倒序处理: 同一标的多次进出指数时(如 T1 纳入、T2 剔除、T3 再纳
    入), 只有从最近往回撤销才能还原出正确状态。

    剔除用 discard 而非 remove: 变动表本身不完整, 出现「记录说纳入、但当前
    名单里没有」是常态, 不该为此抛异常。
    """
    result = set(tickers)
    recent = df_changes[df_changes["date"] > target].sort_values(
        "date", ascending=False, kind="stable"
    )
    for row in recent.itertuples(index=False):
        if row.added_ticker:
            result.discard(row.added_ticker)
        if row.removed_ticker:
            result.add(row.removed_ticker)
    return result


def _build_universe(df_current: pd.DataFrame, df_changes: pd.DataFrame) -> pd.DataFrame:
    """汇总出「曾出现过的全部标的」及其元数据。"""
    records: dict[str, dict[str, object]] = {}

    def record_for(ticker: str) -> dict[str, object]:
        return records.setdefault(
            ticker,
            {
                "ticker": ticker,
                "name": "",
                "sector": "",
                "sub_industry": "",
                "currently_active": False,
                "first_added_date": pd.NaT,
                "last_added_date": pd.NaT,
                "last_removed_date": pd.NaT,
            },
        )

    for row in df_current.itertuples(index=False):
        record = record_for(row.ticker)
        # 当前名单的元数据最全, 优先采用
        record["name"] = row.name or record["name"]
        record["sector"] = row.sector or record["sector"]
        record["sub_industry"] = row.sub_industry or record["sub_industry"]
        record["currently_active"] = True
        record["first_added_date"] = _earlier(record["first_added_date"], row.date_added)
        record["last_added_date"] = _later(record["last_added_date"], row.date_added)

    for row in df_changes.itertuples(index=False):
        if row.added_ticker:
            record = record_for(row.added_ticker)
            record["name"] = record["name"] or row.added_name
            record["first_added_date"] = _earlier(record["first_added_date"], row.date)
            record["last_added_date"] = _later(record["last_added_date"], row.date)
        if row.removed_ticker:
            record = record_for(row.removed_ticker)
            record["name"] = record["name"] or row.removed_name
            record["last_removed_date"] = _later(record["last_removed_date"], row.date)

    frame = pd.DataFrame(list(records.values()), columns=UNIVERSE_COLUMNS)
    # 显式定死 dtype: 记录全为空时 pandas 会把日期列推断成 object
    for column in ("first_added_date", "last_added_date", "last_removed_date"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    frame["currently_active"] = frame["currently_active"].astype(bool)
    return frame.sort_values("ticker").reset_index(drop=True)


def _later(current: object, candidate: object) -> pd.Timestamp:
    """取两个日期里较晚的那个, NaT 视为「没有值」。"""
    parsed = pd.to_datetime(candidate, errors="coerce")
    if pd.isna(parsed):
        return current  # type: ignore[return-value]
    if pd.isna(current):
        return parsed
    return max(current, parsed)  # type: ignore[type-var]


def _earlier(current: object, candidate: object) -> pd.Timestamp:
    """取两个日期里较早的那个, NaT 视为「没有值」。"""
    parsed = pd.to_datetime(candidate, errors="coerce")
    if pd.isna(parsed):
        return current  # type: ignore[return-value]
    if pd.isna(current):
        return parsed
    return min(current, parsed)  # type: ignore[type-var]


def _describe(
    tickers: list[str],
    as_of: pd.Timestamp | None,
    data_dir: DataDirLike | None,
) -> pd.DataFrame:
    """给一批代码补上名称/板块等元数据, 组装成返回用的 DataFrame。"""
    df_universe = load_historical_universe(data_dir)
    matched = df_universe[df_universe["ticker"].isin(tickers)].copy()

    missing = sorted(set(tickers) - set(matched["ticker"]))
    if missing:
        preview = ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else "")
        logger.warning(f"{len(missing)} 只标的在历史宇宙表中查不到元数据: {preview}")
        matched = pd.concat(
            [matched, pd.DataFrame({"ticker": missing})], ignore_index=True
        )

    matched = matched.reindex(columns=[*UNIVERSE_COLUMNS, "as_of"])
    matched["as_of"] = as_of
    return matched.sort_values("ticker").reset_index(drop=True)


if __name__ == "__main__":
    update_cache_from_web()
    print(get_historical_sp500_constituents("2020-01-01", return_type="dataframe"))
