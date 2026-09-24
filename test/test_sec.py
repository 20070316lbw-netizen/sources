"""sources.sec: companyfacts 解析、字段标准化、单季推导、ticker->CIK、身份与限速。

全部用 conftest 里的假 companyfacts JSON, 不访问网络。
"""
from __future__ import annotations

import pandas as pd
import pytest

import sources.sec._client as client_module
import sources.sec.fields as fields_module
from sources._http import DEFAULT_SEC_IDENTITY, sec_identity_headers
from sources.sec import (
    FUNDAMENTAL_COLUMNS,
    RAW_FACT_COLUMNS,
    derive_quarters,
    get_cik,
    get_fundamentals,
    get_fundamentals_batch,
    parse_company_facts,
    standardize_facts,
)
from sources.sec.fundamentals import period_months


def _one(df: pd.DataFrame, **conditions) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for column, value in conditions.items():
        mask &= df[column].eq(value)
    hit = df[mask]
    assert len(hit) == 1, f"期望 1 行, 实际 {len(hit)} 行: {conditions}"
    return hit.iloc[0]


# ---------------------------------------------------------------- 解析


def test_parse_company_facts_flattens_all_units(companyfacts):
    raw = parse_company_facts(companyfacts)

    assert raw.columns.tolist() == RAW_FACT_COLUMNS
    assert len(raw) == 12 + 1 + 4 + 4 + 1 + 1
    assert set(raw["cik"]) == {"0000001234"}
    instant = raw[raw["concept"].eq("StockholdersEquity")]
    assert instant["period_start"].isna().all()
    assert pd.api.types.is_datetime64_any_dtype(raw["filed"])


def test_parse_company_facts_filters_concepts(companyfacts):
    raw = parse_company_facts(companyfacts, concepts={"us-gaap:StockholdersEquity"})

    assert set(raw["concept"]) == {"StockholdersEquity"}
    assert len(raw) == 4


# ---------------------------------------------------------------- 标准化


def test_standardize_prefers_higher_priority_concept_within_filing(companyfacts):
    facts = standardize_facts(parse_company_facts(companyfacts), "test", ["net_income"])

    fy24 = _one(facts, accn="K24", period_end=pd.Timestamp("2024-12-31"))
    assert fy24["concept"] == "us-gaap:NetIncomeLoss"
    assert fy24["value"] == 500
    assert fy24["ticker"] == "TEST"
    assert fy24["period_months"] == 12


def test_standardize_drops_non_periodic_forms(companyfacts):
    facts = standardize_facts(parse_company_facts(companyfacts), "TEST", ["net_income"])

    assert "E8K" not in set(facts["accn"])
    assert facts.columns.tolist() == FUNDAMENTAL_COLUMNS


def test_standardize_instant_and_cover_page_fields(companyfacts):
    raw = parse_company_facts(companyfacts)
    facts = standardize_facts(raw, "TEST", ["total_equity", "shares_outstanding"])

    equity = facts[facts["field"].eq("total_equity")]
    assert (equity["period_months"] == 0).all()
    assert len(equity) == 4  # 两份 10-K 各两个时点, 所有版本都保留
    shares = _one(facts, field="shares_outstanding")
    assert shares["concept"] == "dei:EntityCommonStockSharesOutstanding"
    assert shares["value"] == 50


def test_standardize_rejects_unknown_field(companyfacts):
    with pytest.raises(KeyError, match="未定义"):
        standardize_facts(parse_company_facts(companyfacts), "TEST", ["nope"])


def test_ticker_override_changes_concept_priority(monkeypatch, companyfacts):
    monkeypatch.setattr(
        fields_module, "TICKER_FIELD_OVERRIDES", {"TEST": {"net_income": ("us-gaap:ProfitLoss",)}}
    )
    facts = standardize_facts(parse_company_facts(companyfacts), "TEST", ["net_income"])

    assert facts["concept"].unique().tolist() == ["us-gaap:ProfitLoss"]
    assert facts["value"].tolist() == [510]


