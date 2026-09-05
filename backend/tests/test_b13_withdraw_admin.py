# @ai-generated
"""
B13-1 提现管理后台单元测试
覆盖：
1. B13WithdrawAdminService 所有方法：list_withdraws, get_withdraw_detail, get_review_logs, review_withdraw, update_transfer_info
2. 正常路径 + 异常路径边界场景全覆盖
3. 覆盖率目标 ≥90%
"""
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from sqlalchemy import select

from src.models.business.user_withdraw_apply_model import UserWithdrawApply
from src.services.b13_withdraw_admin_service import B13WithdrawAdminService


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_withdraw_apply(
    apply_id=1,
    status="PENDING",
    user_id=101,
    apply_no="W20260801001",
):
    """构造提现申请 mock 对象"""
    item = MagicMock()
    item.id = apply_id
    item.apply_no = apply_no
    item.user_id = user_id
    item.apply_amount = 100.00
    item.fee = 1.00
    item.actual_amount = 99.00
    item.status = status
    item.review_user_id = 0 if status == "PENDING" else 1
    item.review_remark = "" if status == "PENDING" else "审核通过"
    item.review_time = None if status == "PENDING" else datetime(2026, 1, 2, 10, 0, 0)
    item.transfer_time = None
    item.transfer_batch_id = ""
    item.reject_reason = ""
    item.remark = ""
    item.create_time = datetime(2026, 1, 1, 10, 0, 0)
    return item


def _make_review_log(log_id=1, apply_id=1, action="APPROVE", from_status="PENDING", to_status="APPROVED"):
    """构造审核日志 mock 对象"""
    log = MagicMock()
    log.id = log_id
    log.apply_id = apply_id
    log.from_status = from_status
    log.to_status = to_status
    log.action = action
    log.operator_id = 1
    log.remark = "审核通过"
    log.transfer_batch_id = ""
    log.create_time = datetime(2026, 1, 2, 10, 0, 0)
    return log


def _make_session_cm():
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


# ══════════════════════════════════════════════════════
# 1. 提现列表查询测试
# ══════════════════════════════════════════════════════


