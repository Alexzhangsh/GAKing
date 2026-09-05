# @ai-generated
"""
B11 提现后置审批编排 Service 单元测试（AsyncMock 模拟，不依赖真实 DB/Redis/微信API）

覆盖范围（目标覆盖率 ≥90%）：
 1. WithdrawReviewService
    - approve_and_transfer（审核通过，手动模式 + 自动转账模式）
    - approve_and_transfer 幂等拦截
    - approve_and_transfer B10 转账成功联动
    - approve_and_transfer B10 转账失败不回滚
    - approve_and_transfer mock 用户模拟打款（X01-1）
    - reject（审核驳回 + 日志记录）
    - on_transfer_success（打款成功回调）
    - on_transfer_fail（打款失败回调）
    - list_applies_with_filter（金额/时间范围过滤）
    - get_review_logs（审批历史查询）
    - list_review_logs_with_filters（多条件查询）
    - _acquire_review_lock / _release_review_lock（幂等锁）
    - _trigger_wechat_transfer（B10 转账触发 + mock 用户边界）
    - _log_review（日志记录失败不阻断）
 2. WithdrawReviewLogDAO
    - list_by_apply_id（按申请查询历史）
    - list_with_filters（多条件筛选）
 3. 状态机约束
    - REJECTED 终态不可二次操作
"""
import sys
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.services.withdraw_review_service import (
    ACTION_APPROVE,
    ACTION_REJECT,
    ACTION_TRANSFER,
    ACTION_TRANSFER_FAIL,
    ACTION_TRANSFER_SUCCESS,
    LOCK_KEY_REVIEW,
    WithdrawReviewService,
)
from src.dao.withdraw_review_log_dao import WithdrawReviewLogDAO
from src.config.constants import WithdrawStatus


# ══════════════════════════════════════════════════════
# WithdrawReviewService 测试
# ══════════════════════════════════════════════════════


