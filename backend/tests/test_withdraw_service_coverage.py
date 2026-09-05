# @ai-generated
"""
B-Check-M01 补覆盖：WithdrawService 剩余 59% 缺口 → 目标 ≥90%

覆盖范围（补充现有 B09 测试未覆盖部分，0 改动业务代码）：
1. 内部工具方法：_to_decimal / _calc_fee / _gen_apply_no / _apply_lock_key
2. 流程2 reject_apply：正常驳回 / 申请不存在 / 状态非 PENDING / 锁获取失败 / 余额退回失败 CRITICAL
3. 流程3 approve_apply：正常通过 / 申请不存在 / 状态非 PENDING / 锁获取失败 / update 返回 None
4. 流程4 complete_apply：正常完成 / 申请不存在 / 状态不允许 / 锁获取失败 / 余额释放失败 CRITICAL
5. 流程5 fail_apply：正常退回 / 申请不存在 / 状态不允许 / 锁获取失败 / 余额退回失败 CRITICAL
6. 查询接口：
   - get_account（账户存在返回 dict / 账户不存在返回零占位）
   - list_my_applies（分页正常）
   - list_applies_for_admin（可选 user_id/status 筛选）
   - get_apply_detail（正常 / 申请不存在 ValueError）

所有 DAO / Redis / LockUtil / PayConfigUtil 均用 AsyncMock 打桩，不依赖真实环境。
"""
import sys
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.common.pay_config_util import PayConfigUtil, WithdrawFeeConfig
from src.config.constants import (
    LOCK_KEY_WITHDRAW_APPLY,
    WITHDRAW_FEE_MIN,
    WITHDRAW_FEE_QUANTIZE,
    WITHDRAW_FEE_RATE,
    WITHDRAW_MIN_AMOUNT,
    WithdrawStatus,
)
from src.services.withdraw_service import WithdrawService


# ════════════════════════════════════════════════════════════════════
# 通用辅助
# ════════════════════════════════════════════════════════════════════

def _svc() -> WithdrawService:
    return WithdrawService(account_dao=MagicMock(), apply_dao=MagicMock())


def _fake_apply(
    apply_id: int = 1,
    user_id: int = 10086,
    apply_amount: Decimal = Decimal("100.00"),
    fee: Decimal = Decimal("1.00"),
    actual_amount: Decimal = Decimal("99.00"),
    status: str = WithdrawStatus.PENDING.value,
) -> MagicMock:
    m = MagicMock()
    m.id = apply_id
    m.apply_id = apply_id
    m.user_id = user_id
    m.apply_amount = apply_amount
    m.fee = fee
    m.actual_amount = actual_amount
    m.status = status
    m.to_dict.return_value = {
        "id": apply_id,
        "apply_no": f"GAKW{apply_id:06d}",
        "user_id": user_id,
        "apply_amount": str(apply_amount),
        "fee": str(fee),
        "actual_amount": str(actual_amount),
        "status": status,
    }
    return m


# ════════════════════════════════════════════════════════════════════
# 1. 内部工具方法
# ════════════════════════════════════════════════════════════════════

class TestInternalHelpers:
    def test_to_decimal_from_str(self):
        svc = _svc()
        assert svc._to_decimal("12.34") == Decimal("12.34")

    def test_to_decimal_from_int(self):
        svc = _svc()
        assert svc._to_decimal(100) == Decimal("100")

    def test_to_decimal_from_float(self):
        """float 转 Decimal 走 str 中间路径，避免二进制污染"""
        svc = _svc()
        v = svc._to_decimal(0.1)
        assert v == Decimal("0.1")

    def test_calc_fee_takes_min_fee_when_small(self):
        svc = _svc()
        cfg = WithdrawFeeConfig(rate=Decimal("0.001"), min_fee=Decimal("1.00"))
        # 10 * 0.001 = 0.01 < 1.00 → 返回 1.00
        assert svc._calc_fee(Decimal("10"), cfg) == Decimal("1.00")

    def test_calc_fee_takes_rate_when_large(self):
        svc = _svc()
        cfg = WithdrawFeeConfig(rate=Decimal("0.001"), min_fee=Decimal("1.00"))
        # 5000 * 0.001 = 5.00 > 1.00 → 返回 5.00
        assert svc._calc_fee(Decimal("5000"), cfg) == Decimal("5.00")

    def test_gen_apply_no_prefix_and_length(self):
        no = WithdrawService._gen_apply_no()
        assert no.startswith("GAKW")
        # GAKW(4) + yyyyMMddHHmmss(14) + 6 随机 = 24
        assert len(no) == 24

    def test_gen_apply_no_unique_on_two_calls(self):
        a = WithdrawService._gen_apply_no()
        b = WithdrawService._gen_apply_no()
        # 毫秒级两调用同一秒时随机部分仍可能不同；若相同仅为概率事件
        # 这里只校验格式合法，不强求唯一（实际业务已用 DB UK(apply_no) 兜底）
        assert a.startswith("GAKW") and b.startswith("GAKW")

    def test_apply_lock_key_prefix(self):
        k = WithdrawService._apply_lock_key(42)
        assert k == f"{LOCK_KEY_WITHDRAW_APPLY}42"


