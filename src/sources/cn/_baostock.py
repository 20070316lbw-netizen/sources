"""BaoStock 访问层: 登录会话、统一的查询执行与分页取数。

BaoStock 是模块级全局状态(login 之后同一进程里的所有查询共用一个 socket),
所以这里用引用计数的 `session()` 包一层: 最外层进入时登录、最外层退出时登出,
嵌套调用(比如 get_cn_prices 内部循环几百只股票)只登录一次。**不是线程安全的**,
不要在多个线程里并发调用 sources.cn 的函数。

另外两处刻意绕开 BaoStock 自带实现:
    - BaoStock 会往 stdout 打 "login success!" 之类的提示, 全部吞掉, 改走 loguru;
    - ResultData.get_data() 内部翻页用的是 pandas 2.0 已删除的 DataFrame.append,
      结果超过一页(2000 行)就会崩, 所以这里自己用 next()/get_row_data() 逐行取。

可选环境变量 BAOSTOCK_API_KEY: 设置后登录前调用 bs.set_API_key, 不设则匿名登录。
"""
from __future__ import annotations

import contextlib
import io
import os
from collections.abc import Iterator

import baostock as bs
import pandas as pd
from loguru import logger

API_KEY_ENV_VAR = "BAOSTOCK_API_KEY"
_SUCCESS = "0"

# 当前嵌套深度; 用 dict 装着是为了在函数里改它时不用 global 语句
_state = {"depth": 0}


class BaostockError(RuntimeError):
    """BaoStock 返回了非成功的 error_code。"""


@contextlib.contextmanager
def session() -> Iterator[None]:
    """登录 BaoStock 的上下文管理器, 支持嵌套(只在最外层登录/登出)。

    Raises:
        BaostockError: 登录失败。
    """
    if _state["depth"] == 0:
        with contextlib.redirect_stdout(io.StringIO()):
            api_key = os.environ.get(API_KEY_ENV_VAR)
            if api_key:
                bs.set_API_key(api_key)
            result = bs.login()
        if result.error_code != _SUCCESS:
            raise BaostockError(f"BaoStock 登录失败: [{result.error_code}] {result.error_msg}")
        logger.debug("BaoStock 登录成功")

    _state["depth"] += 1
    try:
        yield
    finally:
        _state["depth"] -= 1
        if _state["depth"] == 0:
            with contextlib.redirect_stdout(io.StringIO()):
                bs.logout()
            logger.debug("BaoStock 已登出")


def query(method: str, *args: object, **kwargs: object) -> pd.DataFrame:
    """调用 `bs.<method>(*args, **kwargs)` 并把全部结果(含翻页)取成 DataFrame。

    必须在 `session()` 里调用。返回的所有值都是 BaoStock 原样的字符串,
    类型转换由调用方负责。

    Raises:
        BaostockError: 查询失败(包括翻页中途失败)。
    """
    fn = getattr(bs, method)
    rows: list[list[str]] = []
    with contextlib.redirect_stdout(io.StringIO()):
        result = fn(*args, **kwargs)
        _raise_for_error(method, result)
        while result.next():
            rows.append(result.get_row_data())
        # next() 内部翻页请求失败时只会改 error_code 然后返回 False, 需要再查一次
        _raise_for_error(method, result)
    return pd.DataFrame(rows, columns=list(result.fields))


def _raise_for_error(method: str, result: object) -> None:
    code = getattr(result, "error_code", None)
    if code != _SUCCESS:
        msg = getattr(result, "error_msg", "")
        raise BaostockError(f"{method} 失败: [{code}] {msg}")
