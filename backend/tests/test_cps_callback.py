# @ai-generated
import json
import time
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from tests.helpers import (
    PLATFORM_COMMISSION_RATE,
    USER_COMMISSION_RATE,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_SETTLED,
    CHANNEL_MIAOQUAN,
    compute_hmac_sha256,
    compute_commission_split,
    transform_cps_order_to_internal,
)
from src.common.webhook_util import WebhookUtil
from src.common.redis_client import RedisClient
from src.config.constants import IDEMPOTENT_PREFIX


class TestCpsCallbackParsing:
    def test_parse_cps_callback_structure(self, mock_cps_callback):
        assert "order_sn" in mock_cps_callback
        assert "goods_id" in mock_cps_callback
        assert "commission" in mock_cps_callback
        assert "order_status" in mock_cps_callback
        assert "uid" in mock_cps_callback
        assert "source" in mock_cps_callback
        assert "sign" in mock_cps_callback

    def test_parse_cps_callback_order_sn(self, mock_cps_callback):
        assert mock_cps_callback["order_sn"] == "M2026073114203588991"

    def test_parse_cps_callback_goods_id(self, mock_cps_callback):
        assert mock_cps_callback["goods_id"] == "MIAO20260731001"

    def test_parse_cps_callback_commission(self, mock_cps_callback):
        commission = Decimal(str(mock_cps_callback["commission"]))
        assert commission == Decimal("9.98")

    def test_parse_cps_callback_source(self, mock_cps_callback):
        assert mock_cps_callback["source"] == CHANNEL_MIAOQUAN

    def test_parse_cps_callback_price(self, mock_cps_callback):
        pay_price = Decimal(str(mock_cps_callback["pay_price"]))
        assert pay_price == Decimal("39.90")

    def test_transform_to_internal_order(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)

        assert internal["order_id"] == "GAK2026073114203588991"
        assert internal["cps_order_sn"] == "M2026073114203588991"
        assert internal["item_id"] == "MIAO20260731001"
        assert internal["item_title"] == "居家日用超值好物"
        assert internal["pay_amount"] == Decimal("39.90")
        assert internal["settle_commission"] == Decimal("9.98")
        assert internal["order_status"] == ORDER_STATUS_PENDING

    def test_transform_internal_order_id_format(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert internal["order_id"].startswith("GAK")
        assert len(internal["order_id"]) == len("GAK2026073114203588991")

    def test_transform_internal_preserves_user_id(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert internal["user_id"] == "u10001"

    def test_transform_internal_preserves_source(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert internal["cps_source"] == CHANNEL_MIAOQUAN

    def test_transform_internal_initial_transfer_status(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert internal["transfer_status"] == "PENDING"


class TestCpsCommissionSplit:
    def test_commission_split_platform_20_percent(self):
        settle = Decimal("9.98")
        result = compute_commission_split(settle)
        assert result["platform_commission"] == Decimal("1.99")
        assert result["user_income"] == Decimal("7.99")
        assert result["platform_commission"] + result["user_income"] == settle

    def test_commission_split_user_80_percent(self):
        settle = Decimal("9.98")
        result = compute_commission_split(settle)
        user_pct = (result["user_income"] / settle * 100).quantize(Decimal("0.01"))
        assert user_pct == Decimal("80.06")

    def test_commission_split_large_amount(self):
        settle = Decimal("999.99")
        result = compute_commission_split(settle)
        assert result["platform_commission"] == Decimal("199.99")
        assert result["user_income"] == Decimal("800.00")

    def test_commission_split_small_amount(self):
        settle = Decimal("1.00")
        result = compute_commission_split(settle)
        assert result["platform_commission"] == Decimal("0.20")
        assert result["user_income"] == Decimal("0.80")

    def test_commission_split_zero_amount(self):
        settle = Decimal("0.00")
        result = compute_commission_split(settle)
        assert result["platform_commission"] == Decimal("0.00")
        assert result["user_income"] == Decimal("0.00")

    def test_commission_split_total_consistency(self):
        test_amounts = [Decimal("9.98"), Decimal("3.50"), Decimal("128.40"), Decimal("0.99")]
        for amount in test_amounts:
            result = compute_commission_split(amount)
            total = result["platform_commission"] + result["user_income"]
            assert total == amount, f"Split sum mismatch for {amount}: {total}"

    def test_commission_split_with_internal_order(self, mock_cps_callback):
        settle = Decimal(str(mock_cps_callback["commission"]))
        result = compute_commission_split(settle)
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert internal["platform_commission"] == result["platform_commission"]
        assert internal["user_income"] == result["user_income"]

    def test_commission_split_platform_rate_constant(self):
        assert PLATFORM_COMMISSION_RATE == Decimal("0.20")
        assert USER_COMMISSION_RATE == Decimal("0.80")


class TestCpsSignatureVerification:
    @pytest.mark.asyncio
    async def test_signature_verification_valid(self, sample_webhook_secret):
        body = '{"order_sn": "test_order"}'
        signature = compute_hmac_sha256(sample_webhook_secret, body)
        valid, msg = WebhookUtil.validate_signature(body.encode("utf-8"), signature, sample_webhook_secret)
        assert valid is True
        assert msg == ""

    @pytest.mark.asyncio
    async def test_signature_verification_invalid(self, sample_webhook_secret):
        body = '{"order_sn": "test_order"}'
        valid, msg = WebhookUtil.validate_signature(body.encode("utf-8"), "invalid_signature", sample_webhook_secret)
        assert valid is False
        assert "Signature validation failed" in msg

    @pytest.mark.asyncio
    async def test_signature_verification_empty_secret(self):
        body = '{"order_sn": "test_order"}'
        valid, msg = WebhookUtil.validate_signature(body.encode("utf-8"), "any_signature", "")
        assert valid is False
        assert "Webhook secret not configured" in msg

    @pytest.mark.asyncio
    async def test_signature_verification_empty_body(self, sample_webhook_secret):
        body = '{}'
        signature = compute_hmac_sha256(sample_webhook_secret, body)
        valid, msg = WebhookUtil.validate_signature(body.encode("utf-8"), signature, sample_webhook_secret)
        assert valid is True

    @pytest.mark.asyncio
    async def test_signature_verification_deterministic(self, sample_webhook_secret):
        body = '{"test": "data"}'
        sig1 = compute_hmac_sha256(sample_webhook_secret, body)
        sig2 = compute_hmac_sha256(sample_webhook_secret, body)
        assert sig1 == sig2

    @pytest.mark.asyncio
    async def test_signature_verification_different_secrets(self):
        body = '{"test": "data"}'
        sig = compute_hmac_sha256("secret_a", body)
        valid, _ = WebhookUtil.validate_signature(body.encode("utf-8"), sig, "secret_b")
        assert valid is False


class TestCpsWebhookTimestamp:
    @pytest.mark.asyncio
    async def test_timestamp_valid(self, sample_timestamp):
        valid, msg = await WebhookUtil.validate_timestamp(sample_timestamp)
        assert valid is True

    @pytest.mark.asyncio
    async def test_timestamp_expired(self, expired_timestamp):
        valid, msg = await WebhookUtil.validate_timestamp(expired_timestamp)
        assert valid is False
        assert "Timestamp expired" in msg

    @pytest.mark.asyncio
    async def test_timestamp_future(self):
        future_ts = int(time.time()) + 3600
        valid, msg = await WebhookUtil.validate_timestamp(future_ts)
        assert valid is False

    @pytest.mark.asyncio
    async def test_timestamp_boundary(self):
        boundary_ts = int(time.time()) + 290
        valid, msg = await WebhookUtil.validate_timestamp(boundary_ts)
        assert valid is True


class TestCpsIdempotency:
    @pytest.mark.asyncio
    async def test_idempotency_first_request(self, sample_request_id):
        mock_exists = AsyncMock(return_value=0)
        mock_set = AsyncMock(return_value=True)

        with patch.object(RedisClient, "exists", mock_exists), \
             patch.object(RedisClient, "set", mock_set):
            valid, msg = await WebhookUtil.validate_idempotency(sample_request_id)
            assert valid is True

    @pytest.mark.asyncio
    async def test_idempotency_duplicate_request(self, sample_request_id):
        mock_exists = AsyncMock(return_value=1)

        with patch.object(RedisClient, "exists", mock_exists):
            valid, msg = await WebhookUtil.validate_idempotency(sample_request_id)
            assert valid is False
            assert "Duplicate request" in msg

    @pytest.mark.asyncio
    async def test_idempotency_empty_key(self):
        valid, msg = await WebhookUtil.validate_idempotency("")
        assert valid is False
        assert "Idempotency key is required" in msg

    @pytest.mark.asyncio
    async def test_idempotency_key_prefix(self, sample_request_id):
        key = f"{IDEMPOTENT_PREFIX}{sample_request_id}"
        assert key.startswith("gaking:prod:idempotent:")


class TestCpsFullWebhookFlow:
    @pytest.mark.asyncio
    async def test_full_webhook_validation_success(self, mock_cps_callback, sample_webhook_secret, sample_request_id):
        body = json.dumps(mock_cps_callback, separators=(",", ":"))
        timestamp = int(time.time())
        signature = compute_hmac_sha256(sample_webhook_secret, body)

        mock_exists = AsyncMock(return_value=0)
        mock_set = AsyncMock(return_value=True)

        with patch.object(RedisClient, "exists", mock_exists), \
             patch.object(RedisClient, "set", mock_set):
            valid, msg = await WebhookUtil.validate_webhook(
                timestamp, signature, body.encode("utf-8"),
                sample_webhook_secret, sample_request_id
            )
            assert valid is True

    @pytest.mark.asyncio
    async def test_full_webhook_validation_bad_signature(self, mock_cps_callback, sample_webhook_secret):
        body = json.dumps(mock_cps_callback)
        timestamp = int(time.time())

        valid, msg = await WebhookUtil.validate_webhook(
            timestamp, "bad_signature", body.encode("utf-8"),
            sample_webhook_secret
        )
        assert valid is False
        assert "Signature validation failed" in msg

    @pytest.mark.asyncio
    async def test_full_webhook_validation_expired_timestamp(self, mock_cps_callback, sample_webhook_secret, expired_timestamp):
        body = json.dumps(mock_cps_callback)
        signature = compute_hmac_sha256(sample_webhook_secret, body)

        valid, msg = await WebhookUtil.validate_webhook(
            expired_timestamp, signature, body.encode("utf-8"),
            sample_webhook_secret
        )
        assert valid is False
        assert "Timestamp validation failed" in msg

    @pytest.mark.asyncio
    async def test_webhook_verify_signature_combined(self, sample_webhook_secret, sample_request_id):
        data = '{"order_sn": "M2026073114203588991"}'
        timestamp = int(time.time())
        signature = compute_hmac_sha256(sample_webhook_secret, f"{timestamp}.{data}")

        with patch.object(RedisClient, "exists", AsyncMock(return_value=0)):
            valid = await WebhookUtil.verify_signature(timestamp, signature, data, sample_webhook_secret)
            assert valid is True

    @pytest.mark.asyncio
    async def test_webhook_verify_signature_bad(self, sample_webhook_secret):
        data = '{"order_sn": "test"}'
        timestamp = int(time.time())

        valid = await WebhookUtil.verify_signature(timestamp, "wrong_sig", data, sample_webhook_secret)
        assert valid is False


class TestCpsCallbackEdgeCases:
    def test_transform_missing_fields(self):
        minimal_data = {"order_sn": "M123", "commission": 0}
        internal = transform_cps_order_to_internal(minimal_data)
        assert internal["order_id"] == "GAK123"
        assert internal["settle_commission"] == Decimal("0")
        assert internal["platform_commission"] == Decimal("0")
        assert internal["user_income"] == Decimal("0")

    def test_transform_negative_commission(self):
        data = {"order_sn": "M456", "commission": -1.50}
        internal = transform_cps_order_to_internal(data)
        assert internal["settle_commission"] == Decimal("-1.50")
        assert internal["platform_commission"] == Decimal("-0.30")

    def test_transform_with_decimal_commission(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert isinstance(internal["settle_commission"], Decimal)
        assert isinstance(internal["platform_commission"], Decimal)
        assert isinstance(internal["user_income"], Decimal)

    def test_transform_user_id_preserved(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert internal["user_id"] == "u10001"

    def test_item_id_consistency(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert internal["item_id"] == mock_cps_callback["goods_id"]

    def test_commission_split_handles_rounding(self):
        settle = Decimal("3.33")
        result = compute_commission_split(settle)
        total = result["platform_commission"] + result["user_income"]
        assert total == settle

    def test_commission_split_handles_exact_division(self):
        settle = Decimal("10.00")
        result = compute_commission_split(settle)
        assert result["platform_commission"] == Decimal("2.00")
        assert result["user_income"] == Decimal("8.00")


class TestCpsCallbackIntegration:
    def test_end_to_end_parse_and_transform(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)

        expected_split = compute_commission_split(Decimal(str(mock_cps_callback["commission"])))
        assert internal["order_id"] == "GAK2026073114203588991"
        assert internal["cps_order_sn"] == mock_cps_callback["order_sn"]
        assert internal["settle_commission"] == Decimal(str(mock_cps_callback["commission"]))
        assert internal["platform_commission"] == expected_split["platform_commission"]
        assert internal["user_income"] == expected_split["user_income"]
        assert internal["pay_amount"] == Decimal(str(mock_cps_callback["pay_price"]))
        assert internal["user_id"] == mock_cps_callback["uid"]
        assert internal["item_id"] == mock_cps_callback["goods_id"]

    def test_product_match_callback(self, mock_cps_callback, mock_product):
        assert mock_cps_callback["goods_id"] == mock_product["item_id"]
        assert Decimal(str(mock_cps_callback["commission"])) == Decimal(str(mock_product["commission_amount"]))

    def test_channel_code_mapping(self, mock_cps_callback):
        assert mock_cps_callback["source"] == CHANNEL_MIAOQUAN

    def test_order_status_mapping(self, mock_cps_callback):
        assert mock_cps_callback["order_status"] == "已结算"
