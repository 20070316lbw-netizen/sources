"""基本面数据抓取, 数据源: SEC EDGAR (通过 edgartools)

主要目的是为 FF3 的 HML(账面市值比)因子准备原始输入——股东权益、流通股数
等 XBRL 概念的历史序列, 按公司抓取。

使用前提:
    必须设置环境变量 EDGAR_IDENTITY, 格式为 "Your Name your@email.com",
    这是 SEC 对访问者的身份要求。本包不会硬编码任何人的身份信息, 也不会
    在未设置该变量时静默地卡在交互式输入上——会直接抛出清晰的错误。

输出: 长表(long format), 每行是 (ticker, concept, period_end) 的一条事实,
列固定为 [ticker, concept, period_start, period_end, duration_days,
numeric_value, fiscal_period, fiscal_year]。

初步清洗:
    - 统一通过 edgartools 的 EntityFacts.time_series() 取数, 保证跨概念/
      跨公司的列结构一致
    - 附加 ticker/concept 两列方便下游按公司或概念筛选
    - 公司不存在、概念没有数据都只记录 warning 并跳过, 不中断整批抓取

不做的事(留给下游仓库/使用方):
    - 不同公司可能使用不同的 XBRL tag 表达同一个经济概念(口径统一问题),
      这里不做归一, 需要时通过 concepts 参数自行扩展
    - 不做单位换算、不做每股指标(如 book value per share)的计算
    - 不落盘、不缓存
"""
from __future__ import annotations

import os
from collections.abc import Sequence

import pandas as pd
from loguru import logger

# 与账面市值比(HML)最相关的默认概念, 可按需覆盖
DEFAULT_CONCEPTS: tuple[str, ...] = (
    "StockholdersEquity",
    "CommonStockSharesOutstanding",
)

_OUTPUT_COLUMNS = [
    "ticker",
    "concept",
    "period_start",
    "period_end",
    "duration_days",
    "numeric_value",
    "fiscal_period",
    "fiscal_year",
]

_IDENTITY_ENV = "EDGAR_IDENTITY"


def _ensure_identity() -> None:
    """确保 EDGAR_IDENTITY 已设置, 避免 edgartools 在无交互环境下卡住等待输入。"""
    identity = os.environ.get(_IDENTITY_ENV)
    if not identity:
        raise RuntimeError(
            f"未设置环境变量 {_IDENTITY_ENV}。SEC EDGAR 要求提供身份标识, "
            f'请先设置, 例如: export {_IDENTITY_ENV}="Your Name your@email.com"'
        )
    import edgar

    edgar.set_identity(identity)


def get_fundamentals(
    ticker: str,
    concepts: Sequence[str] = DEFAULT_CONCEPTS,
    periods: int = 20,
) -> pd.DataFrame:
    """抓取单个公司在给定 XBRL 概念上的历史事实序列。

    Args:
        ticker: 股票代码, 如 "AAPL"。
        concepts: 要抓取的 XBRL 概念名, 默认见 DEFAULT_CONCEPTS。
        periods: 每个概念最多取多少期(由 edgartools 按 filing_date 倒序截取)。

    Returns:
        DataFrame, 列见 _OUTPUT_COLUMNS。公司不存在、或所有概念都没有数据时,
        返回保留列结构的空 DataFrame。

    Raises:
        RuntimeError: 未设置 EDGAR_IDENTITY 环境变量。
    """
    _ensure_identity()
    import edgar

    logger.info(f"Fetching fundamentals for {ticker}: {list(concepts)}")

    try:
        company = edgar.Company(ticker)
    except edgar.CompanyNotFoundError:
        logger.warning(f"{ticker}: 在 EDGAR 中未找到该公司, 跳过")
        return _empty_frame()

    facts = company.get_facts()
    if facts is None:
        logger.warning(f"{ticker}: 无法获取 company facts, 跳过")
        return _empty_frame()

    frames = []
    for concept in concepts:
        df = facts.time_series(concept, periods=periods)
        if df is None or df.empty:
            logger.warning(f"{ticker}: 概念 '{concept}' 无数据, 跳过")
            continue
        df = df.assign(ticker=ticker, concept=concept)
        frames.append(df)

    if not frames:
        return _empty_frame()

    result = pd.concat(frames, ignore_index=True)
    result = result[_OUTPUT_COLUMNS]
    result = result.sort_values(["ticker", "concept", "period_end"]).reset_index(drop=True)
    return result


def get_fundamentals_batch(
    tickers: Sequence[str],
    concepts: Sequence[str] = DEFAULT_CONCEPTS,
    periods: int = 20,
) -> pd.DataFrame:
    """对多个公司循环抓取并拼接; 单个公司抛异常不影响其他公司。

    与 get_fundamentals 的区别: 单只股票调用时错误会直接抛出方便定位问题,
    批量调用时希望大盘扫描不因为个别公司出错而整体失败, 所以这里兜底捕获。
    """
    frames = []
    for ticker in tickers:
        try:
            frames.append(get_fundamentals(ticker, concepts=concepts, periods=periods))
        except Exception as e:  # noqa: BLE001 - 批量抓取需要容忍单个 ticker 出错
            logger.warning(f"{ticker}: 抓取失败, 跳过 ({e})")

    if not frames:
        return _empty_frame()
    return pd.concat(frames, ignore_index=True).reset_index(drop=True)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_OUTPUT_COLUMNS)


if __name__ == "__main__":
    df = get_fundamentals("AAPL")
    print(df)
