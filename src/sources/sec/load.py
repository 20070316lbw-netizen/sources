"""SEC EDGAR 基本面数据加载模块"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


def load_fundamentals(*, path: Path | str) -> pd.DataFrame:
    """从本地 Parquet 文件加载基本面数据，自动还原 MultiIndex 与数据类型。

    Args:
        path: Parquet 文件路径 (支持 Path 或 str)

    Returns:
        pd.DataFrame: 加载并还原后的基本面数据表。
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(
            f"{path_obj} 不存在, 请先运行抓取函数生成基本面数据"
        )
    return pd.read_parquet(path_obj)