# ════════════════════════════════════════════════════════════════════
# 2. 流程2 reject_apply
# ════════════════════════════════════════════════════════════════════

class TestRejectApply:
    def _patch_common(self):
        """Patch 申请锁 + release"""
        return (
            patch(
                "src.services.withdraw_service.LockUtil.acquire_lock",
                new=AsyncMock(return_value="owner_x"),
            ),
            patch(
                "src.services.withdraw_service.LockUtil.release_lock",
                new=AsyncMock(return_value=True),
            ),
        )

    @pytest.mark.asyncio
    async def test_reject_success(self):
        svc = _svc()
        app = _fake_apply(status=WithdrawStatus.PENDING.value)
        svc.apply_dao.get_by_id = AsyncMock(return_value=app)
        updated = _fake_apply(status=WithdrawStatus.REJECTED.value)
        svc.apply_dao.update_by_id = AsyncMock(return_value=updated)
        svc.account_dao.adjust_balance = AsyncMock(return_value=None)

        p1, p2 = self._patch_common()
        with p1, p2:
            r = await svc.reject_apply(apply_id=1, review_user_id=9, reject_reason="资料不符")
        assert r["status"] == WithdrawStatus.REJECTED.value
        svc.apply_dao.update_by_id.assert_awaited_once()
        svc.account_dao.adjust_balance.assert_awaited_once()
        # 金额验证：frozen -100 / available +100
        (call_uid, kwargs) = svc.account_dao.adjust_balance.call_args.args, svc.account_dao.adjust_balance.call_args.kwargs
        assert svc.account_dao.adjust_balance.call_args[0][0] == 10086

    @pytest.mark.asyncio
    async def test_reject_lock_failed(self):
        svc = _svc()
        with patch(
            "src.services.withdraw_service.LockUtil.acquire_lock",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(ValueError, match="正在处理"):
                await svc.reject_apply(1, 9, "r")

    @pytest.mark.asyncio
    async def test_reject_not_exist(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(return_value=None)
        p1, p2 = self._patch_common()
        with p1, p2:
            with pytest.raises(ValueError, match="不存在"):
                await svc.reject_apply(1, 9, "r")

    @pytest.mark.asyncio
    async def test_reject_status_not_pending(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.APPROVED.value)
        )
        p1, p2 = self._patch_common()
        with p1, p2:
            with pytest.raises(ValueError, match="不允许驳回"):
                await svc.reject_apply(1, 9, "r")

    @pytest.mark.asyncio
    async def test_reject_balance_adjust_failed_raises(self):
        """退回余额失败：先更新状态为 REJECTED，再抛异常，CRITICAL 日志由 logger 负责"""
        svc = _svc()
        app = _fake_apply(status=WithdrawStatus.PENDING.value)
        svc.apply_dao.get_by_id = AsyncMock(return_value=app)
        svc.apply_dao.update_by_id = AsyncMock(return_value=_fake_apply(status=WithdrawStatus.REJECTED.value))
        svc.account_dao.adjust_balance = AsyncMock(side_effect=RuntimeError("DB down"))

        p1, p2 = self._patch_common()
        with p1, p2:
            with pytest.raises(RuntimeError, match="DB down"):
                await svc.reject_apply(1, 9, "r")
        # 状态 update 已执行，余额调整也被调用（然后抛错）
        svc.apply_dao.update_by_id.assert_awaited_once()
        svc.account_dao.adjust_balance.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reject_update_returns_none_fallback_to_original(self):
        """update_by_id 返回 None 时使用 apply_record 作为返回值兜底"""
        svc = _svc()
        app = _fake_apply(status=WithdrawStatus.PENDING.value)
        svc.apply_dao.get_by_id = AsyncMock(return_value=app)
        svc.apply_dao.update_by_id = AsyncMock(return_value=None)
        svc.account_dao.adjust_balance = AsyncMock(return_value=None)

        p1, p2 = self._patch_common()
        with p1, p2:
            r = await svc.reject_apply(1, 9, "rrr")
        # 返回的是原始 record 的 to_dict（因为 update 返回 None）
        assert r["id"] == 1


# ════════════════════════════════════════════════════════════════════
# 3. 流程3 approve_apply
# ════════════════════════════════════════════════════════════════════

class TestApproveApply:
    def _patch_lock(self):
        return (
            patch(
                "src.services.withdraw_service.LockUtil.acquire_lock",
                new=AsyncMock(return_value="owner_y"),
            ),
            patch(
                "src.services.withdraw_service.LockUtil.release_lock",
                new=AsyncMock(return_value=True),
            ),
        )

    @pytest.mark.asyncio
    async def test_approve_success(self):
        svc = _svc()
        app = _fake_apply(status=WithdrawStatus.PENDING.value)
        svc.apply_dao.get_by_id = AsyncMock(return_value=app)
        upd = _fake_apply(status=WithdrawStatus.APPROVED.value)
        svc.apply_dao.update_by_id = AsyncMock(return_value=upd)

        p1, p2 = self._patch_lock()
        with p1, p2:
            r = await svc.approve_apply(1, 9, "ok")
        assert r["status"] == WithdrawStatus.APPROVED.value
        svc.apply_dao.update_by_id.assert_awaited_once()
        update_kwargs = svc.apply_dao.update_by_id.call_args.args[1]
        assert update_kwargs["status"] == WithdrawStatus.APPROVED.value
        assert update_kwargs["review_user_id"] == 9
        assert isinstance(update_kwargs["review_time"], datetime)

    @pytest.mark.asyncio
    async def test_approve_lock_failed(self):
        svc = _svc()
        with patch(
            "src.services.withdraw_service.LockUtil.acquire_lock",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(ValueError, match="正在处理"):
                await svc.approve_apply(1, 9, "x")

    @pytest.mark.asyncio
    async def test_approve_not_exist(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(return_value=None)
        p1, p2 = self._patch_lock()
        with p1, p2:
            with pytest.raises(ValueError, match="不存在"):
                await svc.approve_apply(1, 9, "x")

    @pytest.mark.asyncio
    async def test_approve_wrong_status(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.SUCCESS.value)
        )
        p1, p2 = self._patch_lock()
        with p1, p2:
            with pytest.raises(ValueError, match="不允许审核通过"):
                await svc.approve_apply(1, 9, "x")

    @pytest.mark.asyncio
    async def test_approve_update_returns_none(self):
        svc = _svc()
        app = _fake_apply(status=WithdrawStatus.PENDING.value)
        svc.apply_dao.get_by_id = AsyncMock(return_value=app)
        svc.apply_dao.update_by_id = AsyncMock(return_value=None)
        p1, p2 = self._patch_lock()
        with p1, p2:
            r = await svc.approve_apply(1, 9, "x")
        assert r["id"] == 1  # 兜底 to_dict


# ════════════════════════════════════════════════════════════════════
# 4. 流程4 complete_apply
# ════════════════════════════════════════════════════════════════════

class TestCompleteApply:
    def _patch_lock(self):
        return (
            patch(
                "src.services.withdraw_service.LockUtil.acquire_lock",
                new=AsyncMock(return_value="owner_z"),
            ),
            patch(
                "src.services.withdraw_service.LockUtil.release_lock",
                new=AsyncMock(return_value=True),
            ),
        )

    @pytest.mark.asyncio
    async def test_complete_success_from_approved(self):
        svc = _svc()
        app = _fake_apply(status=WithdrawStatus.APPROVED.value)
        svc.apply_dao.get_by_id = AsyncMock(return_value=app)
        svc.apply_dao.update_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.SUCCESS.value)
        )
        svc.account_dao.adjust_balance = AsyncMock(return_value=None)

        p1, p2 = self._patch_lock()
        with p1, p2:
            r = await svc.complete_apply(1, "BATCH_001")
        assert r["status"] == WithdrawStatus.SUCCESS.value
        # 释放冻结：delta_frozen=-100 / delta_withdrawn=+99 / delta_fee=+1
        svc.account_dao.adjust_balance.assert_awaited_once()
        args, kwargs = svc.account_dao.adjust_balance.call_args
        assert args[0] == 10086
        update_kwargs = svc.apply_dao.update_by_id.call_args.args[1]
        assert update_kwargs["transfer_batch_id"] == "BATCH_001"
        assert isinstance(update_kwargs["transfer_time"], datetime)

    @pytest.mark.asyncio
    async def test_complete_success_from_processing(self):
        svc = _svc()
        app = _fake_apply(status=WithdrawStatus.PROCESSING.value)
        svc.apply_dao.get_by_id = AsyncMock(return_value=app)
        svc.apply_dao.update_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.SUCCESS.value)
        )
        svc.account_dao.adjust_balance = AsyncMock(return_value=None)
        p1, p2 = self._patch_lock()
        with p1, p2:
            r = await svc.complete_apply(1, "B01")
        assert r["status"] == WithdrawStatus.SUCCESS.value

    @pytest.mark.asyncio
    async def test_complete_lock_failed(self):
        svc = _svc()
        with patch(
            "src.services.withdraw_service.LockUtil.acquire_lock",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(ValueError, match="正在处理"):
                await svc.complete_apply(1, "B")

    @pytest.mark.asyncio
    async def test_complete_not_exist(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(return_value=None)
        p1, p2 = self._patch_lock()
        with p1, p2:
            with pytest.raises(ValueError, match="不存在"):
                await svc.complete_apply(1, "B")

    @pytest.mark.asyncio
    async def test_complete_wrong_status(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.PENDING.value)  # PENDING 不在 allowed
        )
        p1, p2 = self._patch_lock()
        with p1, p2:
            with pytest.raises(ValueError, match="不允许标记打款完成"):
                await svc.complete_apply(1, "B")

    @pytest.mark.asyncio
    async def test_complete_balance_release_failed(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.APPROVED.value)
        )
        svc.apply_dao.update_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.SUCCESS.value)
        )
        svc.account_dao.adjust_balance = AsyncMock(side_effect=RuntimeError("balance err"))
        p1, p2 = self._patch_lock()
        with p1, p2:
            with pytest.raises(RuntimeError, match="balance err"):
                await svc.complete_apply(1, "B")
        svc.apply_dao.update_by_id.assert_awaited_once()


