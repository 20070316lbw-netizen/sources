"""sources.sec: 直接从 SEC 官方接口抓取美股基本面(不依赖 edgartools)。

数据源是 SEC 的 XBRL companyfacts 接口, 一家公司一次请求拿到历年全部 10-K /
10-Q 里的数值事实, 每条都带申报日期(filed), 可直接做点时(PIT)数据。

公开 API:
    get_fundamentals        -- 单家公司的标准化基本面长表(含推导的单季值)
    get_fundamentals_batch  -- 批量版, 单只失败不中断
    get_company_facts       -- companyfacts 原始事实长表(全部科目, 未标准化)
    get_sec_tickers         -- SEC 的 ticker -> CIK 映射表
    get_cik / get_ciks      -- ticker -> 10 位 CIK(后者含控股重组前的前身 CIK)
    FIELDS                  -- 标准字段定义(候选科目、单位、时点/期间)
    TICKER_FIELD_OVERRIDES  -- 个股科目优先级覆盖

身份标识: SEC 要求 User-Agent 带名字和邮箱。默认用 "liu 20070316lbw@gmail.com",
设置环境变量 EDGAR_IDENTITY 可以覆盖。全局限速约每秒 8 次(SEC 上限 10 次)。
"""
from __future__ import annotations

from sources.sec.companyfacts import RAW_FACT_COLUMNS, get_company_facts, parse_company_facts
from sources.sec.fields import FIELDS, TICKER_FIELD_OVERRIDES, FieldSpec, get_field_concepts
from sources.sec.fundamentals import (
    DEFAULT_FORMS,
    FUNDAMENTAL_COLUMNS,
    derive_quarters,
    get_fundamentals,
    get_fundamentals_batch,
    standardize_facts,
)
from sources.sec.tickers import (
    PREDECESSOR_CIKS,
    format_cik,
    get_cik,
    get_ciks,
    get_sec_tickers,
    normalize_sec_ticker,
)

__all__ = [
    "DEFAULT_FORMS",
    "FIELDS",
    "FUNDAMENTAL_COLUMNS",
    "PREDECESSOR_CIKS",
    "RAW_FACT_COLUMNS",
    "TICKER_FIELD_OVERRIDES",
    "FieldSpec",
    "derive_quarters",
    "format_cik",
    "get_cik",
    "get_ciks",
    "get_company_facts",
    "get_field_concepts",
    "get_fundamentals",
    "get_fundamentals_batch",
    "get_sec_tickers",
    "normalize_sec_ticker",
    "parse_company_facts",
    "standardize_facts",
]
