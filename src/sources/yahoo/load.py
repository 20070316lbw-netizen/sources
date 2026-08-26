from __future__ import annotations

from pathlib import Path
import pandas as pd


def load_prices(*, path: Path | str) -> pd.DataFrame:
    """从本地读取价格数据, MultiIndex 和 dtype 都会自动还原"""
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(
            f"{path_obj} 不存在, 先运行 `uv run python src/.../fetch.py` 抓取数据"
        )
    return pd.read_parquet(path_obj)