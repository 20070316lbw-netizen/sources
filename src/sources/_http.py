"""内部共享 HTTP 工具。

统一 User-Agent、超时与一个保守的重试策略, 供包内直接用 requests 抓取网页/接口
的数据源(目前是 constituents.py)使用。

注意: yfinance / edgartools 这类第三方库自己管理 HTTP 会话和重试, 不经过这里;
这个模块只服务于我们自己直接发起的 requests 调用。
"""
from __future__ import annotations

import time
from typing import Any

import requests
from loguru import logger

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def get_with_retry(
    url: str,
    *,
    headers: dict | None = None,
    timeout: int = 10,
    max_retries: int = 3,
    backoff: float = 1.5,
    **kwargs: Any,
) -> requests.Response:
    """带重试的 GET 请求。

    只对"确认是瞬时性"的失败重试: 连接/超时错误, 或明确的 5xx 响应。
    4xx(以及任何拿不到状态码的 HTTPError)被当作确定性错误, 立即抛出,
    这样调用方能第一时间定位问题, 而不是白等几次重试。

    Args:
        url: 请求地址。
        headers: 额外/覆盖的请求头, 会与 DEFAULT_HEADERS 合并。
        timeout: 单次请求超时秒数。
        max_retries: 最多尝试次数(含第一次)。
        backoff: 指数退避底数, 第 n 次重试等待 backoff**n 秒。
        **kwargs: 透传给 requests.get 的其他参数。

    Returns:
        成功的 requests.Response。

    Raises:
        requests.RequestException: 重试耗尽后仍失败, 或遇到不可重试的错误。
    """
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=merged_headers, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is None or status < 500:
                raise  # 4xx 或状态码未知: 不重试, 直接抛出
            last_exc = e
        except requests.RequestException as e:
            last_exc = e

        if attempt < max_retries:
            sleep_s = backoff**attempt
            logger.warning(
                f"GET {url} 第 {attempt}/{max_retries} 次失败: {last_exc}, "
                f"{sleep_s:.1f}s 后重试"
            )
            time.sleep(sleep_s)

    assert last_exc is not None
    raise last_exc