class TestB13WithdrawAdminList:
    """提现列表查询测试"""

    @pytest.mark.asyncio
    async def test_list_withdraws_empty(self):
        """无数据 → 返回空列表，0 总数"""
        session, cm = _make_session_cm()

        count_result = MagicMock()
        count_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=count_result)

        mock_dao = AsyncMock()
        mock_dao._active_query.return_value = select(UserWithdrawApply)

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            items, total = await B13WithdrawAdminService.list_withdraws()
        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_list_withdraws_with_user_filter(self):
        """按用户ID筛选 → 正常返回"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="PENDING", user_id=101)

        mock_dao = AsyncMock()
        mock_dao._active_query.return_value = select(UserWithdrawApply)

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [item]
        session.execute = AsyncMock(side_effect=[count_result, items_result])

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            items, total = await B13WithdrawAdminService.list_withdraws(
                user_id=101, page=1, page_size=20
            )
        assert total == 1
        assert len(items) == 1
        assert items[0]["id"] == 1
        assert items[0]["user_id"] == 101

    @pytest.mark.asyncio
    async def test_list_withdraws_with_status_filter(self):
        """按状态筛选 → 正常返回"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="PENDING")

        mock_dao = AsyncMock()
        mock_dao._active_query.return_value = select(UserWithdrawApply)

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [item]
        session.execute = AsyncMock(side_effect=[count_result, items_result])

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            items, total = await B13WithdrawAdminService.list_withdraws(status="PENDING")
        assert total == 1
        assert items[0]["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_list_withdraws_with_time_range(self):
        """按时间范围筛选 → 正常返回"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply()

        mock_dao = AsyncMock()
        mock_dao._active_query.return_value = select(UserWithdrawApply)

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [item]
        session.execute = AsyncMock(side_effect=[count_result, items_result])

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            items, total = await B13WithdrawAdminService.list_withdraws(
                start_time=datetime(2026, 1, 1), end_time=datetime(2026, 2, 1)
            )
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_withdraws_invalid_page(self):
        """非法页码 → 自动修正为默认值"""
        session, cm = _make_session_cm()

        count_result = MagicMock()
        count_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=count_result)

        mock_dao = AsyncMock()
        mock_dao._active_query.return_value = select(UserWithdrawApply)

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            # page=0 应修正为 1, page_size=0 应修正为 20
            items, total = await B13WithdrawAdminService.list_withdraws(page=0, page_size=0)
        assert total == 0
        assert items == []


# ══════════════════════════════════════════════════════
# 2. 提现详情测试
# ══════════════════════════════════════════════════════


class TestB13WithdrawAdminDetail:
    """提现详情测试"""

    @pytest.mark.asyncio
    async def test_get_withdraw_detail_not_found(self):
        """提现申请不存在 → 返回 None"""
        session, cm = _make_session_cm()

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = None

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B13WithdrawAdminService.get_withdraw_detail(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_withdraw_detail_success(self):
        """提现申请存在 → 返回详情"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="PENDING")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B13WithdrawAdminService.get_withdraw_detail(1)
        assert result is not None
        assert result["id"] == 1
        assert result["status"] == "PENDING"
        # detail=True should include transfer_batch_id
        assert "transfer_batch_id" in result


# ══════════════════════════════════════════════════════
# 3. 审核日志测试
# ══════════════════════════════════════════════════════


class TestB13WithdrawAdminReviewLogs:
    """审核日志测试"""

    @pytest.mark.asyncio
    async def test_get_review_logs_empty(self):
        """无日志 → 返回空列表"""
        session, cm = _make_session_cm()

        mock_log_dao = AsyncMock()
        mock_log_dao.list_by_apply_id.return_value = ([], 0)

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.WithdrawReviewLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_log_cls.return_value = mock_log_dao

            items, total = await B13WithdrawAdminService.get_review_logs(apply_id=1)
        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_get_review_logs_success(self):
        """有日志 → 返回序列化结果"""
        session, cm = _make_session_cm()
        log = _make_review_log(log_id=1, apply_id=1)

        mock_log_dao = AsyncMock()
        mock_log_dao.list_by_apply_id.return_value = ([log], 1)

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.WithdrawReviewLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_log_cls.return_value = mock_log_dao

            items, total = await B13WithdrawAdminService.get_review_logs(apply_id=1)
        assert total == 1
        assert len(items) == 1
        assert items[0]["apply_id"] == 1
        assert items[0]["action"] == "APPROVE"

    @pytest.mark.asyncio
    async def test_get_review_logs_with_pagination(self):
        """分页参数正常传递"""
        session, cm = _make_session_cm()
        log = _make_review_log(log_id=1, apply_id=1)

        mock_log_dao = AsyncMock()
        mock_log_dao.list_by_apply_id.return_value = ([log], 1)

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.WithdrawReviewLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_log_cls.return_value = mock_log_dao

            items, total = await B13WithdrawAdminService.get_review_logs(
                apply_id=1, page=1, page_size=10
            )
        assert total == 1
        mock_log_dao.list_by_apply_id.assert_called_with(apply_id=1, page=1, page_size=10)


# ══════════════════════════════════════════════════════
# 4. 审核操作测试
# ══════════════════════════════════════════════════════


class TestB13WithdrawAdminReview:
    """提现审核操作测试"""

    @pytest.mark.asyncio
    async def test_review_approve_success(self):
        """审核通过成功 → 状态变为 APPROVED"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="PENDING")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item
        updated_item = _make_withdraw_apply(apply_id=1, status="APPROVED")
        updated_item.review_user_id = 1
        updated_item.review_time = datetime.now()
        updated_item.review_remark = "审核通过"
        mock_dao.update_by_id.return_value = updated_item

        mock_log_dao = AsyncMock()
        mock_log_dao.create = AsyncMock()

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls, \
             patch("src.services.b13_withdraw_admin_service.WithdrawReviewLogDAO") as mock_log_cls, \
             patch("src.services.b13_withdraw_admin_service.AuditLogger.log") as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            result = await B13WithdrawAdminService.review_withdraw(
                apply_id=1, action="approve",
                review_remark="审核通过", reject_reason="",
                operator_id=1, operator_name="admin",
            )

        assert result["status"] == "APPROVED"
        mock_audit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_reject_success(self):
        """审核驳回成功 → 状态变为 REJECTED"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="PENDING")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item
        updated_item = _make_withdraw_apply(apply_id=1, status="REJECTED")
        updated_item.reject_reason = "信息有误"
        mock_dao.update_by_id.return_value = updated_item

        mock_log_dao = AsyncMock()
        mock_log_dao.create = AsyncMock()

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls, \
             patch("src.services.b13_withdraw_admin_service.WithdrawReviewLogDAO") as mock_log_cls, \
             patch("src.services.b13_withdraw_admin_service.AuditLogger.log") as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            result = await B13WithdrawAdminService.review_withdraw(
                apply_id=1, action="reject",
                review_remark="", reject_reason="信息有误",
                operator_id=1, operator_name="admin",
            )

        assert result["status"] == "REJECTED"
        mock_audit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_not_found(self):
        """提现申请不存在 → ValueError"""
        session, cm = _make_session_cm()

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = None

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="不存在"):
                await B13WithdrawAdminService.review_withdraw(
                    apply_id=999, action="approve",
                    review_remark="", reject_reason="",
                    operator_id=1, operator_name="admin",
                )

    @pytest.mark.asyncio
    async def test_review_invalid_action(self):
        """无效审核动作 → ValueError"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="PENDING")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="无效的审核动作"):
                await B13WithdrawAdminService.review_withdraw(
                    apply_id=1, action="invalid_action",
                    review_remark="", reject_reason="",
                    operator_id=1, operator_name="admin",
                )

    @pytest.mark.asyncio
    async def test_review_approve_wrong_status(self):
        """非 PENDING 状态审核通过 → ValueError"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="APPROVED")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="不允许审核通过"):
                await B13WithdrawAdminService.review_withdraw(
                    apply_id=1, action="approve",
                    review_remark="", reject_reason="",
                    operator_id=1, operator_name="admin",
                )

    @pytest.mark.asyncio
    async def test_review_reject_wrong_status(self):
        """终态驳回 → ValueError"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="REJECTED")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="不允许驳回"):
                await B13WithdrawAdminService.review_withdraw(
                    apply_id=1, action="reject",
                    review_remark="", reject_reason="",
                    operator_id=1, operator_name="admin",
                )

    @pytest.mark.asyncio
    async def test_review_update_fails(self):
        """DAO 更新返回 None → ValueError"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="PENDING")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item
        mock_dao.update_by_id.return_value = None

        mock_log_dao = AsyncMock()

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls, \
             patch("src.services.b13_withdraw_admin_service.WithdrawReviewLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            with pytest.raises(ValueError, match="更新提现申请失败"):
                await B13WithdrawAdminService.review_withdraw(
                    apply_id=1, action="approve",
                    review_remark="", reject_reason="",
                    operator_id=1, operator_name="admin",
                )


# ══════════════════════════════════════════════════════
# 5. 转账信息更新测试
# ══════════════════════════════════════════════════════


class TestB13WithdrawAdminTransfer:
    """转账信息更新测试"""

    @pytest.mark.asyncio
    async def test_update_transfer_success(self):
        """转账成功 → 状态变为 PROCESSING"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="APPROVED")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item
        updated_item = _make_withdraw_apply(apply_id=1, status="PROCESSING")
        updated_item.transfer_batch_id = "BATCH001"
        updated_item.transfer_time = datetime.now()
        mock_dao.update_by_id.return_value = updated_item

        mock_log_dao = AsyncMock()
        mock_log_dao.create = AsyncMock()

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls, \
             patch("src.services.b13_withdraw_admin_service.WithdrawReviewLogDAO") as mock_log_cls, \
             patch("src.services.b13_withdraw_admin_service.AuditLogger.log") as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            result = await B13WithdrawAdminService.update_transfer_info(
                apply_id=1, transfer_batch_id="BATCH001",
                operator_id=1, operator_name="admin",
            )

        assert result["status"] == "PROCESSING"
        mock_audit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_transfer_not_found(self):
        """提现申请不存在 → ValueError"""
        session, cm = _make_session_cm()

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = None

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="不存在"):
                await B13WithdrawAdminService.update_transfer_info(
                    apply_id=999, transfer_batch_id="B001",
                    operator_id=1, operator_name="admin",
                )

    @pytest.mark.asyncio
    async def test_update_transfer_wrong_status(self):
        """非 APPROVED/PROCESSING 状态 → ValueError"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="PENDING")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="不允许更新转账信息"):
                await B13WithdrawAdminService.update_transfer_info(
                    apply_id=1, transfer_batch_id="B001",
                    operator_id=1, operator_name="admin",
                )

    @pytest.mark.asyncio
    async def test_update_transfer_update_fails(self):
        """DAO 更新返回 None → ValueError"""
        session, cm = _make_session_cm()
        item = _make_withdraw_apply(apply_id=1, status="APPROVED")

        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = item
        mock_dao.update_by_id.return_value = None

        mock_log_dao = AsyncMock()

        with patch("src.services.b13_withdraw_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_withdraw_admin_service.UserWithdrawApplyDAO") as mock_dao_cls, \
             patch("src.services.b13_withdraw_admin_service.WithdrawReviewLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            with pytest.raises(ValueError, match="更新转账信息失败"):
                await B13WithdrawAdminService.update_transfer_info(
                    apply_id=1, transfer_batch_id="B001",
                    operator_id=1, operator_name="admin",
                )


# ══════════════════════════════════════════════════════
# 6. 序列化方法测试
# ══════════════════════════════════════════════════════


class TestB13WithdrawAdminSerialization:
    """序列化方法测试"""

    def test_to_withdraw_dict_basic(self):
        """基本字段序列化"""
        item = _make_withdraw_apply(apply_id=1, status="PENDING")
        result = B13WithdrawAdminService._to_withdraw_dict(item, detail=False)
        assert result["id"] == 1
        assert result["status"] == "PENDING"
        assert "transfer_batch_id" not in result

    def test_to_withdraw_dict_detail(self):
        """详情模式包含 transfer_batch_id"""
        item = _make_withdraw_apply(apply_id=1, status="PENDING")
        item.transfer_batch_id = "BATCH001"
        result = B13WithdrawAdminService._to_withdraw_dict(item, detail=True)
        assert result["transfer_batch_id"] == "BATCH001"

    def test_to_withdraw_dict_none_fields(self):
        """空字段处理"""
        item = _make_withdraw_apply(apply_id=1, status="PENDING")
        item.apply_amount = None
        item.fee = None
        item.actual_amount = None
        item.review_time = None
        item.create_time = None

        result = B13WithdrawAdminService._to_withdraw_dict(item)
        assert result["apply_amount"] == "0.00"
        assert result["fee"] == "0.00"
        assert result["actual_amount"] == "0.00"
        assert result["review_time"] is None
        assert result["create_time"] is None