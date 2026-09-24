"""基于 SEC 年报(10-K)计算 ROE。

ROE = 净利润 / 平均股东权益
平均股东权益 = (期初股东权益 + 期末股东权益) / 2

数据来自 `sources.sec`(SEC companyfacts 接口, 一家公司一次请求)。每个财年的
净利润、期末权益、期初权益都取自**同一份 10-K**: 10-K 的资产负债表同时列出本年末
和上年末两个时点, 用同一份文件的数字能保证分子分母口径一致、且是当时首次公布的
版本(若该财年后来被重述, 以最近一次作为"本年"申报的 10-K 为准)。

净利润、股东权益用哪个 XBRL 科目见 `sources.sec.fields.FIELDS` 的 net_income /
total_equity; 个股可在 `TICKER_FIELD_OVERRIDES` 里覆盖。
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
from loguru import logger
from tqdm import tqdm

from sources.map.first_50 import tickers as first_50_tickers
from sources.sec.fundamentals import get_fundamentals

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
_ANNUAL_FORMS = ("10-K", "10-K/A", "10-KT", "10-KT/A")
# 期初时点应比期末早约一年(52/53 周财年会差几天)
_PRIOR_YEAR_DAYS = (330, 400)


def calculate_roe(ticker: str, facts: pd.DataFrame) -> pd.DataFrame:
    """根据标准化基本面长表计算各财年 ROE。

    Args:
        ticker: 股票代码。
        facts: `sources.sec.get_fundamentals` 的输出, 至少含 net_income 与
            total_equity 两个字段。

    Returns:
        DataFrame, 列为 [ticker, period_end, net_income, beginning_equity,
        ending_equity, average_equity, roe, roe_percent], 按 period_end 从新到旧。
    """
    annual = facts[facts["form"].isin(_ANNUAL_FORMS) & ~facts["derived"]]
    income = annual[annual["field"].eq("net_income") & annual["period_months"].eq(12)]
    equity = annual[annual["field"].eq("total_equity") & annual["period_months"].eq(0)]

    rows: list[dict[str, object]] = []
    for accn, inc in income.groupby("accn", sort=False):
        current = inc.loc[inc["period_end"].idxmax()]
        end = current["period_end"]
        eq = equity[equity["accn"].eq(accn)]

        ending = eq[eq["period_end"].eq(end)]
        gap = (end - eq["period_end"]).dt.days
        beginning = eq[gap.between(*_PRIOR_YEAR_DAYS)].sort_values("period_end")
        if ending.empty or beginning.empty:
            continue
        ending_row, beginning_row = ending.iloc[0], beginning.iloc[-1]
        if ending_row["concept"] != beginning_row["concept"]:
            logger.warning(
                f"{ticker} {end.date()}: 期初/期末权益用了不同科目 "
                f"({beginning_row['concept']} / {ending_row['concept']}), ROE 口径可能不一致"
            )

        net_income = float(current["value"])
        ending_equity = float(ending_row["value"])
        beginning_equity = float(beginning_row["value"])
        average_equity = (beginning_equity + ending_equity) / 2
        roe = float("nan") if average_equity == 0 else net_income / average_equity
        rows.append(
            {
                "ticker": ticker.upper(),
                "period_end": pd.Timestamp(end),
                "net_income": net_income,
                "beginning_equity": beginning_equity,
                "ending_equity": ending_equity,
                "average_equity": average_equity,
                "roe": roe,
                "roe_percent": roe * 100,
                "_filed": current["filed"],
            }
        )

    if not rows:
        return pd.DataFrame(columns=_ROE_COLUMNS)

    result = (
        pd.DataFrame(rows)
        .sort_values(["period_end", "_filed"])
        .drop_duplicates("period_end", keep="last")  # 同一财年多次作为"本年"申报, 取最新
        .sort_values("period_end", ascending=False)
    )
    return result[_ROE_COLUMNS].reset_index(drop=True)


def get_roe(ticker: str, years: int = 1) -> pd.DataFrame:
    """抓取数据并返回指定公司最近若干财年的 ROE(按 period_end 从新到旧)。"""

    if years < 1:
        raise ValueError("years 必须大于等于 1")

    facts = get_fundamentals(ticker, ["net_income", "total_equity"], derive=False)
    result = calculate_roe(ticker, facts)
    if result.empty:
        raise ValueError(f"{ticker} 的 10-K 里找不到可用的净利润/股东权益")
    return result.head(years).reset_index(drop=True)


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

    ticker_list = list(tickers)
    iterator = (
        tqdm(ticker_list, desc="计算 ROE", unit="只")
        if show_progress
        else ticker_list
    )

    frames: list[pd.DataFrame] = []
    for ticker in iterator:
        if isinstance(iterator, tqdm):
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
