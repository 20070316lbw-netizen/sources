"""从 SEC 年报中提取净利润和股东权益并计算 ROE。

ROE = 净利润 / 平均股东权益
平均股东权益 = (期初股东权益 + 期末股东权益) / 2
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from itertools import pairwise

import pandas as pd
from edgar import Company, set_identity
from edgar.xbrl import XBRLS
from loguru import logger

from sources.map.first_50 import tickers as first_50_tickers

_ROE_COLUMNS = [
    "ticker",
    "period_end",
    "net_income",
    "beginning_equity",
    "ending_equity",
    "average_equity",
    "roe",
    "roe_percent",
]
_IDENTITY_ENV = "EDGAR_IDENTITY"


def _ensure_identity() -> None:
    """设置 SEC 要求的访问者身份。"""

    identity = os.environ.get(_IDENTITY_ENV)
    if not identity:
        raise RuntimeError(
            f"未设置环境变量 {_IDENTITY_ENV}。请先设置，例如："
            f'export {_IDENTITY_ENV}="Your Name your@email.com"'
        )
    set_identity(identity)


def get_roe_statements(
    ticker: str,
    years: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """抓取计算 ROE 所需的利润表和资产负债表。"""

    if years < 1:
        raise ValueError("years 必须大于等于 1")

    _ensure_identity()
    company = Company(ticker)
    filings = (
        company.get_filings(form="10-K")
        .filter(amendments=False)
        .head(years)
    )
    if len(filings) == 0:
        raise ValueError(f"{ticker} 没有可用的 10-K 年报")

    xbrls = XBRLS.from_filings(filings)
    income = xbrls.statements.income_statement(max_periods=years).to_dataframe() # type: ignore
    balance = xbrls.statements.balance_sheet(max_periods=years).to_dataframe() # type: ignore
    return income, balance


def _period_columns(frame: pd.DataFrame) -> list[str]:
    """返回报表中的日期列，按新到旧排列。"""

    columns = [
        column
        for column in frame.columns
        if isinstance(column, str)
        and len(column) == 10
        and column[4] == "-"
        and column[7] == "-"
    ]
    return sorted(columns, reverse=True)


def _standard_values(
    frame: pd.DataFrame,
    concepts: tuple[str, ...],
    periods: list[str],
) -> pd.Series:
    """按优先顺序提取第一个可用的标准字段。"""

    values = pd.Series(index=periods, dtype="float64")
    for concept in concepts:
        rows = frame.loc[frame["standard_concept"].eq(concept), periods]
        if rows.empty:
            continue

        concept_values = rows.apply(pd.to_numeric, errors="coerce").bfill().iloc[0]
        values = values.fillna(concept_values)

    if values.notna().any():
        return values

    names = "、".join(concepts)
    raise ValueError(f"报表中找不到可用字段：{names}")


def calculate_roe(
    ticker: str,
    income: pd.DataFrame,
    balance: pd.DataFrame,
) -> pd.DataFrame:
    """根据已经标准化的利润表和资产负债表计算各年度 ROE。"""

    income_periods = _period_columns(income)
    balance_periods = _period_columns(balance)
    if len(balance_periods) < 2:
        raise ValueError("计算平均股东权益至少需要两个年度的资产负债表")

    net_income = _standard_values(
        income,
        ("NetIncomeToCommonShareholders", "NetIncome"),
        income_periods,
    )
    equity = _standard_values(
        balance,
        ("AllEquityBalance",),
        balance_periods,
    )

    rows: list[dict[str, object]] = []
    for current_period, previous_period in pairwise(balance_periods):
        if current_period not in net_income.index:
            continue

        current_income = net_income[current_period]
        ending_equity = equity[current_period]
        beginning_equity = equity[previous_period]
        if pd.isna(current_income) or pd.isna(ending_equity) or pd.isna(beginning_equity):
            continue

        average_equity = (beginning_equity + ending_equity) / 2
        roe = float("nan") if average_equity == 0 else current_income / average_equity
        rows.append(
            {
                "ticker": ticker.upper(),
                "period_end": pd.Timestamp(current_period),
                "net_income": float(current_income),
                "beginning_equity": float(beginning_equity),
                "ending_equity": float(ending_equity),
                "average_equity": float(average_equity),
                "roe": float(roe),
                "roe_percent": float(roe * 100),
            }
        )

    return pd.DataFrame(rows, columns=_ROE_COLUMNS)


def get_roe(ticker: str, years: int = 1) -> pd.DataFrame:
    """抓取数据并返回指定公司最近若干年度的 ROE。"""

    if years < 1:
        raise ValueError("years 必须大于等于 1")

    income, balance = get_roe_statements(ticker, years=years + 1)
    return calculate_roe(ticker, income, balance).head(years).reset_index(drop=True)


def get_roe_batch(
    tickers: Iterable[str] = first_50_tickers,
    years: int = 1,
) -> pd.DataFrame:
    """计算多只股票的 ROE；单只失败时记录警告并继续。"""

    _ensure_identity()
    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        try:
            result = get_roe(ticker, years=years)
        except Exception as error:  # noqa: BLE001 - 批量任务不能被单只股票中断
            logger.warning(f"{ticker}: ROE 计算失败，已跳过 ({error})")
            continue
        frames.append(result)

    if not frames:
        return pd.DataFrame(columns=_ROE_COLUMNS)
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    print(get_roe_batch())
