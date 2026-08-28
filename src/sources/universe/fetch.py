"""标的抓取. 删除了注释, 如需要复习可以去 Quant-Lab 复习"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from loguru import logger
from pydantic import BaseModel, Field, ValidationError, field_validator

from sources.config import SEC_IDENTITY
from sources.error import EdgarFetchError, WikiFetchError

_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_SEC_CIK_URL = "https://www.sec.gov/files/company_tickers.json"
_SEC_HEADERS = {"User-Agent": SEC_IDENTITY}
_MIN_EXPECTED_UNIVERSE_SIZE = 400
_MAX_EXPECTED_UNIVERSE_SIZE = 600


class SP500UniverseMember(BaseModel):
    """校验通过的一条 S&P 500 成分股记录, 校验通过才允许入库。"""

    ticker      : str = Field(min_length=1, max_length=10)
    company_name: str = Field(min_length=1)
    cik         : str = Field(
        pattern     = r"^\d{10}$",
        description ="SEC CIK, 固定 10 位数字, 不足的时候补 0",
    )
    # ^\d{10}$：^ $ 锁定首尾避免部分匹配混过, \d{10} 要求恰好 10 位数字


    @field_validator("cik", mode="before")
    @classmethod
    def _pad_cik(cls, v: object) -> object:
        """类型转换前补 0, 保住前导零。"""
        if isinstance(v, int):
            return str(v).zfill(10)

        if isinstance(v, str) and v.isdigit():
            return v.zfill(10)

        return v


    @field_validator("ticker", mode="before")
    @classmethod
    def _normalize_ticker(cls, v: object) -> object:
        """统一使用 yfinance 接受的 ticker 表示。"""
        if isinstance(v, str):
            return v.strip().upper().replace(".", "-")
        return v


    @field_validator("company_name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        normalized = v.strip()
        if not normalized:
            raise ValueError("公司名称不能为空")
        return normalized


def fetch_sp500_universe(
    *,
    timeout: float = 10,
    min_expected_size: int = _MIN_EXPECTED_UNIVERSE_SIZE,
    max_expected_size: int = _MAX_EXPECTED_UNIVERSE_SIZE,
) -> list[SP500UniverseMember]:
    """从维基百科抓取当前 S&P 500 成分股列表, 逐条校验后返回。

    Args:
        timeout: 请求维基百科页面的超时时间 (秒)。
        min_expected_size: 校验通过的成分股数量下限, 用于识别页面结构异常。
        max_expected_size: 校验通过的成分股数量上限, 用于识别页面结构异常。

    Returns:
        list[SP500UniverseMember]: 校验通过的成分股列表。

    Raises:
        WikiFetchError: 请求失败、表格解析失败, 或解析出的列表为空。
    """
    try:
        resp = requests.get(
            _WIKI_URL,
            headers = {"User-Agent": _BROWSER_UA},
            timeout = timeout,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise WikiFetchError(f"维基百科请求失败: -{exc}") from exc

    try:
        table = pd.read_html(StringIO(resp.text), converters={"CIK": str})[0]
    except (ValueError, IndexError) as exc:
        raise WikiFetchError(f"页面解析失败, 可能是页面结构改变: {exc}") from exc
    
    required_columns = {"Symbol", "Security", "CIK"}
    missing_columns = required_columns - set(table.columns)
    if missing_columns:
        raise WikiFetchError(
            f"页面缺少必要字段: {sorted(missing_columns)}"     
        )

    universe: list[SP500UniverseMember] = []

    for row_number, (_, row) in enumerate(table.iterrows()):
        try:
            universe.append(
                SP500UniverseMember(
                    ticker=row["Symbol"],
                    company_name=row["Security"],
                    cik=row["CIK"]
                )
            )

        except ValidationError as exc:
            raise WikiFetchError(
                f"第 {row_number} 行校验失败，拒绝使用不完整快照: "
                f"{row.to_dict()}"
            ) from exc


    if not universe:
        raise WikiFetchError("解析出的成分股列表为空, 页面结构可能变化")
    
    if not (
        min_expected_size
        <= len(universe)
        <= max_expected_size
    ):
        raise WikiFetchError(
            f"成分股数量异常: {len(universe)},"
            f"预期范围 {min_expected_size}"
            f"~{max_expected_size}"
        )

    logger.info(f"成功抓取并且校验 {len(universe)} 条 S&P 成分股")

    return universe


def load_cached_universe(*, path: Path | str = "data/sp500_ticker.csv") -> pd.DataFrame:
    """读取本地 universe CSV, 同时保留 CIK 的前导零。

    Args:
        path: universe 缓存 CSV 的路径。默认 "data/sp500_ticker.csv" ——
            相对路径以调用方当前工作目录 (通常就是调用方项目根目录) 为起点。
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(
            f"{path_obj} 不存在, 请先生成缓存"
        )

    universe = pd.read_csv(path_obj, dtype={"cik": str})
    universe["cik"] = universe["cik"].str.zfill(10)
    return universe


def validate_cik_against_sec(universe: pd.DataFrame, *, timeout: float = 30) -> set[str]:
    """用 SEC 官方注册库手动交叉检查 universe 中的 CIK。

    Args:
        universe: 待校验的 universe DataFrame, 需包含 cik 列。
        timeout: 请求 SEC CIK 注册库的超时时间 (秒)。
    """
    logger.info("正在拉取 SEC 官方 CIK 注册库做交叉校验 ...")
    try:
        response = requests.get(
            _SEC_CIK_URL,
            headers=_SEC_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise EdgarFetchError(f"SEC CIK 注册库请求失败: {exc}") from exc

    sec_valid_ciks = {
        str(value["cik_str"]).zfill(10)
        for value in response.json().values()
    }

    wiki_ciks = set(universe["cik"])
    invalid = wiki_ciks - sec_valid_ciks

    if invalid:
        logger.warning(f"以下 CIK 在 SEC 官方注册库里查不到: {sorted(invalid)}")
    else:
        logger.success(f"校验通过: {len(wiki_ciks)} 个 CIK 全部能查到")
    return invalid
