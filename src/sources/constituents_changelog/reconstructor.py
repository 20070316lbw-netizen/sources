"""
标普500历史成分股点时反推引擎
"""
import datetime
from pathlib import Path
from typing import List, Optional, Set, Union
import pandas as pd

from src.sources.constituents_changelog import fetch_wikipedia_tables

# 本地离线缓存数据存放目录
DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_data_file(filename_stem: str) -> pd.DataFrame:
    """优先从 Parquet 文件加载数据，如不存在则回退至 CSV 文件。"""
    parquet_path = DATA_DIR / f"{filename_stem}.parquet"
    csv_path = DATA_DIR / f"{filename_stem}.csv"
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except Exception:
            pass
    if csv_path.exists():
        return pd.read_csv(csv_path)
    raise FileNotFoundError(f"未找到数据文件: {parquet_path} 或 {csv_path}")


def load_current_constituents() -> pd.DataFrame:
    """从本地缓存加载当前标普500成分股名单。"""
    return _load_data_file("sp500_current")


def load_changelog() -> pd.DataFrame:
    """从本地缓存加载标普500历次增删变动日志。"""
    return _load_data_file("sp500_changelog")


def load_historical_universe() -> pd.DataFrame:
    """从本地缓存加载1990年至今全部进入过标普500的股票元数据。"""
    return _load_data_file("sp500_historical_universe")


def update_cache_from_web(data_dir: Optional[Union[str, Path]] = None) -> None:
    """
    从维基百科抓取最新成分股及变动日志表格, 并更新本地持久化缓存 Parquet与CSV格式

    参数:
        data_dir: 缓存写入路径, 若为None则写入模块自带的 data/ 目录。
    """
    target_dir = Path(data_dir) if data_dir else DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    df_current, df_changes = fetch_wikipedia_tables()

    # 1. 保存当前成分股名单
    df_current.to_parquet(target_dir / "sp500_current.parquet", index=False)
    df_current.to_csv(target_dir / "sp500_current.csv", index=False)

    # 2. 保存历史增删变动日志
    df_changes.to_parquet(target_dir / "sp500_changelog.parquet", index=False)
    df_changes.to_csv(target_dir / "sp500_changelog.csv", index=False)

    # 3. 统计并生成全量历史宇宙（所有曾入选过标普500的标的）
    symbol_metadata = {}
    for _, r in df_current.iterrows():
        sym = r["symbol"]
        symbol_metadata[sym] = {
            "symbol": sym,
            "name": r.get("name", ""),
            "sector": r.get("sector", ""),
            "sub_industry": r.get("sub_industry", ""),
            "currently_active": True,
            "last_added_date": r.get("date_added", ""),
            "last_removed_date": ""
        }

    for _, r in df_changes.iterrows():
        if r["added_symbol"]:
            s = r["added_symbol"]
            if s not in symbol_metadata:
                symbol_metadata[s] = {
                    "symbol": s,
                    "name": r["added_name"],
                    "sector": "",
                    "sub_industry": "",
                    "currently_active": False,
                    "last_added_date": r["date"],
                    "last_removed_date": ""
                }
            else:
                if not symbol_metadata[s]["name"] and r["added_name"]:
                    symbol_metadata[s]["name"] = r["added_name"]
                if not symbol_metadata[s]["last_added_date"]:
                    symbol_metadata[s]["last_added_date"] = r["date"]

        if r["removed_symbol"]:
            s = r["removed_symbol"]
            if s not in symbol_metadata:
                symbol_metadata[s] = {
                    "symbol": s,
                    "name": r["removed_name"],
                    "sector": "",
                    "sub_industry": "",
                    "currently_active": False,
                    "last_added_date": "",
                    "last_removed_date": r["date"]
                }
            else:
                if not symbol_metadata[s]["name"] and r["removed_name"]:
                    symbol_metadata[s]["name"] = r["removed_name"]
                if not symbol_metadata[s]["last_removed_date"]:
                    symbol_metadata[s]["last_removed_date"] = r["date"]

    df_universe = pd.DataFrame(list(symbol_metadata.values())).sort_values("symbol").reset_index(drop=True)
    df_universe.to_parquet(target_dir / "sp500_historical_universe.parquet", index=False)
    df_universe.to_csv(target_dir / "sp500_historical_universe.csv", index=False)