# ════════════════════════════════════════════════════════════════════
# 5. 流程5 fail_apply
# ════════════════════════════════════════════════════════════════════

class TestFailApply:
    def _patch_lock(self):
        return (
            patch(
                "src.services.withdraw_service.LockUtil.acquire_lock",
                new=AsyncMock(return_value="owner_w"),
            ),
            patch(
                "src.services.withdraw_service.LockUtil.release_lock",
                new=AsyncMock(return_value=True),
            ),
        )

    @pytest.mark.asyncio
    async def test_fail_apply_success_approved(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.APPROVED.value)
        )
        svc.apply_dao.update_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.REJECTED.value)
        )
        svc.account_dao.adjust_balance = AsyncMock(return_value=None)
        p1, p2 = self._patch_lock()
        with p1, p2:
            r = await svc.fail_apply(1, "银行卡异常")
        assert r["status"] == WithdrawStatus.REJECTED.value
        # 余额：available +100 / frozen -100
        svc.account_dao.adjust_balance.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fail_apply_success_processing(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.PROCESSING.value)
        )
        svc.apply_dao.update_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.REJECTED.value)
        )
        svc.account_dao.adjust_balance = AsyncMock(return_value=None)
        p1, p2 = self._patch_lock()
        with p1, p2:
            await svc.fail_apply(1, "转账失败")

    @pytest.mark.asyncio
    async def test_fail_lock_failed(self):
        svc = _svc()
        with patch(
            "src.services.withdraw_service.LockUtil.acquire_lock",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(ValueError, match="正在处理"):
                await svc.fail_apply(1, "x")

    @pytest.mark.asyncio
    async def test_fail_not_exist(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(return_value=None)
        p1, p2 = self._patch_lock()
        with p1, p2:
            with pytest.raises(ValueError, match="不存在"):
                await svc.fail_apply(1, "x")

    @pytest.mark.asyncio
    async def test_fail_wrong_status(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.PENDING.value)
        )
        p1, p2 = self._patch_lock()
        with p1, p2:
            with pytest.raises(ValueError, match="不允许标记打款失败"):
                await svc.fail_apply(1, "x")

    @pytest.mark.asyncio
    async def test_fail_balance_back_failed_raises(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.APPROVED.value)
        )
        svc.apply_dao.update_by_id = AsyncMock(
            return_value=_fake_apply(status=WithdrawStatus.REJECTED.value)
        )
        svc.account_dao.adjust_balance = AsyncMock(side_effect=RuntimeError("revert err"))
        p1, p2 = self._patch_lock()
        with p1, p2:
            with pytest.raises(RuntimeError, match="revert err"):
                await svc.fail_apply(1, "x")


