"""SEC 接口的底层请求: 身份标识 + 全局限速 + 重试。

SEC 的公平访问规则: 每秒最多 10 次请求, User-Agent 必须带身份(名字 + 邮箱)。
超速会先收到 429, 持续超速会被临时封 IP。这里用一个进程级的最小间隔做限速,
保守地卡在每秒约 8 次; 重试交给 `_http.get_with_retry`(5xx / 429 退避重试)。
"""
from __future__ import annotations

import threading
import time
from typing import Any

from sources._http import get_with_retry, sec_identity_headers

MIN_INTERVAL = 0.125  # 秒; 1 / 0.125 = 8 次/秒, 低于 SEC 的 10 次/秒上限

_lock = threading.Lock()
_last_request = 0.0


def _throttle() -> None:
    """保证相邻两次请求的发起时间至少间隔 MIN_INTERVAL(线程安全)。"""
    global _last_request
    with _lock:
        wait = _last_request + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def sec_get_json(url: str, *, timeout: int = 30) -> Any:
    """GET 一个 sec.gov 的 JSON 接口, 返回解析后的对象。

    Raises:
        requests.RequestException: 重试耗尽或遇到不可重试的 4xx(如 404 不存在该 CIK)。
    """
    _throttle()
    resp = get_with_retry(
        url,
        headers=sec_identity_headers(),
        timeout=timeout,
        max_retries=4,
        backoff=2.0,
    )
    return resp.json()
