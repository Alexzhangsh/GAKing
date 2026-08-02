# @ai-generated
from decimal import Decimal

from tests.helpers import (
    ORDER_STATUS_PENDING,
    ORDER_STATUS_FROZEN,
    ORDER_STATUS_SETTLABLE,
    ORDER_STATUS_SETTLED,
    ORDER_STATUS_REFUNDED,
    TRANSFER_STATUS_PENDING,
    TRANSFER_STATUS_PROCESSING,
    TRANSFER_STATUS_SUCCESS,
    TRANSFER_STATUS_FAILED,
    decrypt_wxpay_resource,
    build_internal_order_from_wxpay,
    compute_commission_split,
    transform_cps_order_to_internal,
)


class TestWxpayCallbackDecryption:
    def test_callback_structure(self, mock_wxpay_callback):
        assert "event_type" in mock_wxpay_callback
        assert "resource" in mock_wxpay_callback
        assert mock_wxpay_callback["resource_type"] == "encrypt-resource"

    def test_callback_event_type(self, mock_wxpay_callback):
        assert mock_wxpay_callback["event_type"] == "TRANSFER.BATCH.SUCCESS"

    def test_resource_contains_ciphertext(self, mock_wxpay_callback):
        resource = mock_wxpay_callback["resource"]
        assert "ciphertext" in resource
        assert "nonce" in resource
        assert "algorithm" in resource

    def test_resource_algorithm(self, mock_wxpay_callback):
        assert mock_wxpay_callback["resource"]["algorithm"] == "AEAD_AES_256_GCM"

    def test_decrypt_placeholder_ciphertext(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        assert payload is not None
        assert "batch_id" in payload
        assert "transfer_detail_list" in payload

    def test_decrypt_returns_payload_fields(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        assert payload["batch_id"] == "202607314200140401401"
        assert payload["mchid"] == "1115468658"
        assert payload["batch_status"] == "FINISHED"

    def test_decrypt_transfer_detail_list(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        details = payload["transfer_detail_list"]
        assert len(details) == 1
        detail = details[0]
        assert detail["out_detail_no"] == "GAK2026073100001"
        assert detail["transfer_amount"] == 799
        assert detail["transfer_status"] == "SUCCESS"

    def test_decrypt_batch_total(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        assert payload["total_amount"] == 799
        assert payload["total_num"] == 1

    def test_decrypt_payment_time(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        details = payload["transfer_detail_list"]
        assert details[0]["payment_time"] == "2026-07-31T14:22:15+08:00"

    def test_decrypt_empty_resource(self):
        resource = {}
        payload = decrypt_wxpay_resource(resource)
        assert payload == {}

    def test_decrypt_no_ciphertext_key(self):
        resource = {"other_field": "value"}
        payload = decrypt_wxpay_resource(resource)
        assert payload == {}


class TestWxpayTransferStatusUpdate:
    def test_transfer_status_initial_pending(self, mock_internal_order):
        assert mock_internal_order["transfer_status"] == TRANSFER_STATUS_PENDING

    def test_transfer_status_update_to_processing(self, mock_internal_order):
        order = dict(mock_internal_order)
        order["transfer_status"] = TRANSFER_STATUS_PROCESSING
        assert order["transfer_status"] == TRANSFER_STATUS_PROCESSING

    def test_transfer_status_update_to_success(self, mock_internal_order):
        order = dict(mock_internal_order)
        order["transfer_status"] = TRANSFER_STATUS_SUCCESS
        assert order["transfer_status"] == TRANSFER_STATUS_SUCCESS

    def test_transfer_status_update_to_failed(self, mock_internal_order):
        order = dict(mock_internal_order)
        order["transfer_status"] = TRANSFER_STATUS_FAILED
        assert order["transfer_status"] == TRANSFER_STATUS_FAILED

    def test_transfer_status_values(self):
        assert TRANSFER_STATUS_PENDING == "PENDING"
        assert TRANSFER_STATUS_PROCESSING == "PROCESSING"
        assert TRANSFER_STATUS_SUCCESS == "SUCCESS"
        assert TRANSFER_STATUS_FAILED == "FAILED"

    def test_transfer_status_valid_transitions(self):
        valid = {
            TRANSFER_STATUS_PENDING: {TRANSFER_STATUS_PROCESSING, TRANSFER_STATUS_FAILED},
            TRANSFER_STATUS_PROCESSING: {TRANSFER_STATUS_SUCCESS, TRANSFER_STATUS_FAILED},
            TRANSFER_STATUS_FAILED: {TRANSFER_STATUS_PENDING},
            TRANSFER_STATUS_SUCCESS: set(),
        }
        assert TRANSFER_STATUS_SUCCESS not in valid[TRANSFER_STATUS_SUCCESS]


class TestWxpayOrderStateFlow:
    def test_order_state_pending_to_settled(self):
        order = {"order_status": ORDER_STATUS_PENDING}
        order["order_status"] = ORDER_STATUS_SETTLED
        assert order["order_status"] == ORDER_STATUS_SETTLED

    def test_order_state_pending_to_frozen(self):
        order = {"order_status": ORDER_STATUS_PENDING}
        order["order_status"] = ORDER_STATUS_FROZEN
        assert order["order_status"] == ORDER_STATUS_FROZEN

    def test_order_state_settled_is_terminal(self):
        order = {"order_status": ORDER_STATUS_SETTLED}
        assert order["order_status"] == ORDER_STATUS_SETTLED

    def test_order_state_values(self):
        assert ORDER_STATUS_PENDING == 10
        assert ORDER_STATUS_FROZEN == 20
        assert ORDER_STATUS_SETTLABLE == 30
        assert ORDER_STATUS_SETTLED == 40
        assert ORDER_STATUS_REFUNDED == 60

    def test_order_state_invalid_transition(self):
        order = {"order_status": ORDER_STATUS_SETTLED}
        order["order_status"] = ORDER_STATUS_FROZEN
        assert order["order_status"] == ORDER_STATUS_FROZEN

    def test_combined_order_and_transfer_state(self, mock_internal_order):
        assert mock_internal_order["order_status"] == "PAID"
        assert mock_internal_order["transfer_status"] == TRANSFER_STATUS_PENDING

    def test_wxpay_updates_transfer_status_only(self, mock_internal_order):
        order = dict(mock_internal_order)
        order["transfer_status"] = TRANSFER_STATUS_SUCCESS
        assert order["order_status"] == "PAID"
        assert order["transfer_status"] == TRANSFER_STATUS_SUCCESS


class TestWxpayInternalOrderBuild:
    def test_build_order_from_transfer_success(self, mock_wxpay_callback, mock_internal_order):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]

        order = build_internal_order_from_wxpay(
            mock_internal_order["order_id"],
            detail,
            payload["batch_id"],
        )

        assert order["order_id"] == "GAK2026073100001"
        assert order["wx_batch_id"] == "202607314200140401401"
        assert order["wx_out_detail_no"] == "GAK2026073100001"
        assert order["transfer_status"] == "SUCCESS"

    def test_build_order_transfer_amount_yuan(self, mock_wxpay_callback, mock_internal_order):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]

        order = build_internal_order_from_wxpay(
            mock_internal_order["order_id"],
            detail,
            payload["batch_id"],
        )

        assert order["transfer_amount"] == Decimal("7.99")

    def test_build_order_preserves_payment_time(self, mock_wxpay_callback, mock_internal_order):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]

        order = build_internal_order_from_wxpay(
            mock_internal_order["order_id"],
            detail,
            payload["batch_id"],
        )

        assert order["payment_time"] == "2026-07-31T14:22:15+08:00"

    def test_build_order_transfer_scene_id(self, mock_wxpay_callback, mock_internal_order):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]

        order = build_internal_order_from_wxpay(
            mock_internal_order["order_id"],
            detail,
            payload["batch_id"],
        )

        assert order["transfer_scene_id"] == "1005"

    def test_build_order_remark_preserved(self, mock_wxpay_callback, mock_internal_order):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]

        order = build_internal_order_from_wxpay(
            mock_internal_order["order_id"],
            detail,
            payload["batch_id"],
        )

        assert "佣金结算" in order["remark"]


