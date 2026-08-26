"""config.py 样本, 按照计划放在 src/sources/config.py"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT        = Path(__file__).resolve().parent.parent.parent
PACKAGE_ROOT        = Path(__file__).resolve().parent.parent
DATA_DIR            = PROJECT_ROOT / "data"
SP500_CACHE_PATH    = DATA_DIR / "sp500_ticker.csv"
SEC_CACHE_DIR       = DATA_DIR / "sec"
SEC_IDENTITY        = "liu 20070316lbw@gmail.com"

DATA_DIR.mkdir(parents=True, exist_ok=True)
SEC_CACHE_DIR.mkdir(parents=True, exist_ok=True)