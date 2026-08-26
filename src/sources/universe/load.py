"""对 SP500 DataFrame 的 ticker 列做读取, 返回全 SP500 列表"""

from __future__ import annotations

import pandas as pd
from loguru import logger

from sources.config import SP500_CACHE_PATH
from sources.universe.fetch import fetch_sp500_universe


def _load_sp500_dataframe() -> pd.DataFrame:
    """检查 sp500 缓存 csv 文件是否存在, 存在则直接读取; 不存在则抓取后写入缓存再读取。"""
    if not SP500_CACHE_PATH.exists():
        logger.warning("缓存文件不存在, 正在重新抓取中")
        members = fetch_sp500_universe()
        df = pd.DataFrame([m.model_dump() for m in members])
        df.to_csv(SP500_CACHE_PATH, index=False)
        logger.success(f"成功抓取并写入缓存文件: {SP500_CACHE_PATH}")
    else:
        logger.success("已存在缓存文件, 读取成功")

    return pd.read_csv(SP500_CACHE_PATH, dtype={"cik": str})


def load_sp500_list() -> list[str]:
    """返回 S&P 500 全量 ticker 列表。"""
    df = _load_sp500_dataframe()
    return df["ticker"].tolist()


if __name__ == "__main__":
    target = load_sp500_list()
    print(target)
