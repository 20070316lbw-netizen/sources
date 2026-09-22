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
from tqdm import tqdm

from sources.map.field_mapping_50 import get_equity_concepts, get_net_income_concepts
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
    """按优先顺序提取会计科目对应的数值。

    优先返回**单个** concept 就能覆盖全部期间的那一列: 不同 concept 对应不同
    会计口径(如母公司口径的 AllEquityBalance vs 含少数股东权益的合并口径
    AllEquityBalanceIncludingMinorityInterest), 跨 concept 拼出来的序列会让
    相邻年度的 ROE 分母不可比 —— 期初权益取 A 口径、期末取 B 口径, 算出来的
    数字没有意义。

    只有在没有任何单一 concept 能覆盖全部期间时, 才退回按优先级逐列填补, 并
    明确告警, 让调用方知道这一列是拼出来的。
    """

    matches: list[tuple[str, pd.Series]] = []

    for concept in concepts:
        candidate = _concept_values(frame, concept, periods)
        if candidate is None:
            continue
        if candidate.notna().all():
            return candidate
        matches.append((concept, candidate))

    values = pd.Series(index=periods, dtype="float64")
    for _, candidate in matches:
        values = values.fillna(candidate)

    if values.isna().all():
        names = "、".join(concepts)
        raise ValueError(f"报表中找不到可用字段：{names}")

    if len(matches) > 1:
        merged = "、".join(name for name, _ in matches)
        logger.warning(
            f"没有单一会计科目覆盖全部期间, 已按优先级拼接 {merged}; "
            "跨口径混算可能让不同年度的 ROE 不可比"
        )
    return values


def _concept_values(
    frame: pd.DataFrame,
    concept: str,
    periods: list[str],
) -> pd.Series | None:
    """取单个 concept 在各期间的数值; 该 concept 在报表里不存在时返回 None。"""

    rows = pd.DataFrame()
    if "standard_concept" in frame.columns:
        rows = frame.loc[frame["standard_concept"].eq(concept), periods]

    # standard_concept 未命中时, 回退匹配原始 XBRL 标签(如 us-gaap_StockholdersEquity)
    if rows.empty and "concept" in frame.columns:
        raw = frame["concept"].astype("string").fillna("")
        rows = frame.loc[raw.eq(concept) | raw.str.endswith(f"_{concept}"), periods]

    if rows.empty:
        return None

    # 多行命中时按行向下补齐, 取合并后的第一行
    return rows.apply(pd.to_numeric, errors="coerce").bfill().iloc[0]


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

    net_income_concepts = get_net_income_concepts(ticker)
    equity_concepts = get_equity_concepts(ticker)

    net_income = _standard_values(
        income,
        net_income_concepts,
        income_periods,
    )
    equity = _standard_values(
        balance,
        equity_concepts,
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
    show_progress: bool = True,
) -> pd.DataFrame:
    """计算多只股票的 ROE；单只失败时记录警告并继续。

    Args:
        tickers: 股票代码列表，默认为前 50 只标的。
        years: 计算 ROE 的年数，默认为 1 年。
        show_progress: 是否显示进度条，默认为 True。
    """

    _ensure_identity()
    ticker_list = list(tickers)
    iterator = (
        tqdm(ticker_list, desc="计算 ROE", unit="只")
        if show_progress
        else ticker_list
    )

    frames: list[pd.DataFrame] = []
    for ticker in iterator:
        if show_progress and isinstance(iterator, tqdm):
            iterator.set_postfix_str(ticker)
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
