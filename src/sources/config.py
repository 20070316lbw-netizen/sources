from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT        = Path(__file__).resolve().parent.parent.parent
PACKAGE_ROOT        = Path(__file__).resolve().parent.parent
DATA_DIR            = PROJECT_ROOT / "data"
SP500_CACHE_PATH    = DATA_DIR / "sp500_ticker.csv"
SEC_CACHE_DIR       = DATA_DIR / "sec"

# 从项目根目录的 .env 读取本地身份信息 (.env 已 gitignore, 不会被提交)
load_dotenv(PROJECT_ROOT / ".env")

# SEC EDGAR 要求 User-Agent 里带真实姓名 + 邮箱; 参考 .env.example 复制一份 .env 自行填写,
# 这里的默认值只是占位符, 千万不要把真实身份信息硬编码提交到仓库里
SEC_IDENTITY        = os.environ.get("SEC_IDENTITY", "Your Name your.email@example.com")

DATA_DIR.mkdir(parents=True, exist_ok=True)
# 注意: SEC_CACHE_DIR 不在这里预建, 实际落盘时 save_fundamentals() 会按需创建,
# 避免仅仅 import config 就在磁盘上凭空建出一个空目录。
