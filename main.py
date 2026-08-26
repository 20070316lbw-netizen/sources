"""对所有已实现的代码模块进行全流程测试运行。"""

from __future__ import annotations

import traceback
from pathlib import Path
import pandas as pd
from loguru import logger

from sources.config import DATA_DIR, SP500_CACHE_PATH, PROJECT_ROOT
from sources.error import (
    DataFetchError,
    EdgarFetchError,
    PgsqlError,
    QuantLabError,
    SchemaInitializationError,
    UniverseLoadError,
    WikiFetchError,
    YahooFetchError,
    YahooLoadError,
)
from sources.universe.fetch import (
    SP500UniverseMember,
    fetch_sp500_universe,
    load_cached_universe,
    validate_cik_against_sec,
)
from sources.yahoo.fetch import fetch_prices, save_prices
from sources.yahoo.load import load_prices


def test_error_hierarchy() -> None:
    """测试异常体系继承关系"""
    logger.info("=== [1/4] 测试自定义异常体系 ===")
    assert issubclass(DataFetchError, QuantLabError)
    assert issubclass(PgsqlError, QuantLabError)
    assert issubclass(WikiFetchError, DataFetchError)
    assert issubclass(YahooFetchError, DataFetchError)
    assert issubclass(EdgarFetchError, DataFetchError)
    assert issubclass(SchemaInitializationError, PgsqlError)
    assert issubclass(UniverseLoadError, PgsqlError)
    assert issubclass(YahooLoadError, PgsqlError)

    edgar_err = EdgarFetchError(cik="0000320193", status_code=404)
    assert "0000320193" in str(edgar_err)
    logger.success("异常体系测试通过！\n")


def test_universe_member_model() -> None:
    """测试 SP500UniverseMember Pydantic 模型的数据清洗与校验规则"""
    logger.info("=== [2/4] 测试 SP500UniverseMember 数据模型 ===")
    
    # 正常数据及自动清洗测试 (如 ticker '.' 转 '-', CIK 补 0)
    m1 = SP500UniverseMember(ticker="brk.b", company_name="Berkshire Hathaway", cik="1067983")
    assert m1.ticker == "BRK-B", f"Ticker 格式化错误: {m1.ticker}"
    assert m1.cik == "0001067983", f"CIK 补零错误: {m1.cik}"
    logger.success(f"模型自动补零与 Ticker 规范化测试通过: {m1}")

    # 异常数据拦截测试
    try:
        SP500UniverseMember(ticker="AAPL", company_name="Apple", cik="invalid_cik")
        logger.error("未能拦截非法 CIK！")
    except Exception as e:
        logger.success(f"成功拦截非法 CIK: {e}")
    logger.success("SP500UniverseMember 模型测试通过！\n")


def test_universe_pipeline() -> pd.DataFrame:
    """测试 S&P 500 Universe 抓取、缓存保存、缓存读取与 SEC 交叉验证"""
    logger.info("=== [3/4] 测试 Universe 模块 (抓取、缓存与 SEC 校验) ===")

    # 1. 抓取 Wikipedia
    logger.info("正在从 Wikipedia 抓取 S&P 500 列表...")
    members = fetch_sp500_universe()
    logger.info(f"抓取到 {len(members)} 条记录，首条数据: {members[0]}")

    # 2. 转换为 DataFrame 并保存到 SP500_CACHE_PATH
    df_universe = pd.DataFrame([m.model_dump() for m in members])
    df_universe.to_csv(SP500_CACHE_PATH, index=False)
    logger.success(f"已缓存至 {SP500_CACHE_PATH}")

    # 3. 测试 load_cached_universe
    loaded_df = load_cached_universe()
    assert len(loaded_df) == len(df_universe), "读取缓存行数不一致"
    # 确认 CIK 前导零保留
    sample_cik = loaded_df["cik"].iloc[0]
    assert len(sample_cik) == 10 and sample_cik.isdigit(), f"CIK 格式异常: {sample_cik}"
    logger.success(f"缓存读取成功，共 {len(loaded_df)} 行数据")

    # 4. 测试 validate_cik_against_sec
    logger.info("正在进行 SEC 官方 CIK 交叉验证...")
    invalid_ciks = validate_cik_against_sec(loaded_df)
    if invalid_ciks:
        logger.warning(f"SEC 校验发现 {len(invalid_ciks)} 个不匹配的 CIK: {sorted(invalid_ciks)}")
    else:
        logger.success("SEC 校验全部通过！")

    logger.success("Universe 模块测试完成！\n")
    return loaded_df