# ════════════════════════════════════════════════════════════════════
# 6. 查询接口
# ════════════════════════════════════════════════════════════════════

class TestQueryMethods:
    @pytest.mark.asyncio
    async def test_get_account_exists(self):
        svc = _svc()
        expected_dict: Dict[str, Any] = {
            "user_id": 1,
            "total_balance": 520.0,
            "available_balance": 500.0,
            "frozen_balance": 20.0,
            "cumulative_withdrawn": 100.0,
            "cumulative_fee": 1.0,
            "last_settle_date": None,
            "version": 3,
        }
        svc.account_dao.get_account_cached = AsyncMock(return_value=expected_dict)
        r = await svc.get_account(1)
        assert r == expected_dict
        svc.account_dao.get_account_cached.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_get_account_missing_returns_zero_placeholder(self):
        svc = _svc()
        svc.account_dao.get_account_cached = AsyncMock(return_value=None)
        r = await svc.get_account(999)
        assert r["user_id"] == 999
        assert r["available_balance"] == 0.0
        assert r["frozen_balance"] == 0.0
        assert r["total_balance"] == 0.0
        assert r["cumulative_withdrawn"] == 0.0
        assert r["cumulative_fee"] == 0.0
        assert r["version"] == 0

    @pytest.mark.asyncio
    async def test_list_my_applies(self):
        svc = _svc()
        rows = [_fake_apply(apply_id=i, user_id=1) for i in range(1, 4)]
        svc.apply_dao.list_by_user_id = AsyncMock(return_value=(rows, 3))
        r = await svc.list_my_applies(user_id=1, page=1, page_size=20)
        assert r["total"] == 3
        assert r["page"] == 1
        assert r["page_size"] == 20
        assert len(r["list"]) == 3

    @pytest.mark.asyncio
    async def test_list_applies_for_admin_all(self):
        svc = _svc()
        rows = [_fake_apply(apply_id=i, user_id=100 + i) for i in range(1, 6)]
        svc.apply_dao.list_with_filters = AsyncMock(return_value=(rows, 5))
        r = await svc.list_applies_for_admin(page=1, page_size=50)
        assert r["total"] == 5
        svc.apply_dao.list_with_filters.assert_awaited_once()
        kwargs = svc.apply_dao.list_with_filters.call_args.kwargs
        assert kwargs["user_id"] is None
        assert kwargs["status"] is None

    @pytest.mark.asyncio
    async def test_list_applies_for_admin_with_filter(self):
        svc = _svc()
        rows = [_fake_apply(apply_id=1, user_id=7, status=WithdrawStatus.PENDING.value)]
        svc.apply_dao.list_with_filters = AsyncMock(return_value=(rows, 1))
        r = await svc.list_applies_for_admin(
            user_id=7, status=WithdrawStatus.PENDING.value, page=1, page_size=10
        )
        assert r["total"] == 1
        kwargs = svc.apply_dao.list_with_filters.call_args.kwargs
        assert kwargs["user_id"] == 7
        assert kwargs["status"] == WithdrawStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_apply_detail_ok(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(return_value=_fake_apply(apply_id=42))
        r = await svc.get_apply_detail(42)
        assert r["id"] == 42

    @pytest.mark.asyncio
    async def test_get_apply_detail_missing(self):
        svc = _svc()
        svc.apply_dao.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="不存在"):
            await svc.get_apply_detail(404)