def get_historical_sp500_constituents(
    as_of: Optional[Union[str, datetime.date, datetime.datetime]] = None,
    return_type: str = "symbols"
) -> Union[List[str], pd.DataFrame]:
    """
    根据指定历史时间点反推标普500成分股名单:
        1. 以当前最新成分股名单 S(T_now) 为基准。
        2. 按时间倒序逆向回溯变动日志中所有发生在 as_of 之后的增删记录：
           - 若标的在 as_of 之后才被加入 Added : 说明在 as_of 时点尚未入选 -> 从集合中剔除。
           - 若标的在 as_of 之后被移除 Removed : 说明在 as_of 时点仍在指数中 -> 还原补回集合。

    参数:
        as_of: 目标历史时点（例如 2020-01-01、datetime.date 对象，或传 None 表示当前最新）。
        return_type: 返回数据格式:
            - symbols: 返回排序后的股票代码列表 (List[str])
            - dataframe: 返回包含代码、名称、板块、时点信息的 DataFrame。

    返回:
        按字母顺序排序的代码列表或 DataFrame。
    """
    df_current = load_current_constituents()

    # 若未指定历史时点，直接返回最新成分股
    if as_of is None:
        symbols = sorted(df_current["symbol"].unique().tolist())
        if return_type == "symbols":
            return symbols
        return df_current[df_current["symbol"].isin(symbols)].sort_values("symbol").reset_index(drop=True)

    # 规范化目标日期为 YYYY-MM-DD
    if isinstance(as_of, (datetime.date, datetime.datetime)):
        target_date_str = as_of.strftime("%Y-%m-%d")
    else:
        target_date_str = pd.to_datetime(str(as_of)).strftime("%Y-%m-%d")

    df_changes = load_changelog()
    if "date" in df_changes.columns:
        df_changes = df_changes.sort_values("date", ascending=False).reset_index(drop=True)

    symbols_set: Set[str] = set(df_current["symbol"].unique())

    # 倒序逆推发生在 target_date_str 之后的所有变动
    for _, row in df_changes.iterrows():
        change_date = str(row["date"])
        if change_date > target_date_str:
            add_sym = str(row.get("added_symbol", "")).strip()
            rem_sym = str(row.get("removed_symbol", "")).strip()
            # 目标时点之后才加入的，在目标时点尚未进入 -> 剔除
            if add_sym and add_sym in symbols_set:
                symbols_set.remove(add_sym)
            # 目标时点之后被移出的，在目标时点仍在指数中 -> 补回
            if rem_sym:
                symbols_set.add(rem_sym)

    sorted_symbols = sorted(symbols_set)

    if return_type == "symbols":
        return sorted_symbols

    # 组装返回 DataFrame
    df_universe = load_historical_universe()
    matched = df_universe[df_universe["symbol"].isin(symbols_set)].copy()
    missing = set(symbols_set) - set(matched["symbol"])
    if missing:
        missing_df = pd.DataFrame([{"symbol": s, "name": "", "sector": "", "sub_industry": ""} for s in missing])
        matched = pd.concat([matched, missing_df], ignore_index=True)

    matched["as_of"] = target_date_str
    return matched.sort_values("symbol").reset_index(drop=True)


def get_all_historical_sp500_symbols() -> List[str]:
    """
    获取全部历史成员股票代码列表 (1990年至今曾进入过标普500的所有标的)
    """
    df_universe = load_historical_universe()
    return sorted(df_universe["symbol"].unique().tolist())


def get_sp500_changelog(
    start_date: Optional[Union[str, datetime.date]] = None,
    end_date: Optional[Union[str, datetime.date]] = None
) -> pd.DataFrame:
    """
    获取标普500成分股历史变动日志表格, 支持按起止日期过滤。

    参数:
        start_date: 起始日期 (如 2020-01-01), 可选
        end_date: 截止日期 (如 2023-12-31), 可选
    返回:
        变动明细 DataFrame。
    """
    df_changes = load_changelog()
    if start_date:
        s_date = str(start_date)
        df_changes = df_changes[df_changes["date"] >= s_date]
    if end_date:
        e_date = str(end_date)
        df_changes = df_changes[df_changes["date"] <= e_date]
    return df_changes.reset_index(drop=True)
