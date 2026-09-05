# @ai-generated
"""
微信支付V3 HTTP 客户端（B10 新建）

职责：
1. 封装 httpx 异步请求，自动注入微信支付V3认证头
2. 内置重试机制（超时/5xx 退避重试，4xx 不重试）
3. 接入 B04 CircuitBreaker 熔断降级（channel_code=wechat_pay）
4. 统一日志埋点 + 异常码映射

设计要点：
1. 不复用 CPS 的 http_client.py（那是给 CPS 渠道用的，签名/异常体系不同）
2. 复用 B04 CircuitBreaker 类（不修改它），传入独立 channel_code
3. 重试策略：超时/连接错误重试，HTTP 4xx（业务错误）不重试直接抛
4. 日志：记录 method/url/状态码/耗时，敏感数据脱敏

约束：不修改 B01-B09 基线代码
"""
import asyncio
import logging
import time
from typing import Any, Dict, Optional

import httpx

from src.common.wechat_pay.constants import (
    WECHAT_PAY_BASE_URL,
    WECHAT_PAY_BREAKER_CHANNEL,
    WECHAT_PAY_MAX_RETRY,
    WECHAT_PAY_REQUEST_TIMEOUT,
    WECHAT_PAY_RETRY_BASE_DELAY,
)
from src.common.wechat_pay.exceptions import (
    WECHAT_PAY_ERROR_CIRCUIT_BREAKER,
    WECHAT_PAY_ERROR_PARSE,
    WECHAT_PAY_ERROR_TIMEOUT,
    WechatPayError,
    raise_from_http_error,
)
from src.common.wechat_pay.signer import WechatPaySigner
from src.cps.circuit_breaker import CircuitBreaker

logger = logging.getLogger("common.wechat_pay.client")


