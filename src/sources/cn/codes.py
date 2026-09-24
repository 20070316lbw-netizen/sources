"""A 股证券代码格式转换。

sources.cn 对外统一使用 `<6 位代码>.<交易所>` 的格式, 交易所大写:
`600519.SH`(上交所)、`000001.SZ`(深交所)、`430047.BJ`(北交所)。
BaoStock 内部用 `sh.600519` 这种格式, 只在访问层转换, 下游看不到。
"""
from __future__ import annotations

_EXCHANGES = ("SH", "SZ", "BJ")

# 只给了 6 位数字时按首位推断交易所。指数代码(如沪深300 000300.SH 与
# 深市的 000300.SZ)会被推断错, 查指数时请显式带后缀。
_PREFIX_EXCHANGE = {
    "6": "SH", "9": "SH", "5": "SH",
    "0": "SZ", "2": "SZ", "3": "SZ", "1": "SZ",
    "4": "BJ", "8": "BJ",
}


def normalize_ticker(ticker: str) -> str:
    """把各种写法的代码统一成 `600519.SH` 格式。

    接受 `600519.SH` / `600519.sh` / `sh.600519` / `SH600519` / `600519`(按首位推断)。

    Raises:
        ValueError: 无法识别的代码。
    """
    raw = ticker.strip().upper()

    if "." in raw:
        left, right = raw.split(".", 1)
        if left in _EXCHANGES and _is_code(right):
            return f"{right}.{left}"
        if right in _EXCHANGES and _is_code(left):
            return f"{left}.{right}"
    elif raw[:2] in _EXCHANGES and _is_code(raw[2:]):
        return f"{raw[2:]}.{raw[:2]}"
    elif _is_code(raw) and raw[0] in _PREFIX_EXCHANGE:
        return f"{raw}.{_PREFIX_EXCHANGE[raw[0]]}"

    raise ValueError(f"无法识别的 A 股代码: {ticker!r}, 示例: '600519.SH'")


def to_baostock_code(ticker: str) -> str:
    """`600519.SH` -> `sh.600519`(同样接受 normalize_ticker 支持的所有写法)。"""
    code, exchange = normalize_ticker(ticker).split(".")
    return f"{exchange.lower()}.{code}"


def from_baostock_code(code: str) -> str:
    """`sh.600519` -> `600519.SH`。"""
    return normalize_ticker(code)


def _is_code(s: str) -> bool:
    return len(s) == 6 and s.isdigit()
