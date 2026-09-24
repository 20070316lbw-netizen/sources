"""基本面标准化: companyfacts 原始事实 -> 带申报日期的标准字段长表(点时数据原料)。

输出每行是"某份申报文件(accn, filed)对某个期间报告的某个标准字段的值", 同一期间
的多个版本(原始申报 + 之后作为比较期/重述再次出现)全部保留, 不做取舍——按
filed 做 as-of 查询是存储层(liudb)的事。

单季值推导: 10-Q 的现金流量表只有年初至今累计值, 10-K 只有全年值, 所以很多单季
(第四季度、现金流的 Q2/Q3)没有直接报告。对可加的期间型字段, 用同一份文件的累计
值减去**当时已知**的上一个累计值(同一财年起点、同一科目)推出 3 个月值, 标记
derived=True, 申报日期和 accn 沿用被减数所在的文件——推导所用的信息在那一天
都已公开, 不会引入未来数据。
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd
from loguru import logger
from tqdm import tqdm

from sources.sec.companyfacts import get_company_facts
from sources.sec.fields import FIELDS, get_field_concepts
from sources.sec.tickers import get_ciks

FUNDAMENTAL_COLUMNS = [
    "ticker",
    "cik",
    "field",
    "concept",
    "unit",
    "period_start",
    "period_end",
    "period_months",
    "value",
    "fy",
    "fp",
    "form",
    "accn",
    "filed",
    "derived",
]

# 年报/季报及其修订版; 8-K、S-1 等里的零星 XBRL 事实不要
DEFAULT_FORMS: tuple[str, ...] = (
    "10-K", "10-K/A", "10-Q", "10-Q/A", "10-KT", "10-KT/A", "10-QT", "10-QT/A",
)

_DAYS_PER_MONTH = 365.25 / 12
_MONTH_BUCKETS: dict[tuple[int, int], int] = {
    (70, 125): 3,
    (150, 210): 6,
    (230, 300): 9,
    (330, 390): 12,
}
# 推导单季时, 两个累计值的截止日应相差约一个季度(12~16 周)
_QUARTER_GAP_DAYS = (70, 125)
# 同一版本的主键: 一份文件里同一字段、同一期间只留一个值
_VERSION_KEY = ["ticker", "field", "accn", "period_end", "period_months"]


def period_months(start: pd.Series, end: pd.Series) -> pd.Series:
    """期间长度归到财务季度档位(月数); 时点型(start 为 NaT)记 0。

    不能简单按天数/30 四舍五入: 不少公司按周划分季度, 如 Costco、百事的季度是
    12/12/12/16 周, 16 周的第四季度有 112 天、36 周的前三季度累计 252 天, 直接折算
    会变成 4 个月和 8 个月。这里按天数区间归档:

        70~125 天 -> 3, 150~210 -> 6, 230~300 -> 9, 330~390 -> 12

    落在区间外的(如过渡期报告)才按天数折算的月数取整。
    """
    days = (end - start).dt.days + 1
    months = (days / _DAYS_PER_MONTH).round()
    for (low, high), bucket in _MONTH_BUCKETS.items():
        months = months.mask(days.between(low, high), bucket)
    return months.fillna(0).astype("int64")


def standardize_facts(
    raw: pd.DataFrame,
    ticker: str,
    fields: Iterable[str] | None = None,
    forms: Sequence[str] | None = DEFAULT_FORMS,
) -> pd.DataFrame:
    """把 companyfacts 原始长表映射成标准字段(不含推导的单季值)。

    Args:
        raw: `get_company_facts` / `parse_company_facts` 的输出。
        ticker: 写进结果的 ticker(原样大写, 不做格式转换, 以便和行情表对上)。
        fields: 要的标准字段, 默认 FIELDS 里全部。
        forms: 只保留这些表单类型的申报; None 表示不过滤。

    Returns:
        DataFrame, 列为 FUNDAMENTAL_COLUMNS, derived 全为 False。

    Raises:
        KeyError: fields 里有未定义的字段。
    """
    field_list = _check_fields(fields)

    data = raw
    if forms is not None:
        data = data[data["form"].isin(list(forms))]
    qualified = data["taxonomy"] + ":" + data["concept"]

    frames: list[pd.DataFrame] = []
    for field in field_list:
        spec = FIELDS[field]
        concepts = get_field_concepts(field, ticker)
        priority = {concept: rank for rank, concept in enumerate(concepts)}

        mask = qualified.isin(concepts) & data["unit"].eq(spec.unit)
        is_instant = data["period_start"].isna()
        mask &= is_instant if spec.kind == "instant" else ~is_instant
        rows = data.loc[mask].copy()
        if rows.empty:
            continue
        rows["concept"] = qualified[mask]
        rows["field"] = field
        rows["_priority"] = rows["concept"].map(priority)
        frames.append(rows)

    if not frames:
        return _empty()

    out = pd.concat(frames, ignore_index=True)
    out["ticker"] = ticker.upper()
    out["period_months"] = period_months(out["period_start"], out["period_end"])
    out["derived"] = False
    # 同一文件、同一期间命中多个候选科目时, 按优先级留一个
    out = (
        out.sort_values(["_priority", "filed"])
        .drop_duplicates(_VERSION_KEY, keep="first")
    )
    return _finalize(out)


def derive_quarters(facts: pd.DataFrame) -> pd.DataFrame:
    """用累计值之差补出没有直接报告的单季(3 个月)值, 追加到原表后返回。

    对每个可加字段的 6/9/12 个月累计值 F, 找同一字段、同一期间起点、短 3 个月、
    且在 F 申报当天或之前已公开的累计值 G, 单季 = F - G。G 有多个候选时优先用
    和 F 同一科目的(公司换科目时才退而用别的候选科目), 再取最新申报的版本。
    同一份文件里已经直接报告了该单季的, 以报告值为准, 不再推导。
    """
    if facts.empty:
        return facts

    additive = [name for name, spec in FIELDS.items() if spec.additive]
    dur = facts[facts["field"].isin(additive) & facts["period_months"].isin([3, 6, 9, 12])]
    later = dur[dur["period_months"] >= 6]
    earlier = dur[dur["period_months"] <= 9]

    keys = ["ticker", "field", "period_start"]
    m = later.merge(
        earlier[[*keys, "concept", "period_end", "period_months", "value", "filed", "accn"]],
        on=keys, suffixes=("", "_g"),
    )
    gap = (m["period_end"] - m["period_end_g"]).dt.days
    m = m[
        m["period_months_g"].eq(m["period_months"] - 3)
        & m["filed_g"].le(m["filed"])
        & gap.between(*_QUARTER_GAP_DAYS)
    ]
    if m.empty:
        return facts

    # 同一个 F 可能对上多个 G: 同科目优先, 其次取 F 申报时已知的最新版本
    m = m.assign(_same=m["concept"].eq(m["concept_g"]))
    m = m.sort_values(["_same", "filed_g", "accn_g"]).drop_duplicates(
        ["ticker", "field", "accn", "period_end", "period_months"], keep="last"
    )
    derived = m[FUNDAMENTAL_COLUMNS].copy()
    derived["period_start"] = m["period_end_g"] + pd.Timedelta(days=1)
    derived["period_months"] = 3
    derived["value"] = m["value"] - m["value_g"]
    derived["derived"] = True

    combined = pd.concat([facts, derived], ignore_index=True)
    # 报告值(derived=False)排在前面, 同一文件同一单季只留报告值
    combined = combined.sort_values("derived", kind="stable").drop_duplicates(
        _VERSION_KEY, keep="first"
    )
    return _finalize(combined)


def get_fundamentals(
    ticker: str,
    fields: Iterable[str] | None = None,
    *,
    cik: str | int | Sequence[str | int] | None = None,
    forms: Sequence[str] | None = DEFAULT_FORMS,
    derive: bool = True,
) -> pd.DataFrame:
    """抓取一家公司全部历史申报里的标准化基本面(每个 CIK 一次 SEC 请求)。

    Args:
        ticker: 股票代码, 原样写进结果(如 "BRK-B")。
        fields: 标准字段列表, 默认全部, 见 `sources.sec.FIELDS`。
        cik: 直接指定 CIK(可以是多个, 如前身 + 现主体), 用于已退市/改名、映射表里
            查不到的公司。默认按 ticker 查当前 CIK 并带上 PREDECESSOR_CIKS 里的前身。
        forms: 保留的申报表单类型, 默认 10-K/10-Q 及修订版。
        derive: 是否推导未直接报告的单季值。

    Returns:
        DataFrame, 列为 FUNDAMENTAL_COLUMNS:
        ticker, cik, field, concept(实际命中的科目), unit,
        period_start(时点型为 NaT), period_end, period_months(0=时点, 3/6/9/12=期间),
        value, fy/fp/form(申报文件的财年/期间/表单), accn(文件号), filed(申报日),
        derived(是否为推导的单季值)。
    """
    field_list = _check_fields(fields)
    concepts = {c for name in field_list for c in get_field_concepts(name, ticker)}

    if cik is None:
        ciks: list[str | int] = list(get_ciks(ticker))
    elif isinstance(cik, (str, int)):
        ciks = [cik]
    else:
        ciks = list(cik)
    raw = pd.concat(
        [get_company_facts(c, concepts=concepts) for c in ciks], ignore_index=True
    )
    facts = standardize_facts(raw, ticker, field_list, forms)
    return derive_quarters(facts) if derive else facts


def get_fundamentals_batch(
    tickers: Iterable[str],
    fields: Iterable[str] | None = None,
    *,
    forms: Sequence[str] | None = DEFAULT_FORMS,
    derive: bool = True,
    show_progress: bool = True,
) -> pd.DataFrame:
    """批量抓取; 单只失败(如 ticker 查不到 CIK)记 warning 后跳过, 不中断其余股票。

    SEC 限速每秒 10 次, 这里每只股票一次请求、全局限速约每秒 8 次。
    """
    field_list = _check_fields(fields)
    ticker_list = list(tickers)
    iterator = (
        tqdm(ticker_list, desc="抓取基本面", unit="只") if show_progress else ticker_list
    )

    frames: list[pd.DataFrame] = []
    for ticker in iterator:
        if isinstance(iterator, tqdm):
            iterator.set_postfix_str(ticker)
        try:
            frames.append(get_fundamentals(ticker, field_list, forms=forms, derive=derive))
        except Exception as error:  # noqa: BLE001 - 批量任务不能被单只股票中断
            logger.warning(f"{ticker}: 基本面抓取失败，已跳过 ({error})")

    frames = [f for f in frames if not f.empty]
    if not frames:
        return _empty()
    return pd.concat(frames, ignore_index=True)


def _check_fields(fields: Iterable[str] | None) -> list[str]:
    field_list = list(fields) if fields is not None else list(FIELDS)
    unknown = [f for f in field_list if f not in FIELDS]
    if unknown:
        raise KeyError(f"未定义的基本面字段: {unknown}; 可选: {sorted(FIELDS)}")
    return field_list


def _empty() -> pd.DataFrame:
    return _finalize(pd.DataFrame(columns=FUNDAMENTAL_COLUMNS))


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df[FUNDAMENTAL_COLUMNS].copy()
    for col in ("period_start", "period_end", "filed"):
        out[col] = pd.to_datetime(out[col])
    out["period_months"] = out["period_months"].astype("int64")
    out["value"] = out["value"].astype("float64")
    out["fy"] = pd.to_numeric(out["fy"], errors="coerce").astype("Int64")
    out["derived"] = out["derived"].astype(bool)
    for col in ("ticker", "cik", "field", "concept", "unit", "fp", "form", "accn"):
        out[col] = out[col].astype("string")
    return out.sort_values(
        ["field", "period_end", "period_months", "filed", "accn"], ignore_index=True
    )