@pytest.mark.parametrize(
    ("start", "end", "months"),
    [
        ("2024-01-01", "2024-12-31", 12),
        ("2023-10-01", "2024-09-28", 12),  # 52 周财年 364 天
        ("2023-09-24", "2024-09-28", 12),  # 53 周财年 371 天
        ("2024-01-01", "2024-03-31", 3),
        ("2024-06-30", "2024-10-05", 3),  # 14 周季度 98 天
        ("2024-01-01", "2024-09-30", 9),
        ("2024-06-10", "2024-09-01", 3),  # Costco/百事 12 周季度 84 天
        ("2024-06-10", "2024-09-29", 3),  # 16 周的第四季度 112 天
        ("2023-09-04", "2024-05-12", 9),  # 36 周累计 252 天
        ("2023-09-04", "2024-02-18", 6),  # 24 周累计 168 天
        ("2024-01-01", "2024-01-31", 1),  # 区间外按天数折算
    ],
)
def test_period_months(start, end, months):
    result = period_months(pd.Series([pd.Timestamp(start)]), pd.Series([pd.Timestamp(end)]))
    assert result.iloc[0] == months


def test_period_months_instant_is_zero():
    result = period_months(pd.Series([pd.NaT]), pd.Series([pd.Timestamp("2024-12-31")]))
    assert result.iloc[0] == 0


# ---------------------------------------------------------------- 单季推导


def _derived(companyfacts, fields) -> pd.DataFrame:
    facts = standardize_facts(parse_company_facts(companyfacts), "TEST", fields)
    return derive_quarters(facts)


def test_derive_cash_flow_quarters_from_ytd(companyfacts):
    out = _derived(companyfacts, ["operating_cash_flow"])
    quarters = out[out["period_months"].eq(3)].set_index("period_end")

    assert quarters["value"].to_dict() == {
        pd.Timestamp("2024-03-31"): 50,
        pd.Timestamp("2024-06-30"): 60,
        pd.Timestamp("2024-09-30"): 70,
        pd.Timestamp("2024-12-31"): 80,
    }
    q4 = quarters.loc[pd.Timestamp("2024-12-31")]
    assert bool(q4["derived"]) is True
    assert q4["accn"] == "K24"
    assert q4["filed"] == pd.Timestamp("2025-02-10")  # 沿用被减数所在文件的申报日
    assert q4["period_start"] == pd.Timestamp("2024-10-01")


def test_derive_keeps_reported_quarter_over_derived(companyfacts):
    out = _derived(companyfacts, ["net_income"])

    q2 = _one(out, accn="Q224", period_end=pd.Timestamp("2024-06-30"), period_months=3)
    assert q2["value"] == 120
    assert bool(q2["derived"]) is False


def test_derive_q4_from_annual_and_restatement(companyfacts):
    out = _derived(companyfacts, ["net_income"])
    q4 = out[out["period_months"].eq(3) & out["period_end"].eq(pd.Timestamp("2024-12-31"))]

    assert q4.set_index("accn")["value"].to_dict() == {"K24": 140, "K24A": 120}
    assert q4["derived"].all()


def test_derive_only_uses_information_known_at_filing(companyfacts):
    # 9 个月累计值在 10-K 之后才申报: 推导 Q4 时不能用
    for item in companyfacts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]:
        if item["accn"] == "Q324":
            item["filed"] = "2025-03-01"
    out = _derived(companyfacts, ["net_income"])
    q4 = out[out["period_months"].eq(3) & out["period_end"].eq(pd.Timestamp("2024-12-31"))]

    assert q4.set_index("accn")["value"].to_dict() == {"K24A": 120}


def test_derive_skips_non_additive_fields(companyfacts):
    raw = parse_company_facts(companyfacts)
    raw.loc[raw["concept"].eq("NetIncomeLoss"), "concept"] = "EarningsPerShareDiluted"
    raw.loc[raw["concept"].eq("EarningsPerShareDiluted"), "unit"] = "USD/shares"
    out = derive_quarters(standardize_facts(raw, "TEST", ["eps_diluted"]))

    assert not out["derived"].any()


# ---------------------------------------------------------------- 抓取入口


def test_get_fundamentals_end_to_end(mock_sec):
    out = get_fundamentals("test")

    assert set(out["field"]) == {"net_income", "operating_cash_flow", "total_equity",
                                 "shares_outstanding"}
    assert (out["ticker"] == "TEST").all()
    assert mock_sec[-1].endswith("CIK0000001234.json")


def test_get_fundamentals_accepts_explicit_cik(mock_sec):
    out = get_fundamentals("OLD", ["net_income"], cik=1234)

    assert (out["ticker"] == "OLD").all()
    assert not any(url.endswith("company_tickers.json") for url in mock_sec)