class WechatPayClient:
    """微信支付V3 HTTP 客户端

    封装 httpx async + 签名注入 + 重试 + 熔断
    线程安全：每个请求独立 httpx.AsyncClient（无连接池泄漏风险）
    """

    def __init__(
        self,
        signer: WechatPaySigner,
        *,
        circuit_breaker: Optional[CircuitBreaker] = None,
        max_retry: int = WECHAT_PAY_MAX_RETRY,
        timeout: float = WECHAT_PAY_REQUEST_TIMEOUT,
    ) -> None:
        """初始化客户端

        Args:
            signer: 微信支付签名器（含商户私钥 + 证书序列号）
            circuit_breaker: 熔断器实例（None 则新建默认实例）
            max_retry: 最大重试次数
            timeout: 请求超时（秒）
        """
        self.signer = signer
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.max_retry = max_retry
        self.timeout = timeout

    # ── POST 请求 ───────────────────────────────────────

    async def post(
        self,
        path: str,
        data: Dict[str, Any],
        *,
        retry: Optional[int] = None,
    ) -> Dict[str, Any]:
        """发送 POST 请求（自动签名 + 重试 + 熔断）

        Args:
            path: API 路径（如 /v3/transfer/batches）
            data: 请求体 dict
            retry: 重试次数覆盖（None 用默认）
        Returns:
            响应 JSON dict
        Raises:
            WechatPayError: 熔断/超时/HTTP错误/解析失败
        """
        import json

        body_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return await self._request("POST", path, body_str=body_str, retry=retry)

    # ── GET 请求 ────────────────────────────────────────

    async def get(
        self,
        path: str,
        *,
        retry: Optional[int] = None,
    ) -> Dict[str, Any]:
        """发送 GET 请求（自动签名 + 重试 + 熔断）

        Args:
            path: API 路径（含 query string）
            retry: 重试次数覆盖
        Returns:
            响应 JSON dict
        Raises:
            WechatPayError: 熔断/超时/HTTP错误/解析失败
        """
        return await self._request("GET", path, body_str="", retry=retry)

    # ── 核心请求逻辑 ────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        body_str: str,
        retry: Optional[int],
    ) -> Dict[str, Any]:
        """统一请求逻辑（签名 → 熔断检查 → 重试 → 响应解析）"""
        max_retry = retry if retry is not None else self.max_retry

        # 1. 熔断检查
        allowed = await self.circuit_breaker.allow_request(WECHAT_PAY_BREAKER_CHANNEL)
        if not allowed:
            logger.warning(
                "[wechat_pay_client] 熔断中，请求被拒绝 method=%s path=%s",
                method,
                path,
            )
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CIRCUIT_BREAKER,
                msg="微信支付熔断降级中，请稍后重试",
            )

        # 2. 生成认证头
        auth_header = self.signer.build_authorization_header(method, path, body_str)
        url = f"{WECHAT_PAY_BASE_URL}{path}"
        headers = {
            "Authorization": auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # 3. 重试循环
        last_error: Optional[Exception] = None
        for attempt in range(1, max_retry + 2):  # +1 因为首次不算重试
            try:
                start = time.time()
                result = await self._do_http_request(method, url, headers, body_str)
                elapsed = time.time() - start
                logger.info(
                    "[wechat_pay_client] 请求成功 method=%s path=%s "
                    "elapsed=%.3fs attempt=%d/%d",
                    method,
                    path,
                    elapsed,
                    attempt,
                    max_retry + 1,
                )
                # 记录熔断成功
                await self.circuit_breaker.record_success(WECHAT_PAY_BREAKER_CHANNEL)
                return result

            except WechatPayError as e:
                last_error = e
                # 业务错误（4xx）不重试
                if e.http_status and 400 <= e.http_status < 500:
                    logger.warning(
                        "[wechat_pay_client] 业务错误不重试 method=%s path=%s "
                        "status=%d code=%s",
                        method,
                        path,
                        e.http_status,
                        e.wechat_code,
                    )
                    await self.circuit_breaker.record_failure(
                        WECHAT_PAY_BREAKER_CHANNEL
                    )
                    raise
                # 超时/5xx 可重试
                if attempt <= max_retry:
                    delay = WECHAT_PAY_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "[wechat_pay_client] 请求失败重试 method=%s path=%s "
                        "attempt=%d/%d delay=%.1fs err=%s",
                        method,
                        path,
                        attempt,
                        max_retry + 1,
                        delay,
                        e.msg,
                    )
                    await asyncio.sleep(delay)
                else:
                    await self.circuit_breaker.record_failure(
                        WECHAT_PAY_BREAKER_CHANNEL
                    )
                    raise

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "[wechat_pay_client] 请求超时 method=%s path=%s "
                    "attempt=%d/%d: %s",
                    method,
                    path,
                    attempt,
                    max_retry + 1,
                    e,
                )
                if attempt <= max_retry:
                    await asyncio.sleep(WECHAT_PAY_RETRY_BASE_DELAY * attempt)
                else:
                    await self.circuit_breaker.record_failure(
                        WECHAT_PAY_BREAKER_CHANNEL
                    )
                    raise WechatPayError(
                        code=WECHAT_PAY_ERROR_TIMEOUT,
                        msg=f"微信支付请求超时，已重试 {max_retry} 次: {e}",
                    )

            except httpx.ConnectError as e:
                last_error = e
                logger.warning(
                    "[wechat_pay_client] 连接失败 method=%s path=%s "
                    "attempt=%d/%d: %s",
                    method,
                    path,
                    attempt,
                    max_retry + 1,
                    e,
                )
                if attempt <= max_retry:
                    await asyncio.sleep(WECHAT_PAY_RETRY_BASE_DELAY * attempt)
                else:
                    await self.circuit_breaker.record_failure(
                        WECHAT_PAY_BREAKER_CHANNEL
                    )
                    raise WechatPayError(
                        code=WECHAT_PAY_ERROR_TIMEOUT,
                        msg=f"微信支付连接失败，已重试 {max_retry} 次: {e}",
                    )

        # 兜底：不应执行到此处
        await self.circuit_breaker.record_failure(WECHAT_PAY_BREAKER_CHANNEL)
        raise WechatPayError(
            code=WECHAT_PAY_ERROR_TIMEOUT,
            msg=f"微信支付请求失败: {last_error}",
        )

    async def _do_http_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body_str: str,
    ) -> Dict[str, Any]:
        """执行单次 HTTP 请求并解析响应

        Args:
            method: HTTP 方法
            url: 完整 URL
            headers: 请求头（含 Authorization）
            body_str: 请求体字符串
        Returns:
            响应 JSON dict
        Raises:
            WechatPayError: HTTP 错误 / 解析失败
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=False,
        ) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers)
            else:
                response = await client.post(url, headers=headers, content=body_str)

        # 解析响应体
        response_body: Optional[Dict[str, Any]] = None
        try:
            if response.text:
                response_body = response.json()
        except Exception as e:
            logger.error(
                "[wechat_pay_client] 响应JSON解析失败 status=%d body=%s: %s",
                response.status_code,
                response.text[:200],
                e,
            )
            if response.status_code >= 400:
                raise WechatPayError(
                    code=WECHAT_PAY_ERROR_HTTP,
                    msg=f"微信支付HTTP {response.status_code} 且响应解析失败",
                    http_status=response.status_code,
                )
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_PARSE,
                msg=f"微信支付响应JSON解析失败: {e}",
                data={"raw_text": response.text[:500]},
            )

        # HTTP 错误处理
        if response.status_code >= 400:
            raise_from_http_error(response.status_code, response_body)

        return response_body or {}