class TestWithdrawReviewService:
    """提现后置审批编排 Service 测试"""

    def _make_service(
        self,
        withdraw_service: Optional[MagicMock] = None,
        review_log_dao: Optional[MagicMock] = None,
        wechat_pay_service: Optional[MagicMock] = None,
    ) -> WithdrawReviewService:
        if withdraw_service is None:
            withdraw_service = MagicMock()
        if review_log_dao is None:
            review_log_dao = MagicMock()
            review_log_dao.create = AsyncMock(return_value=MagicMock())
        return WithdrawReviewService(
            withdraw_service=withdraw_service,
            review_log_dao=review_log_dao,
            wechat_pay_service=wechat_pay_service,
        )

    def _patch_lock(self, acquired: bool = True):
        """patch LockUtil.acquire_lock / release_lock"""
        owner = "lock_owner_123" if acquired else None
        return (
            patch(
                "src.services.withdraw_review_service.LockUtil.acquire_lock",
                new=AsyncMock(return_value=owner),
            ),
            patch(
                "src.services.withdraw_review_service.LockUtil.release_lock",
                new=AsyncMock(return_value=True),
            ),
        )

    @pytest.mark.asyncio
    async def test_approve_manual_mode(self):
        """审核通过（手动打款模式，不触发微信转账）"""
        svc = self._make_service()
        svc.withdraw_service.approve_apply = AsyncMock(
            return_value={"apply_id": 1, "status": "APPROVED", "apply_no": "GAKW001"}
        )

        acq, rel = self._patch_lock(True)
        with acq, rel:
            result = await svc.approve_and_transfer(
                apply_id=1,
                review_user_id=100,
                review_remark="通过",
            )

        assert result["apply"]["status"] == "APPROVED"
        assert result["transfer"] is None
        svc.withdraw_service.approve_apply.assert_awaited_once()
        svc.review_log_dao.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_approve_auto_transfer_success(self):
        """审核通过 + 自动转账成功"""
        wechat_svc = MagicMock()
        wechat_svc.transfer_single = AsyncMock(
            return_value={"batch_id": "wx_batch_001", "out_batch_no": "GAKW001"}
        )
        svc = self._make_service(wechat_pay_service=wechat_svc)
        svc.withdraw_service.approve_apply = AsyncMock(
            return_value={
                "apply_id": 1,
                "status": "APPROVED",
                "apply_no": "GAKW001",
                "apply_amount": "100.00",
            }
        )

        acq, rel = self._patch_lock(True)
        with acq, rel:
            result = await svc.approve_and_transfer(
                apply_id=1,
                review_user_id=100,
                review_remark="通过",
                openid="oX123456",
                auto_transfer=True,
            )

        assert result["transfer"]["batch_id"] == "wx_batch_001"
        wechat_svc.transfer_single.assert_awaited_once()
        # 应记录2条日志：APPROVE + TRANSFER
        assert svc.review_log_dao.create.await_count == 2

    @pytest.mark.asyncio
    async def test_approve_auto_transfer_fail_no_rollback(self):
        """审核通过 + 自动转账失败（不回滚审核状态）"""
        wechat_svc = MagicMock()
        wechat_svc.transfer_single = AsyncMock(side_effect=Exception("微信API失败"))
        svc = self._make_service(wechat_pay_service=wechat_svc)
        svc.withdraw_service.approve_apply = AsyncMock(
            return_value={
                "apply_id": 1,
                "status": "APPROVED",
                "apply_no": "GAKW001",
                "apply_amount": "100.00",
            }
        )

        acq, rel = self._patch_lock(True)
        with acq, rel:
            result = await svc.approve_and_transfer(
                apply_id=1,
                review_user_id=100,
                review_remark="通过",
                openid="oX123456",
                auto_transfer=True,
            )

        # 审核已通过，转账失败不回滚
        assert result["apply"]["status"] == "APPROVED"
        assert result["transfer"] is None
        # 仍记录2条日志：APPROVE + TRANSFER(失败)
        assert svc.review_log_dao.create.await_count == 2

    @pytest.mark.asyncio
    async def test_approve_no_wechat_service_skip_transfer(self):
        """未注入微信支付服务时跳过自动转账"""
        svc = self._make_service(wechat_pay_service=None)
        svc.withdraw_service.approve_apply = AsyncMock(
            return_value={"apply_id": 1, "status": "APPROVED", "apply_no": "GAKW001"}
        )

        acq, rel = self._patch_lock(True)
        with acq, rel:
            result = await svc.approve_and_transfer(
                apply_id=1,
                review_user_id=100,
                review_remark="通过",
                openid="oX123456",
                auto_transfer=True,
            )

        assert result["transfer"] is None
        # 只记录1条日志：APPROVE
        assert svc.review_log_dao.create.await_count == 1

    @pytest.mark.asyncio
    async def test_approve_idempotent_blocked(self):
        """审核通过幂等拦截"""
        svc = self._make_service()
        acq, rel = self._patch_lock(False)  # 锁获取失败
        with acq, rel:
            with pytest.raises(ValueError, match="正在.*处理中"):
                await svc.approve_and_transfer(
                    apply_id=1,
                    review_user_id=100,
                    review_remark="通过",
                )
        # B09 approve_apply 不应被调用
        svc.withdraw_service.approve_apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_reject_success(self):
        """审核驳回成功"""
        svc = self._make_service()
        svc.withdraw_service.reject_apply = AsyncMock(
            return_value={"apply_id": 1, "status": "REJECTED"}
        )

        acq, rel = self._patch_lock(True)
        with acq, rel:
            result = await svc.reject(
                apply_id=1,
                review_user_id=100,
                reject_reason="信息不全",
            )

        assert result["status"] == "REJECTED"
        svc.withdraw_service.reject_apply.assert_awaited_once()
        svc.review_log_dao.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reject_idempotent_blocked(self):
        """审核驳回幂等拦截"""
        svc = self._make_service()
        acq, rel = self._patch_lock(False)
        with acq, rel:
            with pytest.raises(ValueError, match="正在.*处理中"):
                await svc.reject(1, 100, "驳回")
        svc.withdraw_service.reject_apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_transfer_success(self):
        """微信打款成功回调"""
        svc = self._make_service()
        svc.withdraw_service.complete_apply = AsyncMock(
            return_value={"apply_id": 1, "status": "SUCCESS"}
        )

        acq, rel = self._patch_lock(True)
        with acq, rel:
            result = await svc.on_transfer_success(
                apply_id=1,
                transfer_batch_id="wx_batch_001",
            )

        assert result["status"] == "SUCCESS"
        svc.withdraw_service.complete_apply.assert_awaited_once()
        svc.review_log_dao.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_transfer_success_idempotent_blocked(self):
        """打款成功回调幂等拦截"""
        svc = self._make_service()
        acq, rel = self._patch_lock(False)
        with acq, rel:
            with pytest.raises(ValueError, match="正在.*处理中"):
                await svc.on_transfer_success(1, "batch_001")
        svc.withdraw_service.complete_apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_transfer_fail(self):
        """微信打款失败回调"""
        svc = self._make_service()
        svc.withdraw_service.fail_apply = AsyncMock(
            return_value={"apply_id": 1, "status": "REJECTED"}
        )

        acq, rel = self._patch_lock(True)
        with acq, rel:
            result = await svc.on_transfer_fail(
                apply_id=1,
                fail_reason="银行卡异常",
            )

        assert result["status"] == "REJECTED"
        svc.withdraw_service.fail_apply.assert_awaited_once()
        svc.review_log_dao.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_transfer_fail_idempotent_blocked(self):
        """打款失败回调幂等拦截"""
        svc = self._make_service()
        acq, rel = self._patch_lock(False)
        with acq, rel:
            with pytest.raises(ValueError, match="正在.*处理中"):
                await svc.on_transfer_fail(1, "失败")
        svc.withdraw_service.fail_apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_applies_with_filter_amount_range(self):
        """金额范围过滤"""
        svc = self._make_service()
        svc.withdraw_service.list_applies_for_admin = AsyncMock(
            return_value={
                "list": [
                    {"apply_amount": "50.00", "create_time": ""},
                    {"apply_amount": "150.00", "create_time": ""},
                    {"apply_amount": "500.00", "create_time": ""},
                ],
                "total": 3,
                "page": 1,
                "page_size": 20,
            }
        )

        result = await svc.list_applies_with_filter(
            min_amount=Decimal("100"), max_amount=Decimal("300")
        )

        assert len(result["list"]) == 1
        assert result["list"][0]["apply_amount"] == "150.00"

    @pytest.mark.asyncio
    async def test_list_applies_with_filter_time_range(self):
        """时间范围过滤"""
        svc = self._make_service()
        svc.withdraw_service.list_applies_for_admin = AsyncMock(
            return_value={
                "list": [
                    {
                        "apply_amount": "100.00",
                        "create_time": "2026-07-01 10:00:00",
                    },
                    {
                        "apply_amount": "100.00",
                        "create_time": "2026-08-01 10:00:00",
                    },
                ],
                "total": 2,
                "page": 1,
                "page_size": 20,
            }
        )

        result = await svc.list_applies_with_filter(
            start_time=datetime(2026, 7, 15, 0, 0, 0),
            end_time=datetime(2026, 8, 15, 0, 0, 0),
        )

        assert len(result["list"]) == 1
        assert result["list"][0]["create_time"] == "2026-08-01 10:00:00"

    @pytest.mark.asyncio
    async def test_list_applies_no_filter(self):
        """无过滤条件直接返回"""
        svc = self._make_service()
        svc.withdraw_service.list_applies_for_admin = AsyncMock(
            return_value={
                "list": [{"apply_amount": "100.00", "create_time": ""}],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
        )

        result = await svc.list_applies_with_filter()
        assert len(result["list"]) == 1
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_get_review_logs(self):
        """查询审批操作历史"""
        svc = self._make_service()
        mock_log = MagicMock()
        mock_log.to_dict.return_value = {"action": "APPROVE"}
        svc.review_log_dao.list_by_apply_id = AsyncMock(return_value=([mock_log], 1))

        result = await svc.get_review_logs(apply_id=1)

        assert result["total"] == 1
        assert result["list"][0]["action"] == "APPROVE"

    @pytest.mark.asyncio
    async def test_list_review_logs_with_filters(self):
        """多条件查询审批日志"""
        svc = self._make_service()
        mock_log = MagicMock()
        mock_log.to_dict.return_value = {"action": "REJECT"}
        svc.review_log_dao.list_with_filters = AsyncMock(return_value=([mock_log], 1))

        result = await svc.list_review_logs_with_filters(
            action="REJECT",
            operator_id=100,
        )

        assert result["total"] == 1
        assert result["list"][0]["action"] == "REJECT"

    @pytest.mark.asyncio
    async def test_log_review_failure_not_block(self):
        """日志记录失败不阻断主流程"""
        svc = self._make_service()
        svc.review_log_dao.create = AsyncMock(side_effect=Exception("DB error"))

        # 不抛异常，静默降级
        await svc._log_review(
            apply_id=1,
            from_status="PENDING",
            to_status="APPROVED",
            action="APPROVE",
            operator_id=100,
            remark="test",
        )
        # 方法正常返回，不抛异常

    @pytest.mark.asyncio
    async def test_trigger_wechat_transfer_no_service(self):
        """未注入微信支付服务时返回 None"""
        svc = self._make_service(wechat_pay_service=None)
        result = await svc._trigger_wechat_transfer(
            apply_id=1,
            apply_result={"apply_no": "GAKW001", "apply_amount": "100.00"},
            openid="oX123",
            operator_id=100,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_wechat_transfer_success(self):
        """微信转账触发成功"""
        wechat_svc = MagicMock()
        wechat_svc.transfer_single = AsyncMock(
            return_value={"batch_id": "wx_001", "out_batch_no": "GAKW001"}
        )
        svc = self._make_service(wechat_pay_service=wechat_svc)

        result = await svc._trigger_wechat_transfer(
            apply_id=1,
            apply_result={"apply_no": "GAKW001", "apply_amount": "100.00"},
            openid="oX123",
            operator_id=100,
        )

        assert result["batch_id"] == "wx_001"
        wechat_svc.transfer_single.assert_awaited_once()
        # 记录 TRANSFER 日志
        svc.review_log_dao.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_trigger_wechat_transfer_fail_returns_none(self):
        """微信转账失败返回 None"""
        wechat_svc = MagicMock()
        wechat_svc.transfer_single = AsyncMock(side_effect=Exception("API error"))
        svc = self._make_service(wechat_pay_service=wechat_svc)

        result = await svc._trigger_wechat_transfer(
            apply_id=1,
            apply_result={"apply_no": "GAKW001", "apply_amount": "100.00"},
            openid="oX123",
            operator_id=100,
        )

        assert result is None
        # 失败也记录日志
        svc.review_log_dao.create.assert_awaited_once()

    # ── X01-1：mock 用户提现边界 ─────────────────────────

    @pytest.mark.asyncio
    async def test_trigger_wechat_transfer_mock_openid_simulates(self):
        """mock 用户（非生产环境）→ 模拟打款，不调真实微信接口"""
        wechat_svc = MagicMock()
        wechat_svc.transfer_single = AsyncMock(
            return_value={"batch_id": "wx_001", "out_batch_no": "GAKW001"}
        )
        svc = self._make_service(wechat_pay_service=wechat_svc)

        with patch(
            "src.common.mock_user_util.EnvConfig.ENVIRONMENT",
            "development",
        ):
            result = await svc._trigger_wechat_transfer(
                apply_id=1,
                apply_result={"apply_no": "GAKW001", "apply_amount": "100.00"},
                openid="dev_abc123",
                operator_id=100,
            )

        # 返回 mock 批次号，且标记 mock=True
        assert result["batch_id"] == "MOCKBATCHGAKW001"
        assert result["mock"] is True
        # 不调用真实微信接口
        wechat_svc.transfer_single.assert_not_called()
        # 记录 TRANSFER 日志（含模拟标记）
        svc.review_log_dao.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_trigger_wechat_transfer_mock_openid_production_refuses(self):
        """mock 用户（生产环境）→ 拒绝模拟，不调真实微信接口，转人工"""
        wechat_svc = MagicMock()
        wechat_svc.transfer_single = AsyncMock(
            return_value={"batch_id": "wx_001", "out_batch_no": "GAKW001"}
        )
        svc = self._make_service(wechat_pay_service=wechat_svc)

        with patch(
            "src.common.mock_user_util.EnvConfig.ENVIRONMENT",
            "production",
        ):
            result = await svc._trigger_wechat_transfer(
                apply_id=1,
                apply_result={"apply_no": "GAKW001", "apply_amount": "100.00"},
                openid="dev_abc123",
                operator_id=100,
            )

        # 生产环境不模拟、不调真实接口 → 返回 None（转人工打款）
        assert result is None
        wechat_svc.transfer_single.assert_not_called()
        svc.review_log_dao.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_wechat_transfer_real_openid_calls_wechat(self):
        """真实 openid → 正常调用真实微信接口（不受 mock 逻辑影响）"""
        wechat_svc = MagicMock()
        wechat_svc.transfer_single = AsyncMock(
            return_value={"batch_id": "wx_001", "out_batch_no": "GAKW001"}
        )
        svc = self._make_service(wechat_pay_service=wechat_svc)

        with patch(
            "src.common.mock_user_util.EnvConfig.ENVIRONMENT",
            "development",
        ):
            result = await svc._trigger_wechat_transfer(
                apply_id=1,
                apply_result={"apply_no": "GAKW001", "apply_amount": "100.00"},
                openid="oX8Kj5tQ2mWvYzAbCdEfGhIjKlMnOpQr",
                operator_id=100,
            )

        assert result["batch_id"] == "wx_001"
        assert result.get("mock") is not True
        wechat_svc.transfer_single.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_approve_and_transfer_mock_openid_simulates(self):
        """审核通过 + mock 用户自动打款 → 模拟打款成功（全流程可自测）"""
        wechat_svc = MagicMock()
        wechat_svc.transfer_single = AsyncMock(
            return_value={"batch_id": "wx_001", "out_batch_no": "GAKW001"}
        )
        svc = self._make_service(wechat_pay_service=wechat_svc)
        svc.withdraw_service.approve_apply = AsyncMock(
            return_value={
                "apply_id": 1,
                "status": "APPROVED",
                "apply_no": "GAKW001",
                "apply_amount": "100.00",
            }
        )

        acq, rel = self._patch_lock(True)
        with acq, rel, patch(
            "src.common.mock_user_util.EnvConfig.ENVIRONMENT",
            "development",
        ):
            result = await svc.approve_and_transfer(
                apply_id=1,
                review_user_id=100,
                review_remark="通过",
                openid="dev_abc123",
                auto_transfer=True,
            )

        assert result["apply"]["status"] == "APPROVED"
        assert result["transfer"]["batch_id"] == "MOCKBATCHGAKW001"
        assert result["transfer"]["mock"] is True
        # 不调用真实微信接口
        wechat_svc.transfer_single.assert_not_called()
        # 记录2条日志：APPROVE + TRANSFER(模拟)
        assert svc.review_log_dao.create.await_count == 2

    @pytest.mark.asyncio
    async def test_release_review_lock_no_owner(self):
        """无 lock_owner 时释放锁不报错"""
        svc = self._make_service()
        svc._current_lock_owner = None
        # 不抛异常
        await svc._release_review_lock(1, "APPROVE")


# ══════════════════════════════════════════════════════
# WithdrawReviewLogDAO 测试
# ══════════════════════════════════════════════════════


class TestWithdrawReviewLogDAO:
    """审批日志 DAO 测试"""

    @pytest.mark.asyncio
    async def test_list_by_apply_id(self):
        """按申请ID查询操作历史"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()]
        mock_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        dao = WithdrawReviewLogDAO(mock_session)
        items, total = await dao.list_by_apply_id(1)

        assert total == 1
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_list_by_apply_id_page_correction(self):
        """页码校正（page < 1 → 1）"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        dao = WithdrawReviewLogDAO(mock_session)
        items, total = await dao.list_by_apply_id(1, page=-1, page_size=0)

        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_list_with_filters(self):
        """多条件筛选查询"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()]
        mock_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        dao = WithdrawReviewLogDAO(mock_session)
        items, total = await dao.list_with_filters(
            apply_id=1,
            action="APPROVE",
            operator_id=100,
            start_time=datetime(2026, 1, 1),
            end_time=datetime(2026, 12, 31),
        )

        assert total == 1
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_list_with_filters_no_conditions(self):
        """无筛选条件查询全部"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        dao = WithdrawReviewLogDAO(mock_session)
        items, total = await dao.list_with_filters()

        assert total == 0
        assert items == []
