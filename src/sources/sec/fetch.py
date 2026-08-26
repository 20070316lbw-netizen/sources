"""SEC EDGAR 基本面数据抓取与 PIT 日频处理模块 (基于 edgartools)"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd
from edgar import Company, set_identity
from loguru import logger

from sources.config import SEC_IDENTITY
from sources.error import EdgarFetchError
from sources.universe.fetch import load_cached_universe


def init_edgar(identity: str | None = None) -> None:
    """初始化 SEC EDGAR 请求身份标识 (User-Agent)。"""
    sec_id = identity or SEC_IDENTITY
    set_identity(sec_id)
    logger.debug(f"已初始化 SEC EDGAR 身份标识: {sec_id}")


def fetch_filing_metrics(
    symbol: str,
    *,
    forms: Sequence[str] = ("10-K", "10-Q"),
    limit: int = 8,
) -> pd.DataFrame:
    """抓取单个标的的 10-K / 10-Q 财报关键财务指标及披露日期 (PIT)。

    Args:
        symbol: 股票代码 (如 'AAPL')
        forms: 抓取的财报类型，默认 ('10-K', '10-Q')
        limit: 抓取最新的财报数量，默认最新 8 期

    Returns:
        pd.DataFrame: 包含 date (披露日), ticker, form, period_end 及各项财务指标的 DataFrame。
    """
    init_edgar()
    try:
        company = Company(symbol)
        filings = company.get_filings(form=list(forms)).latest(limit)
    except Exception as exc:
        raise EdgarFetchError(f"获取 {symbol} 财报列表失败: {exc}") from exc

    records: list[dict] = []
    for filing in filings: # type: ignore
        try:
            obj = filing.obj()
            if obj and hasattr(obj, "financials") and obj.financials:
                metrics = obj.financials.get_financial_metrics()
                if metrics:
                    metrics["date"] = pd.to_datetime(filing.filing_date)
                    metrics["ticker"] = symbol.upper()
                    metrics["form"] = filing.form
                    metrics["period_end"] = pd.to_datetime(filing.period_of_report)
                    records.append(metrics)
        except Exception as exc:
            logger.warning(f"解析 {symbol} 财报 {filing.form} ({filing.filing_date}) 失败: {exc}")

    if not records:
        raise EdgarFetchError(f"未能提取到 {symbol} 的任何有效基本面财务指标")

    df = pd.DataFrame(records)
    # 按披露日期排序
    df = df.sort_values(by="date").reset_index(drop=True)
    return df


def fetch_sp500_fundamentals(
    symbols: list[str] | None = None,
    *,
    forms: Sequence[str] = ("10-K", "10-Q"),
    limit: int = 8,
) -> pd.DataFrame:
    """批量抓取 S&P 500 成分股的基本面财报数据。

    Args:
        symbols: 指定抓取的标的列表，若为 None 则从本地 S&P 500 缓存读取全部标的。
        forms: 财报类型列表，默认 ('10-K', '10-Q')。
        limit: 每只标的抓取的最新期数。

    Returns:
        pd.DataFrame: 合并后的全标的原始财报指标数据表。
    """
    if symbols is None:
        universe_df = load_cached_universe()
        symbols = universe_df["ticker"].tolist()

    all_dfs: list[pd.DataFrame] = []
    total = len(symbols)
    logger.info(f"开始批量抓取 {total} 只标的的基本面数据...")

    for idx, sym in enumerate(symbols, start=1):
        try:
            df_sym = fetch_filing_metrics(sym, forms=forms, limit=limit)
            all_dfs.append(df_sym)
            logger.info(f"[{idx}/{total}] 成功抓取 {sym} 基本面数据 ({len(df_sym)} 期)")
        except EdgarFetchError as exc:
            logger.warning(f"[{idx}/{total}] 抓取 {sym} 失败: {exc}")
        except Exception as exc:
            logger.error(f"[{idx}/{total}] 抓取 {sym} 出现未捕获异常: {exc}")

    if not all_dfs:
        raise EdgarFetchError("所有标的基本面数据抓取均失败")

    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df


def to_daily_pit(
    df_fundamentals: pd.DataFrame,
    *,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    trading_days: pd.DatetimeIndex | Sequence[pd.Timestamp] | None = None,
) -> pd.DataFrame:
    """将财报截面数据转换为与行情数据完全对齐的日频 Point-in-Time (PIT) 数据。

    处理逻辑：
    1. 以财报实际向 SEC 披露的日期 (date / filing_date) 作为生效生效起点;
    2. 使用 pandas 现成的 unstack -> reindex -> ffill -> stack 流水线，在新财报披露前自动沿用上期数据；
    3. 输出 MultiIndex 为 ['Date', 'Ticker']，列名统一为小写，与 Yahoo 价格数据结构无缝拼接。
    """
    if df_fundamentals.empty:
        raise ValueError("输入的基本面数据为空")

    df = df_fundamentals.copy()
    # 统一日期格式与列
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].str.upper()

    # 剔除无法 forward-fill 的辅助非数值元数据列
    non_numeric_cols = {"form", "period_end"}
    numeric_cols = [c for c in df.columns if c not in (non_numeric_cols | {"date", "ticker"})]
    df_metrics = df[["date", "ticker"] + numeric_cols]

    # 去重（若同一天存在多份披露，保留最后一条）
    df_metrics = df_metrics.drop_duplicates(subset=["date", "ticker"], keep="last")

    # 确定日频日历 (优先使用传入的交易日列表，其次根据 start/end 生成工作日，最后使用数据内置日期跨度)
    if trading_days is not None:
        calendar = pd.DatetimeIndex(trading_days) # type: ignore
    elif start is not None and end is not None:
        calendar = pd.date_range(start=start, end=end, freq="B")
    else:
        calendar = pd.date_range(
            start=df_metrics["date"].min(),
            end=df_metrics["date"].max(),
            freq="B",
        )

    # 借助 pandas unstack -> reindex -> ffill -> stack 现成机制完成日频 PIT 处理
    unstacked = df_metrics.set_index(["date", "ticker"]).unstack(level="ticker")
    # 对日历进行重索引并沿时间轴前向填充 (ffill)
    daily_unstacked = unstacked.reindex(calendar).ffill()

    # 重塑回 (Date, Ticker) MultiIndex 长表
    daily_pit = daily_unstacked.stack(level="ticker", future_stack=True)
    daily_pit.index.names = ["Date", "Ticker"]
    daily_pit.columns = daily_pit.columns.str.lower() # type: ignore
    daily_pit = daily_pit.sort_index()

    return daily_pit # type: ignore


def save_fundamentals(
    df: pd.DataFrame,
    *,
    path: Path | str,
) -> None:
    """将基本面数据保存为 Parquet 文件。"""
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path_obj)
