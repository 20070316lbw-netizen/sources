"""定义所有错误的基类"""

from __future__ import annotations


# ---------------------------------------------------------- 
# 总错误类
class QuantLabError(Exception):
    """项目所有自定义异常的根。捕获它 = 捕获本项目抛出的一切异常。"""
# ---------------------------------------------------------- 
# 总错误类下的分支
class DataFetchError(QuantLabError):
    """项目内所有数据抓取自定义异常的根"""

class PgsqlError(QuantLabError):
    """所有 PostgerSQL 自定义异常的根"""

# ---------------------------------------------------------- 
# 数据抓取相关
class EdgarFetchError(DataFetchError):
    """EDGAR 数据抓取相关的错误。"""

    def __init__(self, message_or_cik: str = "", status_code: int | None = None) -> None:
        if status_code is not None:
            self.cik = message_or_cik
            self.status_code = status_code
            super().__init__(f"CIK {message_or_cik} 抓取失败, 状态码 {status_code}")
        else:
            self.cik = ""
            self.status_code = None
            super().__init__(message_or_cik)


class YahooFetchError(DataFetchError):
    """Yahoo 数据抓取相关的错误"""


class WikiFetchError(DataFetchError):
    """Wiki 数据抓取相关错误。"""
# ---------------------------------------------------------- 
# 数据库与存储相关
class SchemaInitializationError(PgsqlError):
    """数据库 schema 初始化失败。"""


class UniverseLoadError(PgsqlError):
    """Universe 快照写入失败或输入不满足写入约束。"""


class YahooLoadError(PgsqlError):
    """Yahoo 数据入库时失败"""


class EdgarLoadError(PgsqlError):
    """EDGAR 数据入库或读取时失败"""

# ---------------------------------------------------------- 
# 杂项



        


