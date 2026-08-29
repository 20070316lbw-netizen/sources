from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger


def load_prices(*, path: Path | str = "data/sp500.parquet") -> pd.DataFrame:
    """从本地读取价格数据, MultiIndex 和 dtype 都会自动还原

    Args:
        path: Parquet 文件路径。默认 "data/sp500.parquet" ——
            相对路径以调用方当前工作目录 (通常就是调用方项目根目录) 为起点。
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(
            f"{path_obj} 不存在, 先运行 `uv run python src/.../fetch.py` 抓取数据"
        )
    logger.success(f"成功在 {path} 读取到数据")
    return pd.read_parquet(path_obj)