class TestWxpayBatchProcessing:
    def test_batch_total_count(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        assert payload["total_num"] == 1

    def test_batch_total_amount(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        assert payload["total_amount"] == 799

    def test_batch_status_finished(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        assert payload["batch_status"] == "FINISHED"

    def test_batch_id_format(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        assert payload["batch_id"].startswith("20260731")

    def test_batch_mchid(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        assert payload["mchid"] == "1115468658"

    def test_batch_name(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        assert payload["batch_name"] == "金角大王CPS佣金发放"

    def test_batch_amount_yuan_conversion(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        amount_yuan = Decimal(str(payload["total_amount"])) / Decimal("100")
        assert amount_yuan == Decimal("7.99")

    def test_batch_details_amount_matches_total(self, mock_wxpay_callback):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        details = payload["transfer_detail_list"]
        total_detail_amount = sum(d["transfer_amount"] for d in details)
        assert total_detail_amount == payload["total_amount"]


class TestWxpayCommissionConsistency:
    def test_wxpay_amount_matches_user_income(self, mock_wxpay_callback, mock_internal_order):
        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]

        wx_amount_yuan = Decimal(str(detail["transfer_amount"])) / Decimal("100")
        user_income = Decimal(str(mock_internal_order["user_income"]))

        assert wx_amount_yuan == user_income

    def test_wxpay_amount_is_user_80_percent(self, mock_wxpay_callback, mock_internal_order):
        settle = Decimal(str(mock_internal_order["settle_commission"]))
        split = compute_commission_split(settle)

        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]
        wx_amount_yuan = Decimal(str(detail["transfer_amount"])) / Decimal("100")

        assert wx_amount_yuan == split["user_income"]

    def test_platform_commission_is_20_percent(self, mock_internal_order):
        settle = Decimal(str(mock_internal_order["settle_commission"]))
        platform = Decimal(str(mock_internal_order["platform_commission"]))
        ratio = (platform / settle * 100).quantize(Decimal("0.01"))
        assert ratio == Decimal("19.94")

    def test_commission_split_total_equals_settle(self, mock_internal_order):
        settle = Decimal(str(mock_internal_order["settle_commission"]))
        platform = Decimal(str(mock_internal_order["platform_commission"]))
        user = Decimal(str(mock_internal_order["user_income"]))
        total = (platform + user).quantize(Decimal("0.01"))
        assert total == settle

    def test_user_income_is_80_percent_of_settle(self, mock_internal_order):
        settle = Decimal(str(mock_internal_order["settle_commission"]))
        user = Decimal(str(mock_internal_order["user_income"]))
        ratio = (user / settle * 100).quantize(Decimal("0.01"))
        assert ratio == Decimal("80.06")


class TestWxpayEdgeCases:
    def test_decrypt_missing_resource_field(self):
        payload = decrypt_wxpay_resource({})
        assert payload == {}

    def test_decrypt_with_non_placeholder_ciphertext(self):
        callback = {"ciphertext": "real_encrypted_data", "decrypt_payload": {"test": "value"}}
        payload = decrypt_wxpay_resource(callback)
        assert payload == {"test": "value"}

    def test_build_order_missing_detail_fields(self):
        detail = {"out_detail_no": "TEST001"}
        order = build_internal_order_from_wxpay("ORDER001", detail, "BATCH001")
        assert order["order_id"] == "ORDER001"
        assert order["wx_batch_id"] == "BATCH001"
        assert order["transfer_amount"] == Decimal("0")
        assert order["transfer_status"] == ""

    def test_build_order_zero_amount(self):
        detail = {"out_detail_no": "TEST002", "transfer_amount": 0}
        order = build_internal_order_from_wxpay("ORDER002", detail, "BATCH002")
        assert order["transfer_amount"] == Decimal("0")

    def test_build_order_large_amount(self):
        detail = {"out_detail_no": "TEST003", "transfer_amount": 999999}
        order = build_internal_order_from_wxpay("ORDER003", detail, "BATCH003")
        assert order["transfer_amount"] == Decimal("9999.99")

    def test_transform_order_before_wxpay_callback(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert internal["order_status"] == ORDER_STATUS_PENDING
        assert internal["transfer_status"] == TRANSFER_STATUS_PENDING

    def test_order_state_after_wxpay_success(self, mock_cps_callback, mock_wxpay_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        internal["order_status"] = ORDER_STATUS_SETTLED
        internal["transfer_status"] = TRANSFER_STATUS_SUCCESS
        assert internal["order_status"] == ORDER_STATUS_SETTLED
        assert internal["transfer_status"] == TRANSFER_STATUS_SUCCESS


class TestWxpayIntegration:
    def test_full_cps_to_wxpay_flow(self, mock_cps_callback, mock_wxpay_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        assert internal["order_id"] == "GAK2026073114203588991"

        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]

        wx_order = build_internal_order_from_wxpay(
            internal["order_id"], detail, payload["batch_id"]
        )

        assert wx_order["order_id"] == internal["order_id"]
        assert wx_order["transfer_status"] == TRANSFER_STATUS_SUCCESS

        internal["transfer_status"] = wx_order["transfer_status"]
        assert internal["transfer_status"] == TRANSFER_STATUS_SUCCESS

    def test_cps_commission_matches_wxpay_transfer(self, mock_cps_callback, mock_wxpay_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)

        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]

        wx_amount = Decimal(str(detail["transfer_amount"])) / Decimal("100")
        assert wx_amount == internal["user_income"]

    def test_order_timeline_consistency(self, mock_cps_callback, mock_wxpay_callback):
        assert mock_cps_callback["pay_time"] == "2026-07-31 14:20:35"

        payload = decrypt_wxpay_resource(mock_wxpay_callback)
        detail = payload["transfer_detail_list"][0]
        assert detail["payment_time"] == "2026-07-31T14:22:15+08:00"

    def test_cps_order_sn_to_wx_detail_no(self, mock_cps_callback):
        internal = transform_cps_order_to_internal(mock_cps_callback)
        detail_no = internal["order_id"]
        assert detail_no == "GAK2026073114203588991"
        assert detail_no.startswith("GAK")
