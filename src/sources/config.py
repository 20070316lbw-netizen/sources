from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT        = Path(__file__).resolve().parent.parent.parent
PACKAGE_ROOT        = Path(__file__).resolve().parent.parent
DATA_DIR            = PROJECT_ROOT / "data"
SP500_CACHE_PATH    = DATA_DIR / "sp500_ticker.csv"
SEC_CACHE_DIR       = DATA_DIR / "sec"
# SEC EDGAR 要求 User-Agent 里带真实姓名 + 邮箱, 可通过环境变量覆盖, 避免把身份信息写死在多处
SEC_IDENTITY        = os.environ.get("SEC_IDENTITY", "liu 20070316lbw@gmail.com")

DATA_DIR.mkdir(parents=True, exist_ok=True)
# 注意: SEC_CACHE_DIR 不在这里预建, 实际落盘时 save_fundamentals() 会按需创建,
# 避免仅仅 import config 就在磁盘上凭空建出一个空目录。
