"""SEC XBRL companyfacts 接口: 一家公司历年所有 XBRL 申报里的全部数值事实。

    https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

每条事实(fact)带着它**出自哪份文件**(accn)和**哪天申报的**(filed)。同一个
会计期间的同一科目, 会在当期报告和之后若干份报告(作为比较期)里各出现一次,
重述时数值还会不同——这正是做点时(PIT)数据需要的原料: 任意时点 t 能看到的
数值 = filed <= t 的版本里最新申报的那个。

这里只做解析和改列名, 不挑科目、不去重; 标准化在 `fundamentals` 模块里做。
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from sources.sec._client import sec_get_json
from sources.sec.tickers import format_cik, get_cik

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

RAW_FACT_COLUMNS = [
    "cik",
    "taxonomy",
    "concept",
    "unit",
    "period_start",
    "period_end",
    "value",
    "fy",
    "fp",
    "form",
    "accn",
    "filed",
    "frame",
]


def fetch_company_facts(ticker_or_cik: str | int) -> dict[str, Any]:
    """下载 companyfacts 原始 JSON。"""
    cik = get_cik(ticker_or_cik)
    return sec_get_json(COMPANYFACTS_URL.format(cik=cik))


def parse_company_facts(
    payload: dict[str, Any],
    concepts: Iterable[str] | None = None,
) -> pd.DataFrame:
    """把 companyfacts JSON 展开成长表。

    Args:
        payload: companyfacts 接口返回的 JSON。
        concepts: 只保留这些科目, 写成 "taxonomy:Concept"(如 "us-gaap:Revenues");
            None 表示全部保留。

    Returns:
        DataFrame, 列为 RAW_FACT_COLUMNS。时点型(instant)事实的 period_start 为 NaT;
        fy/fp/form 描述的是**申报文件**的财年/期间, 不一定是这条事实本身所属的期间
        (比较期数据尤其如此), 期间以 period_start/period_end 为准。
    """
    wanted = set(concepts) if concepts is not None else None
    cik = format_cik(payload.get("cik", 0))
    rows: list[tuple] = []

    for taxonomy, facts in (payload.get("facts") or {}).items():
        for concept, body in facts.items():
            if wanted is not None and f"{taxonomy}:{concept}" not in wanted:
                continue
            for unit, items in (body.get("units") or {}).items():
                for item in items:
                    rows.append(
                        (
                            cik,
                            taxonomy,
                            concept,
                            unit,
                            item.get("start"),
                            item.get("end"),
                            item.get("val"),
                            item.get("fy"),
                            item.get("fp"),
                            item.get("form"),
                            item.get("accn"),
                            item.get("filed"),
                            item.get("frame"),
                        )
                    )

    df = pd.DataFrame(rows, columns=RAW_FACT_COLUMNS)
    df["period_start"] = pd.to_datetime(df["period_start"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["filed"] = pd.to_datetime(df["filed"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce").astype("float64")
    df["fy"] = pd.to_numeric(df["fy"], errors="coerce").astype("Int64")
    for col in ("cik", "taxonomy", "concept", "unit", "fp", "form", "accn", "frame"):
        df[col] = df[col].astype("string")
    return df.dropna(subset=["period_end", "value", "accn", "filed"]).reset_index(drop=True)


def get_company_facts(
    ticker_or_cik: str | int,
    concepts: Iterable[str] | None = None,
) -> pd.DataFrame:
    """抓取并解析一家公司的全部 XBRL 事实(一次请求)。

    Args:
        ticker_or_cik: ticker(如 "AAPL"、"BRK-B")或 CIK。
        concepts: 只保留的科目, 见 parse_company_facts。

    Returns:
        DataFrame, 列为 RAW_FACT_COLUMNS。
    """
    return parse_company_facts(fetch_company_facts(ticker_or_cik), concepts)