def test_yahoo_pipeline(sample_tickers: list[str]) -> None:
    """测试 Yahoo 价格数据抓取、parquet 保存与加载"""
    logger.info("=== [4/4] 测试 Yahoo 模块 (行情抓取、Parquet 存储与读取) ===")
    
    start_date = "2024-01-02"
    end_date = "2024-01-10"
    parquet_path = DATA_DIR / "test_prices.parquet"

    # 1. 抓取价格
    logger.info(f"正在抓取 {sample_tickers} 从 {start_date} 到 {end_date} 的行情数据...")
    df_prices = fetch_prices(symbol=sample_tickers, start=start_date, end=end_date)
    logger.info(f"获取到的价格数据形状: {df_prices.shape}")
    logger.info(f"索引名: {df_prices.index.names}, 列名: {list(df_prices.columns)}")
    print(df_prices.head())

    # 2. 保存至 Parquet (测试 Path 对象与 str 字符串入参兼容性)
    save_prices(df_prices, path=str(parquet_path))
    assert parquet_path.exists(), "Parquet 文件未能成功保存"
    logger.success(f"价格数据成功保存至 (通过 str 路径) {parquet_path}")

    # 3. 读取 Parquet (测试 Path 对象与 str 字符串入参兼容性)
    loaded_prices = load_prices(path=str(parquet_path))
    assert loaded_prices.shape == df_prices.shape, "加载的数据形状与保存时不一致"
    logger.success(f"价格数据成功加载验证 (通过 str 路径)，MultiIndex: {loaded_prices.index.names}")

    # 4. 测试读取不存在文件的错误处理 (传入 str 路径)
    fake_path_str = str(DATA_DIR / "non_existent_file.parquet")
    try:
        load_prices(path=fake_path_str)
        logger.error("未能触发 FileNotFoundError 异常")
    except FileNotFoundError:
        logger.success("load_prices 文件不存在时正确抛出 FileNotFoundError (str 路径测试通过)")

    # 5. 测试异常行情抓取抛出 YahooFetchError
    try:
        fetch_prices(symbol=["INVALID_TICKER_XYZ_123"], start="2024-01-01", end="2024-01-02")
        logger.warning("抓取无效标的未抛出异常，可能返回了空结构")
    except YahooFetchError as e:
        logger.success(f"抓取无效数据正确抛出 YahooFetchError: {e}")
    except Exception as e:
        logger.error(f"抛出的异常不是 YahooFetchError: {type(e)}: {e}")

    logger.success("Yahoo 模块测试完成！\n")


def main() -> None:
    logger.info("================ 开始全模块测试 ================")
    
    # 1. 测试异常类
    try:
        test_error_hierarchy()
    except Exception:
        logger.error(f"异常体系测试失败:\n{traceback.format_exc()}")

    # 2. 测试 Pydantic 模型
    try:
        test_universe_member_model()
    except Exception:
        logger.error(f"Universe 模型测试失败:\n{traceback.format_exc()}")

    # 3. 测试 Universe 数据流
    universe_df = None
    try:
        universe_df = test_universe_pipeline()
    except Exception:
        logger.error(f"Universe 流程测试失败:\n{traceback.format_exc()}")

    # 4. 测试 Yahoo 行情数据流
    try:
        sample_tickers = ["AAPL", "MSFT", "NVDA"]
        if universe_df is not None and not universe_df.empty:
            sample_tickers = universe_df["ticker"].head(3).tolist()
        test_yahoo_pipeline(sample_tickers)
    except Exception:
        logger.error(f"Yahoo 流程测试失败:\n{traceback.format_exc()}")

    logger.info("================ 测试流程结束 ================")


if __name__ == "__main__":
    main()



