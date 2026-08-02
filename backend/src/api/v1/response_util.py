# @ai-generated
"""
统一响应封装 & 请求ID工具
提供全局响应体构造、异常捕获、请求ID埋点
"""
import logging
import uuid
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from src.schemas.cps import ApiResponse

logger = logging.getLogger("api.common")


def get_request_id(request: Request) -> str:
    """从请求头获取或生成请求ID"""
    request_id = request.headers.get("X-Request-Id")
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:16]}"
    return request_id


def success_response(
    data: Any = None,
    msg: str = "success",
    request_id: Optional[str] = None,
) -> JSONResponse:
    """构造成功响应"""
    body = ApiResponse(code=200, msg=msg, data=data, request_id=request_id)
    return JSONResponse(status_code=200, content=body.model_dump())


def error_response(
    code: int = 400,
    msg: str = "error",
    data: Any = None,
    request_id: Optional[str] = None,
    http_status: Optional[int] = None,
) -> JSONResponse:
    """构造错误响应"""
    body = ApiResponse(code=code, msg=msg, data=data, request_id=request_id)
    http_code = http_status if http_status is not None else (200 if code < 500 else 500)
    return JSONResponse(status_code=http_code, content=body.model_dump())


def handle_service_exception(
    exc: Exception,
    request_id: str,
) -> JSONResponse:
    """统一业务异常处理

    ValueError → 400 参数/业务校验错误
    其他异常 → 500 服务异常
    """
    if isinstance(exc, ValueError):
        logger.warning("[request_id=%s] 业务校验失败: %s", request_id, exc)
        return error_response(code=400, msg=str(exc), request_id=request_id)

    logger.error("[request_id=%s] 服务异常: %s", request_id, exc, exc_info=True)
    return error_response(code=500, msg="内部服务异常", request_id=request_id)