def test_get_fundamentals_batch_skips_failures(mock_sec):
    out = get_fundamentals_batch(["TEST", "UNKNOWN", "BRK.B"], ["net_income"],
                                 show_progress=False)

    # UNKNOWN 查不到 CIK 被跳过; BRK.B 统一成 BRK-B 后能查到(假数据同一份)
    assert sorted(out["ticker"].unique()) == ["BRK.B", "TEST"]


def test_get_fundamentals_batch_empty_keeps_columns(mock_sec):
    out = get_fundamentals_batch(["UNKNOWN"], show_progress=False)

    assert out.empty
    assert out.columns.tolist() == FUNDAMENTAL_COLUMNS


def test_get_cik_normalizes_and_accepts_digits(mock_sec):
    assert get_cik("brk.b") == "0001067983"
    assert get_cik(320193) == "0000320193"
    with pytest.raises(ValueError, match="找不到"):
        get_cik("NOPE")


# ---------------------------------------------------------------- 身份与限速


def test_sec_identity_defaults_and_env_override(monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    assert sec_identity_headers()["User-Agent"] == DEFAULT_SEC_IDENTITY == (
        "liu 20070316lbw@gmail.com"
    )

    monkeypatch.setenv("EDGAR_IDENTITY", "Someone else@example.com")
    assert sec_identity_headers()["User-Agent"] == "Someone else@example.com"


def test_throttle_spaces_requests(monkeypatch):
    clock = {"now": 100.0}
    sleeps: list[float] = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(client_module.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(client_module.time, "sleep", fake_sleep)
    monkeypatch.setattr(client_module, "_last_request", 0.0)

    client_module._throttle()
    client_module._throttle()

    assert sleeps == [pytest.approx(client_module.MIN_INTERVAL)]


def test_get_fundamentals_merges_predecessor_ciks(monkeypatch, mock_sec):
    import sources.sec.tickers as tickers_module

    monkeypatch.setattr(tickers_module, "PREDECESSOR_CIKS", {"TEST": ("0000000042",)})
    out = get_fundamentals("TEST", ["total_equity"])

    fetched = [url.rsplit("/", 1)[-1] for url in mock_sec if "companyfacts" in url]
    assert fetched == ["CIK0000000042.json", "CIK0000001234.json"]
    # 文件号(accn)全局唯一; 假数据两份相同, 同一 accn 的重复事实只留一条
    assert len(out) == 4


def test_get_fundamentals_accepts_cik_list(mock_sec):
    get_fundamentals("OLD", ["net_income"], cik=[42, "1234"])

    fetched = [url.rsplit("/", 1)[-1] for url in mock_sec if "companyfacts" in url]
    assert fetched == ["CIK0000000042.json", "CIK0000001234.json"]


def test_derive_falls_back_to_other_concept_when_company_switches(companyfacts):
    # 10-K 换成了 ...ContinuingOperations 科目, 季报仍是原科目: 仍能推导 Q4
    gaap = companyfacts["facts"]["us-gaap"]
    ocf = gaap["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"]
    annual = [item for item in ocf if item["accn"] == "K24"]
    gaap["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"] = [
        item for item in ocf if item["accn"] != "K24"
    ]
    gaap["NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"] = {
        "units": {"USD": annual}
    }
    out = _derived(companyfacts, ["operating_cash_flow"])

    q4 = _one(out, period_months=3, period_end=pd.Timestamp("2024-12-31"))
    assert q4["value"] == 80
    assert q4["concept"].endswith("ContinuingOperations")


def test_derive_prefers_same_concept(companyfacts):
    # 同一 9 个月期间另有一个更晚申报、不同科目的版本: 仍用同科目的那个
    gaap = companyfacts["facts"]["us-gaap"]
    gaap["NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"] = {
        "units": {"USD": [{"start": "2024-01-01", "end": "2024-09-30", "val": 999,
                           "accn": "Q324B", "fy": 2024, "fp": "Q3", "form": "10-Q/A",
                           "filed": "2024-12-01"}]}
    }
    out = _derived(companyfacts, ["operating_cash_flow"])

    q4 = _one(out, period_months=3, period_end=pd.Timestamp("2024-12-31"))
    assert q4["value"] == 80
