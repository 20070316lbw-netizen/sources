"""对 50 个重点目标标的及通用的基本面字段进行映射。

解决抓取基本面及计算 ROE 时各公司会计科目与 XBRL 标签不一致的问题：
1. 提供默认的股东权益与净利润候选字段优先级列表；
2. 支持针对特定股票的自定义字段映射覆盖；
3. 保留列名标准化映射接口。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# 股东权益默认候选字段（优先标准概念，支持合并报表与母公司口径）
DEFAULT_EQUITY_CONCEPTS: tuple[str, ...] = (
    "AllEquityBalance",
    "AllEquityBalanceIncludingMinorityInterest",
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "CommonEquity",
)

# 净利润默认候选字段
DEFAULT_NET_INCOME_CONCEPTS: tuple[str, ...] = (
    "NetIncomeToCommonShareholders",
    "NetIncome",
    "NetIncomeLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
    "ProfitLoss",
)

# 针对特定股票的自定义概念映射覆盖表
# 结构示例:
# {
#     "PG": {
#         "equity": ("AllEquityBalanceIncludingMinorityInterest", "AllEquityBalance"),
#     },
# }
TICKER_CONCEPT_MAPPING: dict[str, dict[str, tuple[str, ...]]] = {}

# 列名映射字典（保留兼容性）
FIELD_MAPPING: dict[str, str] = {}


def get_equity_concepts(ticker: str | None = None) -> tuple[str, ...]:
    """返回指定股票计算 ROE 使用的股东权益候选字段列表。"""
    if ticker:
        ticker_upper = ticker.upper()
        if ticker_upper in TICKER_CONCEPT_MAPPING:
            custom = TICKER_CONCEPT_MAPPING[ticker_upper].get("equity")
            if custom:
                return tuple(custom)
    return DEFAULT_EQUITY_CONCEPTS


def get_net_income_concepts(ticker: str | None = None) -> tuple[str, ...]:
    """返回指定股票计算 ROE 使用的净利润候选字段列表。"""
    if ticker:
        ticker_upper = ticker.upper()
        if ticker_upper in TICKER_CONCEPT_MAPPING:
            custom = TICKER_CONCEPT_MAPPING[ticker_upper].get("net_income")
            if custom:
                return tuple(custom)
    return DEFAULT_NET_INCOME_CONCEPTS


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将 df 的列名按 FIELD_MAPPING 统一。"""
    return df.rename(columns=FIELD_MAPPING)