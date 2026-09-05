# @ai-generated
"""
统一异常处理器（B14 新建，不修改 B01-B13 基线）
注册具体异常类型的 handler，将 FastAPI 默认的 {"detail": ...} 转为标准 ApiResponse 格式
FastAPI 按异常类型精确匹配，优先于 main.py 既有的 @app.exception_handler(Exception) 兜底

注册异常类型：
  - HTTPException      → 401/403/404/422 等，code 与 HTTP 状态码对齐
  - RequestValidationError → 422 参数校验失败，data 含错误详情
  - ValueError         → 400 业务校验错误
  - PyJWTError         → 401 token 无效/过期
"""
import logging
from typing import Any, Dict

import jwt
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.v1.response_util import get_request_id
from src.schemas.cps import ApiResponse

logger = logging.getLogger("common.b14_exception_handlers")


def register_b14_exception_handlers(app: FastAPI) -> None:
    """注册 B14 统一异常处理器到 FastAPI app

    在 main.py 中间件注册后、include_router 前调用
    这些 handler 优先于 main.py 既有的 @app.exception_handler(Exception) 兜底
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTPException → 标准 ApiResponse 格式"""
        request_id = get_request_id(request)
        code = exc.status_code
        msg = str(exc.detail) if exc.detail else "请求错误"
        body = ApiResponse(code=code, msg=msg, data=None, request_id=request_id)
        return JSONResponse(status_code=code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """参数校验失败 → 422 标准 ApiResponse 格式"""
        request_id = get_request_id(request)
        errors = _format_validation_errors(exc.errors())
        body = ApiResponse(
            code=422,
            msg="参数校验失败",
            data=errors,
            request_id=request_id,
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """ValueError（业务校验） → 400 标准 ApiResponse 格式"""
        request_id = get_request_id(request)
        msg = str(exc) if str(exc) else "参数错误"
        logger.warning("[request_id=%s] 业务校验失败: %s", request_id, msg)
        body = ApiResponse(code=400, msg=msg, data=None, request_id=request_id)
        return JSONResponse(status_code=400, content=body.model_dump())

    @app.exception_handler(jwt.PyJWTError)
    async def jwt_error_handler(request: Request, exc: jwt.PyJWTError):
        """JWT 异常 → 401 标准 ApiResponse 格式"""
        request_id = get_request_id(request)
        body = ApiResponse(
            code=401,
            msg="登录已超时或 token 无效，请重新登录",
            data=None,
            request_id=request_id,
        )
        return JSONResponse(status_code=401, content=body.model_dump())


def _format_validation_errors(errors: list) -> list:
    """格式化 pydantic 校验错误，脱敏 loc/msg"""
    formatted = []
    for err in errors:
        loc = err.get("loc", [])
        msg = err.get("msg", "校验失败")
        formatted.append(
            {
                "field": ".".join(str(x) for x in loc if x != "body"),
                "message": msg,
                "type": err.get("type", ""),
            }
        )
    return formatted
