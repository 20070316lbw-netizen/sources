"""对 SP500 DataFrame 的 ticker 列做读取, 返回全 SP500 列表"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from sources.universe.fetch import fetch_sp500_universe


def _load_sp500_dataframe(*, path: Path | str = "data/sp500_ticker.csv") -> pd.DataFrame:
    """检查 sp500 缓存 csv 文件是否存在, 存在则直接读取; 不存在则抓取后写入缓存再读取。

    Args:
        path: 缓存 CSV 的路径。默认 "data/sp500_ticker.csv" ——
            相对路径以调用方当前工作目录 (通常就是调用方项目根目录) 为起点。
    """
    path_obj = Path(path)
    if not path_obj.exists():
        logger.warning("缓存文件不存在, 正在重新抓取中")
        members = fetch_sp500_universe()
        df = pd.DataFrame([m.model_dump() for m in members])
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path_obj, index=False)
        logger.success(f"成功抓取并写入缓存文件: {path_obj}")
    else:
        logger.success("已存在缓存文件, 读取成功")

    return pd.read_csv(path_obj, dtype={"cik": str})


def load_sp500_list(*, path: Path | str = "data/sp500_ticker.csv") -> list[str]:
    """返回 S&P 500 全量 ticker 列表。

    Args:
        path: 缓存 CSV 的路径。默认 "data/sp500_ticker.csv" ——
            相对路径以调用方当前工作目录 (通常就是调用方项目根目录) 为起点。
    """
    df = _load_sp500_dataframe(path=path)
    return df["ticker"].tolist()


if __name__ == "__main__":
    target = load_sp500_list()
    print(target)
