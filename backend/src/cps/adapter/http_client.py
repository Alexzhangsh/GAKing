# @ai-generated
"""
CPS 渠道统一请求工具
封装 httpx 异步请求，内置超时、异常捕获、日志埋点
所有三方渠道 HTTP 请求统一走此工具
"""
import asyncio
import logging
import time
from typing import Any, Dict, Optional

import httpx

from src.common.log_util import SensitiveDataMasker
from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType

logger = logging.getLogger("cps.http")

DEFAULT_TIMEOUT = 15.0
MAX_RETRY = 3
RETRY_DELAY = 1.0


async def post_json(
    url: str,
    data: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    retry: int = MAX_RETRY,
    channel_name: str = "",
    logger_tag: str = "",
) -> Dict[str, Any]:
    """统一 POST JSON 请求工具

    Args:
        url: 请求 URL
        data: 请求体（JSON）
        headers: 自定义请求头
        timeout: 超时时间（秒）
        retry: 重试次数
        channel_name: 渠道名称（用于日志标记）
        logger_tag: 日志标签
    Returns:
        解析后的 JSON 响应字典
    Raises:
        CpsChannelException: 请求异常 / 超时 / 解析失败
    """
    tag = f"[{channel_name}]" if channel_name else ""
    tag += f"[{logger_tag}]" if logger_tag else ""

    masked_data = SensitiveDataMasker.mask_dict(data) if data else {}
    logger.info(f"{tag} POST {url} | params={masked_data}")

    last_error: Optional[Exception] = None
    for attempt in range(1, retry + 1):
        try:
            start = time.time()
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
            ) as client:
                response = await client.post(url, json=data, headers=headers or {})
            elapsed = time.time() - start
            logger.info(
                f"{tag} Response status={response.status_code} "
                f"elapsed={elapsed:.3f}s"
            )

            if response.status_code == 429:
                raise CpsChannelException(
                    error_type=CpsErrorType.RATE_LIMITED,
                    message="渠道接口限流（HTTP 429）",
                    channel_name=channel_name,
                    status_code=response.status_code,
                    raw_response=response.text[:500],
                )

            response.raise_for_status()
            result = response.json()
            return result

        except httpx.TimeoutException as e:
            last_error = e
            logger.warning(f"{tag} Request timeout (attempt {attempt}/{retry}): {e}")
        except httpx.ConnectError as e:
            last_error = e
            logger.warning(f"{tag} Connection error (attempt {attempt}/{retry}): {e}")
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.error(
                f"{tag} HTTP error {e.response.status_code} "
                f"(attempt {attempt}/{retry}): {e}"
            )
            if e.response.status_code in (401, 403):
                raise CpsChannelException(
                    error_type=CpsErrorType.INVALID_API_KEY,
                    message=f"API 密钥无效（HTTP {e.response.status_code}）",
                    channel_name=channel_name,
                    status_code=e.response.status_code,
                    raw_response=e.response.text[:500],
                ) from e
        except httpx.HTTPError as e:
            last_error = e
            logger.error(f"{tag} HTTP error (attempt {attempt}/{retry}): {e}")
        except ValueError as e:
            logger.error(f"{tag} JSON parse error: {e}")
            raise CpsChannelException(
                error_type=CpsErrorType.PARSE_ERROR,
                message=f"响应 JSON 解析失败: {e}",
                channel_name=channel_name,
                raw_response=str(last_error)[:500] if last_error else None,
            ) from e

        if attempt < retry:
            await asyncio.sleep(RETRY_DELAY * attempt)

    raise CpsChannelException(
        error_type=CpsErrorType.REQUEST_TIMEOUT,
        message=f"请求失败，已重试 {retry} 次: {last_error}",
        channel_name=channel_name,
    )


async def get(
    url: str,
    params: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    retry: int = MAX_RETRY,
    channel_name: str = "",
    logger_tag: str = "",
) -> Dict[str, Any]:
    """统一 GET 请求工具（查询参数形式）

    Args:
        url: 请求 URL
        params: 查询参数
        headers: 自定义请求头
        timeout: 超时时间（秒）
        retry: 重试次数
        channel_name: 渠道名称（用于日志标记）
        logger_tag: 日志标签
    Returns:
        解析后的 JSON 响应字典
    Raises:
        CpsChannelException: 请求异常 / 超时 / 解析失败
    """
    tag = f"[{channel_name}]" if channel_name else ""
    tag += f"[{logger_tag}]" if logger_tag else ""

    masked_params = SensitiveDataMasker.mask_dict(params) if params else {}
    logger.info(f"{tag} GET {url} | params={masked_params}")

    last_error: Optional[Exception] = None
    for attempt in range(1, retry + 1):
        try:
            start = time.time()
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
            ) as client:
                response = await client.get(url, params=params, headers=headers or {})
            elapsed = time.time() - start
            logger.info(
                f"{tag} Response status={response.status_code} "
                f"elapsed={elapsed:.3f}s"
            )

            if response.status_code == 429:
                raise CpsChannelException(
                    error_type=CpsErrorType.RATE_LIMITED,
                    message="渠道接口限流（HTTP 429）",
                    channel_name=channel_name,
                    status_code=response.status_code,
                    raw_response=response.text[:500],
                )

            response.raise_for_status()
            result = response.json()
            return result

        except httpx.TimeoutException as e:
            last_error = e
            logger.warning(f"{tag} Request timeout (attempt {attempt}/{retry}): {e}")
        except httpx.ConnectError as e:
            last_error = e
            logger.warning(f"{tag} Connection error (attempt {attempt}/{retry}): {e}")
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.error(
                f"{tag} HTTP error {e.response.status_code} "
                f"(attempt {attempt}/{retry}): {e}"
            )
            if e.response.status_code in (401, 403):
                raise CpsChannelException(
                    error_type=CpsErrorType.INVALID_API_KEY,
                    message=f"API 密钥无效（HTTP {e.response.status_code}）",
                    channel_name=channel_name,
                    status_code=e.response.status_code,
                    raw_response=e.response.text[:500],
                ) from e
        except httpx.HTTPError as e:
            last_error = e
            logger.error(f"{tag} HTTP error (attempt {attempt}/{retry}): {e}")
        except ValueError as e:
            logger.error(f"{tag} JSON parse error: {e}")
            raise CpsChannelException(
                error_type=CpsErrorType.PARSE_ERROR,
                message=f"响应 JSON 解析失败: {e}",
                channel_name=channel_name,
                raw_response=str(last_error)[:500] if last_error else None,
            ) from e

        if attempt < retry:
            await asyncio.sleep(RETRY_DELAY * attempt)

    raise CpsChannelException(
        error_type=CpsErrorType.REQUEST_TIMEOUT,
        message=f"请求失败，已重试 {retry} 次: {last_error}",
        channel_name=channel_name,
    )
