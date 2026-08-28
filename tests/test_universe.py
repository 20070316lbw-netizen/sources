import pytest
from pydantic import ValidationError

from sources.universe.fetch import SP500UniverseMember


def test_universe_member_normalization():
    """测试 SP500UniverseMember 的自动格式化规则"""
    member = SP500UniverseMember(
        ticker="brk.b",
        company_name=" Berkshire Hathaway ",
        cik="1067983",
    )
    assert member.ticker == "BRK-B"
    assert member.company_name == "Berkshire Hathaway"
    assert member.cik == "0001067983"


def test_universe_member_int_cik():
    """测试整型 CIK 的自动补零"""
    member = SP500UniverseMember(
        ticker="AAPL",
        company_name="Apple Inc.",
        cik=320193,  # type: ignore
    )
    assert member.cik == "0000320193"


def test_universe_member_invalid_cik():
    """测试非法 CIK 触发校验错误"""
    with pytest.raises(ValidationError):
        SP500UniverseMember(
            ticker="AAPL",
            company_name="Apple Inc.",
            cik="invalid_cik",
        )


def test_universe_member_empty_name():
    """测试空公司名触发校验错误"""
    with pytest.raises(ValidationError):
        SP500UniverseMember(
            ticker="AAPL",
            company_name="   ",
            cik="0000320193",
        )
