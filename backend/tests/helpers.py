# @ai-generated
import json
import os
import sys
import hashlib
import hmac
from decimal import Decimal, ROUND_FLOOR
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MOCK_DATA_DIR = os.path.join(os.path.dirname(__file__), "mock_data")

PLATFORM_COMMISSION_RATE = Decimal("0.20")
USER_COMMISSION_RATE = Decimal("0.80")

ORDER_STATUS_PENDING = 10
ORDER_STATUS_FROZEN = 20
ORDER_STATUS_SETTLABLE = 30
ORDER_STATUS_SETTLED = 40
ORDER_STATUS_INVALID = 50
ORDER_STATUS_REFUNDED = 60

TRANSFER_STATUS_PENDING = "PENDING"
TRANSFER_STATUS_PROCESSING = "PROCESSING"
TRANSFER_STATUS_SUCCESS = "SUCCESS"
TRANSFER_STATUS_FAILED = "FAILED"

CHANNEL_MIAOQUAN = "miaoyouquan"
CHANNEL_ORDERX = "orderx"

WEBHOOK_TIMESTAMP_THRESHOLD = 300

TRANSFER_SCENE_ID = "1005"


def load_mock_json(filename: str) -> Dict[str, Any]:
    filepath = os.path.join(MOCK_DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_hmac_sha256(secret: str, body: str) -> str:
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def compute_commission_split(settle_commission: Decimal) -> Dict[str, Decimal]:
    platform = (settle_commission * PLATFORM_COMMISSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
    user = (settle_commission - platform).quantize(Decimal("0.01"))
    return {
        "platform_commission": platform,
        "user_income": user,
        "total": settle_commission,
    }


def transform_cps_order_to_internal(cps_data: Dict[str, Any]) -> Dict[str, Any]:
    settle_commission = Decimal(str(cps_data.get("commission", "0")))
    split = compute_commission_split(settle_commission)

    order_sn = cps_data.get("order_sn", "")
    if order_sn.startswith("M"):
        internal_order_id = f"GAK{order_sn[1:]}"
    elif order_sn.startswith("O"):
        internal_order_id = f"GAK{order_sn[1:]}"
    else:
        internal_order_id = f"GAK{order_sn}"

    return {
        "order_id": internal_order_id,
        "cps_order_sn": order_sn,
        "user_id": cps_data.get("uid", ""),
        "item_id": cps_data.get("goods_id", ""),
        "item_title": cps_data.get("goods_title", ""),
        "pay_amount": Decimal(str(cps_data.get("pay_price", "0"))),
        "settle_commission": settle_commission,
        "platform_commission": split["platform_commission"],
        "user_income": split["user_income"],
        "order_status": ORDER_STATUS_PENDING,
        "transfer_status": TRANSFER_STATUS_PENDING,
        "cps_source": cps_data.get("source", ""),
        "cps_order_status": cps_data.get("order_status", ""),
        "pay_time": cps_data.get("pay_time", ""),
        "settle_time": cps_data.get("settle_time"),
    }


def decrypt_wxpay_resource(callback: Dict[str, Any]) -> Dict[str, Any]:
    return callback.get("decrypt_payload", {})


def build_internal_order_from_wxpay(
    internal_order_id: str,
    transfer_data: Dict[str, Any],
    batch_id: str,
) -> Dict[str, Any]:
    transfer_amount_raw = transfer_data.get("transfer_amount", 0)
    transfer_amount = Decimal(str(transfer_amount_raw)) / Decimal("100")

    return {
        "order_id": internal_order_id,
        "wx_batch_id": batch_id,
        "wx_out_detail_no": transfer_data.get("out_detail_no", ""),
        "transfer_amount": transfer_amount,
        "transfer_status": transfer_data.get("transfer_status", ""),
        "transfer_scene_id": transfer_data.get("transfer_scene_id", TRANSFER_SCENE_ID),
        "payment_time": transfer_data.get("payment_time"),
        "remark": transfer_data.get("remark", ""),
    }


__all__ = [
    "MOCK_DATA_DIR",
    "PLATFORM_COMMISSION_RATE",
    "USER_COMMISSION_RATE",
    "ORDER_STATUS_PENDING",
    "ORDER_STATUS_FROZEN",
    "ORDER_STATUS_SETTLABLE",
    "ORDER_STATUS_SETTLED",
    "ORDER_STATUS_INVALID",
    "ORDER_STATUS_REFUNDED",
    "TRANSFER_STATUS_PENDING",
    "TRANSFER_STATUS_PROCESSING",
    "TRANSFER_STATUS_SUCCESS",
    "TRANSFER_STATUS_FAILED",
    "CHANNEL_MIAOQUAN",
    "CHANNEL_ORDERX",
    "WEBHOOK_TIMESTAMP_THRESHOLD",
    "TRANSFER_SCENE_ID",
    "load_mock_json",
    "compute_hmac_sha256",
    "compute_commission_split",
    "transform_cps_order_to_internal",
    "decrypt_wxpay_resource",
    "build_internal_order_from_wxpay",
]
