# @ai-generated
"""
微信支付V3异常定义与错误码映射（B10 新建）

职责：
1. 定义微信支付V3统一异常类 WechatPayError
2. 映射微信支付V3 API 错误码到业务异常码
3. 复用全局 BizException 体系（code + msg + data）

错误码规划（B10 专属，不与 B01-B09 冲突）：
  20xxx 微信支付V3异常
    20001 证书加载失败
    20002 签名计算失败
    20003 验签失败
    20004 API 请求失败（HTTP 非 2xx）
    20005 API 响应解析失败
    20006 重复转账单号（幂等拦截）
    20007 转账超时
    20008 余额不足
    20009 参数校验失败
    20010 熔断降级
    20011 回调验签失败
    20012 回调解密失败
    20013 微信侧业务错误（如姓名校验失败、收款限额等）
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.schemas.cps_goods import BizException

logger = logging.getLogger("common.wechat_pay.exceptions")


# ── 业务异常码常量 ──────────────────────────────────────

WECHAT_PAY_ERROR_CERT_LOAD = 20001
WECHAT_PAY_ERROR_SIGN = 20002
WECHAT_PAY_ERROR_VERIFY = 20003
WECHAT_PAY_ERROR_HTTP = 20004
WECHAT_PAY_ERROR_PARSE = 20005
WECHAT_PAY_ERROR_DUPLICATE = 20006
WECHAT_PAY_ERROR_TIMEOUT = 20007
WECHAT_PAY_ERROR_INSUFFICIENT_BALANCE = 20008
WECHAT_PAY_ERROR_PARAM = 20009
WECHAT_PAY_ERROR_CIRCUIT_BREAKER = 20010
WECHAT_PAY_ERROR_CALLBACK_VERIFY = 20011
WECHAT_PAY_ERROR_CALLBACK_DECRYPT = 20012
WECHAT_PAY_ERROR_BIZ = 20013


# ── 微信支付V3 API 错误码 → 业务异常码映射表 ────────────
# 来源：微信支付V3官方文档 https://pay.weixin.qq.com/wiki/doc/apiv3/wxpay/pages/transfer.vue

WECHAT_API_ERROR_MAP: Dict[str, int] = {
    # 参数类错误
    "PARAM_ERROR": WECHAT_PAY_ERROR_PARAM,
    "INVALID_REQUEST": WECHAT_PAY_ERROR_PARAM,
    "NOT_ENOUGH": WECHAT_PAY_ERROR_INSUFFICIENT_BALANCE,
    # 签名/证书类错误
    "SIGN_ERROR": WECHAT_PAY_ERROR_SIGN,
    "CERT_ERROR": WECHAT_PAY_ERROR_CERT_LOAD,
    # 重复请求
    "INVALID_REQ_NO": WECHAT_PAY_ERROR_DUPLICATE,
    # 账户类错误
    "ACCOUNT_ERROR": WECHAT_PAY_ERROR_BIZ,
    "EXCEED_QUOTA_LIMIT": WECHAT_PAY_ERROR_BIZ,
    "NAME_NOT_MATCH": WECHAT_PAY_ERROR_BIZ,
    "V2_ACCOUNT_SIMPLE_VERIFY": WECHAT_PAY_ERROR_BIZ,
    "USER_NOT_ENOUGH": WECHAT_PAY_ERROR_INSUFFICIENT_BALANCE,
    # 系统类错误
    "SYSTEM_ERROR": WECHAT_PAY_ERROR_HTTP,
    "BIZ_ERROR": WECHAT_PAY_ERROR_BIZ,
}


class WechatPayError(BizException):
    """微信支付V3统一异常（继承 BizException，兼容全局异常处理）"""

    def __init__(
        self,
        code: int,
        msg: str,
        data: Optional[Any] = None,
        *,
        wechat_code: Optional[str] = None,
        http_status: Optional[int] = None,
    ) -> None:
        super().__init__(code, msg, data)
        self.wechat_code = wechat_code
        self.http_status = http_status


def map_wechat_api_error(
    wechat_code: str,
    wechat_message: str,
    *,
    http_status: Optional[int] = None,
    raw_response: Optional[Dict] = None,
) -> WechatPayError:
    """将微信支付V3 API 错误码映射为 WechatPayError

    Args:
        wechat_code: 微信返回的 code（如 SIGN_ERROR / NOT_ENOUGH）
        wechat_message: 微信返回的 message
        http_status: HTTP 状态码
        raw_response: 原始响应 dict
    Returns:
        WechatPayError 实例
    """
    biz_code = WECHAT_API_ERROR_MAP.get(wechat_code, WECHAT_PAY_ERROR_BIZ)
    error = WechatPayError(
        code=biz_code,
        msg=f"微信支付错误: {wechat_code} - {wechat_message}",
        data={"wechat_code": wechat_code, "raw": raw_response},
        wechat_code=wechat_code,
        http_status=http_status,
    )
    logger.warning(
        "[wechat_pay] API错误映射 wechat_code=%s → biz_code=%s msg=%s",
        wechat_code,
        biz_code,
        wechat_message,
    )
    return error


def raise_from_http_error(
    status_code: int,
    response_body: Optional[Dict[str, Any]],
) -> None:
    """根据 HTTP 错误状态码和响应体抛出对应异常

    Args:
        status_code: HTTP 状态码
        response_body: 解析后的响应 JSON dict
    Raises:
        WechatPayError: 始终抛出
    """
    if response_body and "code" in response_body:
        wechat_code = response_body.get("code", "")
        wechat_message = response_body.get("message", "未知错误")
        raise map_wechat_api_error(
            wechat_code,
            wechat_message,
            http_status=status_code,
            raw_response=response_body,
        )

    # 无 code 字段的 HTTP 错误
    if status_code == 401:
        raise WechatPayError(
            code=WECHAT_PAY_ERROR_SIGN,
            msg="微信支付认证失败（HTTP 401），请检查证书与签名",
            http_status=status_code,
        )
    if status_code == 429:
        raise WechatPayError(
            code=WECHAT_PAY_ERROR_TIMEOUT,
            msg="微信支付接口限流（HTTP 429），请稍后重试",
            http_status=status_code,
        )
    if status_code >= 500:
        raise WechatPayError(
            code=WECHAT_PAY_ERROR_HTTP,
            msg=f"微信支付服务端错误（HTTP {status_code}）",
            data={"status_code": status_code, "body": response_body},
            http_status=status_code,
        )

    raise WechatPayError(
        code=WECHAT_PAY_ERROR_HTTP,
        msg=f"微信支付请求失败（HTTP {status_code}）",
        data={"status_code": status_code, "body": response_body},
        http_status=status_code,
    )
