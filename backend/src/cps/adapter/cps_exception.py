# @ai-generated
"""
CPS 渠道统一异常封装
区分渠道限流、密钥失效、接口超时、无订单、商品不存在等错误类型
"""
from enum import Enum
from typing import Optional, Any


class CpsErrorType(str, Enum):
    """CPS 渠道错误类型"""

    RATE_LIMITED = "RATE_LIMITED"
    INVALID_API_KEY = "INVALID_API_KEY"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    NO_ORDER_FOUND = "NO_ORDER_FOUND"
    GOODS_NOT_FOUND = "GOODS_NOT_FOUND"
    API_ERROR = "API_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"


class CpsChannelException(Exception):
    """CPS 渠道统一异常

    包含错误类型、渠道名称、原始响应等信息
    全局异常拦截可识别 error_type 字段做差异化处理
    """

    def __init__(
        self,
        error_type: CpsErrorType,
        message: str,
        channel_name: str = "",
        status_code: Optional[int] = None,
        raw_response: Optional[Any] = None,
    ):
        self.error_type = error_type
        self.channel_name = channel_name
        self.status_code = status_code
        self.raw_response = raw_response
        super().__init__(message)

    def __str__(self) -> str:
        parts = [f"[{self.error_type.value}]", f"[{self.channel_name}]"]
        if self.status_code is not None:
            parts.append(f"[HTTP {self.status_code}]")
        parts.append(str(self.args[0]))
        return " ".join(parts)
