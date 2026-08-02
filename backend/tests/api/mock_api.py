# @ai-generated
import json
import os
import sys
import time
import hashlib
import hmac
from decimal import Decimal
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tests.helpers import (
    MOCK_DATA_DIR,
    PLATFORM_COMMISSION_RATE,
    USER_COMMISSION_RATE,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_SETTLED,
    TRANSFER_STATUS_PENDING,
    TRANSFER_STATUS_SUCCESS,
    compute_hmac_sha256,
    compute_commission_split,
    transform_cps_order_to_internal,
    decrypt_wxpay_resource,
    build_internal_order_from_wxpay,
)

router = APIRouter(prefix="/mock", tags=["mock"])


class CpsOrderCallbackRequest(BaseModel):
    order_sn: str = Field(..., description="CPS渠道订单号")
    goods_id: str = Field(..., description="商品ID")
    goods_title: str = Field(default="", description="商品标题")
    pay_price: float = Field(default=0.0, description="支付金额")
    commission_rate: float = Field(default=0.0, description="佣金比例")
    commission: float = Field(default=0.0, description="佣金金额")
    order_status: str = Field(default="已结算", description="CPS订单状态")
    pay_time: str = Field(default="", description="支付时间")
    settle_time: Optional[str] = Field(default=None, description="结算时间")
    uid: str = Field(default="", description="用户ID")
    source: str = Field(default="miaoyouquan", description="CPS来源渠道")
    sign: str = Field(default="", description="签名")


class CpsOrderCallbackResponse(BaseModel):
    success: bool
    order_id: str = ""
    platform_commission: float = 0.0
    user_income: float = 0.0
    settle_commission: float = 0.0
    message: str = ""


class WxpayTransferCallbackRequest(BaseModel):
    event_type: str = Field(default="TRANSFER.BATCH.SUCCESS")
    resource_type: str = Field(default="encrypt-resource")
    resource: Dict[str, Any] = Field(default_factory=dict)
    decrypt_payload: Dict[str, Any] = Field(default_factory=dict)


class WxpayTransferCallbackResponse(BaseModel):
    success: bool
    batch_id: str = ""
    total_processed: int = 0
    total_amount: float = 0.0
    order_updates: list = Field(default_factory=list)
    message: str = ""


@router.post("/cps/order", response_model=CpsOrderCallbackResponse)
async def mock_cps_order_callback(payload: CpsOrderCallbackRequest):
    internal = transform_cps_order_to_internal(payload.model_dump())

    return CpsOrderCallbackResponse(
        success=True,
        order_id=internal["order_id"],
        platform_commission=float(internal["platform_commission"]),
        user_income=float(internal["user_income"]),
        settle_commission=float(internal["settle_commission"]),
        message="CPS订单回调解析成功",
    )


@router.post("/cps/order/with-sign", response_model=CpsOrderCallbackResponse)
async def mock_cps_order_callback_with_sign(
    payload: CpsOrderCallbackRequest,
    request: Request,
    secret: Optional[str] = None,
):
    body_bytes = json.dumps(payload.model_dump(), separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))

    expected_sign = compute_hmac_sha256(secret or "dev_secret", f"{timestamp}.{body_bytes.decode('utf-8')}")
    if payload.sign != expected_sign:
        raise HTTPException(status_code=400, detail="签名校验失败")

    internal = transform_cps_order_to_internal(payload.model_dump())

    return CpsOrderCallbackResponse(
        success=True,
        order_id=internal["order_id"],
        platform_commission=float(internal["platform_commission"]),
        user_income=float(internal["user_income"]),
        settle_commission=float(internal["settle_commission"]),
        message="CPS订单回调验签通过",
    )


@router.post("/wxpay/transfer", response_model=WxpayTransferCallbackResponse)
async def mock_wxpay_transfer_callback(payload: WxpayTransferCallbackRequest):
    callback_dict = payload.model_dump()
    resource = callback_dict.get("resource", {})
    if not resource:
        raise HTTPException(status_code=400, detail="缺少resource字段")

    decrypted = decrypt_wxpay_resource(callback_dict)
    if not decrypted:
        raise HTTPException(status_code=400, detail="解密结果为空")

    batch_id = decrypted.get("batch_id", "")
    total_amount = Decimal(str(decrypted.get("total_amount", 0))) / Decimal("100")
    details = decrypted.get("transfer_detail_list", [])

    order_updates = []
    for detail in details:
        out_detail_no = detail.get("out_detail_no", "")
        update = {
            "order_id": out_detail_no,
            "transfer_status": detail.get("transfer_status", ""),
            "transfer_amount": float(Decimal(str(detail.get("transfer_amount", 0))) / Decimal("100")),
            "payment_time": detail.get("payment_time"),
        }
        order_updates.append(update)

    return WxpayTransferCallbackResponse(
        success=True,
        batch_id=batch_id,
        total_processed=len(details),
        total_amount=float(total_amount),
        order_updates=order_updates,
        message="微信转账回调解密成功",
    )


@router.post("/cps/order/batch", response_model=list)
async def mock_cps_order_batch_callback(orders: list):
    results = []
    for order_data in orders:
        internal = transform_cps_order_to_internal(order_data)
        results.append({
            "order_id": internal["order_id"],
            "platform_commission": float(internal["platform_commission"]),
            "user_income": float(internal["user_income"]),
            "settle_commission": float(internal["settle_commission"]),
        })
    return results


@router.get("/cps/order/health")
async def mock_cps_order_health():
    return {
        "status": "ok",
        "service": "mock-cps-order",
        "timestamp": int(time.time()),
    }


@router.get("/wxpay/transfer/health")
async def mock_wxpay_transfer_health():
    return {
        "status": "ok",
        "service": "mock-wxpay-transfer",
        "timestamp": int(time.time()),
    }


def get_mock_router() -> APIRouter:
    return router


__all__ = [
    "router",
    "CpsOrderCallbackRequest",
    "CpsOrderCallbackResponse",
    "WxpayTransferCallbackRequest",
    "WxpayTransferCallbackResponse",
    "get_mock_router",
]
