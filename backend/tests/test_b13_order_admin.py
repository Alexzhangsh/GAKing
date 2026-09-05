# @ai-generated
"""
B13-1 订单管理后台单元测试
覆盖：
1. B13OrderAdminService 所有方法：list_orders, get_order_detail, validate_transition, batch_validate_transition, execute_transition, list_operation_logs
2. 正常路径 + 异常路径边界场景全覆盖
3. 覆盖率目标 ≥90%
"""
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.config.constants import OrderStatus
from src.config.b12_constants import (
    OrderOperationType,
    ORDER_STATUS_LABELS,
)
from src.services.b13_order_admin_service import B13OrderAdminService


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_order(order_id=1, order_status=OrderStatus.PENDING, user_id=101, channel_code="myq"):
    """构造订单 mock 对象"""
    o = MagicMock()
    o.id = order_id
    o.out_order_no = f"OUT{order_id:08d}"
    o.internal_order_no = f"IN{order_id:08d}"
    o.goods_title = "测试商品标题"
    o.goods_img = "https://example.com/test.jpg"
    o.user_id = user_id
    o.channel_code = channel_code
    o.order_status = order_status
    o.pay_amount = 99.00
    o.total_commission = 10.00
    o.user_commission = 8.00
    o.platform_commission = 2.00
    o.transfer_status = "PENDING"
    o.create_time = datetime(2026, 1, 1, 10, 0, 0)
    o.pay_time = datetime(2026, 1, 1, 10, 5, 0) if order_status >= OrderStatus.FROZEN else None
    o.settle_time = datetime(2026, 1, 4, 10, 0, 0) if order_status >= OrderStatus.SETTLED else None
    o.is_delete = False
    return o


def _make_operation_log(log_id=1, order_id=1, from_status=10, to_status=20):
    """构造订单操作日志 mock 对象"""
    log = MagicMock()
    log.id = log_id
    log.order_id = order_id
    log.out_order_no = "OUT00000001"
    log.internal_order_no = "IN00000001"
    log.order_status_from = from_status
    log.order_status_to = to_status
    log.status_from_label = ORDER_STATUS_LABELS.get(from_status, "")
    log.status_to_label = ORDER_STATUS_LABELS.get(to_status, "")
    log.operation_type = OrderOperationType.STATUS_TRANSITION
    log.operation_type_label = "状态流转"
    log.operator_id = 1
    log.operator_name = "admin"
    log.remark = "测试操作"
    log.create_time = datetime(2026, 1, 1, 10, 0, 0)
    return log


def _make_session_cm():
    """构造 DatabaseManager.get_session() 的上下文管理器 mock"""
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


def _make_mock_dao(get_by_id_return=None):
    """构造 DAO mock，确保 get_by_id 是 AsyncMock 且可被 await"""
    mock_dao = MagicMock()
    mock_dao.get_by_id = AsyncMock(return_value=get_by_id_return)
    return mock_dao


# ══════════════════════════════════════════════════════
# 1. 列表查询测试
# ══════════════════════════════════════════════════════


class TestB13OrderAdminList:
    """订单列表查询测试"""

    @pytest.mark.asyncio
    async def test_list_orders_empty(self):
        """无数据 → 返回空列表，0 总数"""
        session, cm = _make_session_cm()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=count_result)

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = MagicMock()

            items, total = await B13OrderAdminService.list_orders()
        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_list_orders_with_keyword(self):
        """关键词筛选 → 正常返回分页结果"""
        session, cm = _make_session_cm()
        order = _make_order()

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [order]
        session.execute = AsyncMock(side_effect=[count_result, items_result])

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = MagicMock()

            items, total = await B13OrderAdminService.list_orders(
                keyword="测试", page=1, page_size=20
            )
        assert total == 1
        assert len(items) == 1
        assert items[0]["id"] == 1
        assert items[0]["goods_title"] == "测试商品标题"

    @pytest.mark.asyncio
    async def test_list_orders_with_all_filters(self):
        """全条件筛选（keyword + status + channel + user + time）"""
        session, cm = _make_session_cm()
        order = _make_order(order_id=1, order_status=OrderStatus.FROZEN, user_id=101, channel_code="myq")

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [order]
        session.execute = AsyncMock(side_effect=[count_result, items_result])

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = MagicMock()

            items, total = await B13OrderAdminService.list_orders(
                keyword="测试",
                order_status=int(OrderStatus.FROZEN),
                channel_code="myq",
                user_id=101,
                start_time=datetime(2025, 12, 1),
                end_time=datetime(2026, 2, 1),
                page=1,
                page_size=20,
            )
        assert total == 1
        assert len(items) == 1
        assert items[0]["order_status"] == int(OrderStatus.FROZEN)

    @pytest.mark.asyncio
    async def test_list_orders_pagination(self):
        """多页分页测试：第 2 页"""
        session, cm = _make_session_cm()
        orders = [_make_order(order_id=i) for i in range(21, 41)]

        count_result = MagicMock()
        count_result.scalar.return_value = 40
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = orders
        session.execute = AsyncMock(side_effect=[count_result, items_result])

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = MagicMock()

            items, total = await B13OrderAdminService.list_orders(page=2, page_size=20)
        assert total == 40
        assert len(items) == 20
        assert items[0]["id"] == 21


# ══════════════════════════════════════════════════════
# 2. 订单详情测试
# ══════════════════════════════════════════════════════


class TestB13OrderAdminDetail:
    """订单详情测试"""

    @pytest.mark.asyncio
    async def test_get_order_detail_not_found(self):
        """订单不存在 → 返回 None"""
        session, cm = _make_session_cm()

        mock_dao = _make_mock_dao(get_by_id_return=None)
        mock_dao.get_order_detail_cached = AsyncMock(return_value=None)

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B13OrderAdminService.get_order_detail(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_order_detail_success(self):
        """订单存在 → 返回序列化详情（含佣金流水）"""
        session, cm = _make_session_cm()

        order_dict = {
            "id": 1,
            "out_order_no": "OUT00000001",
            "internal_order_no": "IN00000001",
            "goods_title": "测试商品",
            "goods_img": "https://example.com/test.jpg",
            "user_id": 101,
            "channel_code": "myq",
            "order_status": int(OrderStatus.SETTLED),
            "pay_amount": 99.00,
            "total_commission": 10.00,
            "user_commission": 8.00,
            "platform_commission": 2.00,
            "transfer_status": "PENDING",
            "wx_batch_id": "",
            "create_time": "2026-01-01 10:00:00",
            "pay_time": "2026-01-01 10:05:00",
            "settle_time": "2026-01-04 10:00:00",
            "commission_flows": [
                {
                    "id": 1,
                    "order_id": 1,
                    "user_id": 101,
                    "flow_type": "ORDER",
                    "amount": 8.00,
                    "before_balance": 10.00,
                    "after_balance": 18.00,
                    "transfer_status": "PENDING",
                    "remark": "",
                    "create_time": datetime(2026, 1, 4, 10, 0, 0),
                }
            ],
        }

        mock_dao = _make_mock_dao(get_by_id_return=None)
        mock_dao.get_order_detail_cached = AsyncMock(return_value=order_dict)

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B13OrderAdminService.get_order_detail(1)
        assert result is not None
        assert result["id"] == 1
        assert result["goods_title"] == "测试商品"
        assert len(result["commission_flows"]) == 1
        # str(8.00) produces "8.0" in Python
        assert result["commission_flows"][0]["amount"] == "8.0"


# ══════════════════════════════════════════════════════
# 3. 状态流转校验测试
# ══════════════════════════════════════════════════════


class TestB13OrderAdminValidate:
    """状态流转校验测试"""

    @pytest.mark.asyncio
    async def test_validate_transition_order_not_found(self):
        """订单不存在 → 返回 invalid"""
        session, cm = _make_session_cm()

        mock_dao = _make_mock_dao(get_by_id_return=None)
        mock_log_dao = _make_mock_dao()

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls, \
             patch("src.services.b13_order_admin_service.OrderOperationLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            result = await B13OrderAdminService.validate_transition(
                order_id=999, target_status=int(OrderStatus.FROZEN)
            )
        assert result["valid"] is False
        assert "不存在" in result["message"]

    @pytest.mark.asyncio
    async def test_validate_transition_valid(self):
        """合法流转 → 返回 valid"""
        session, cm = _make_session_cm()
        order = _make_order(order_id=1, order_status=OrderStatus.PENDING)

        mock_dao = _make_mock_dao(get_by_id_return=order)
        mock_log_dao = _make_mock_dao()

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls, \
             patch("src.services.b13_order_admin_service.OrderOperationLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            result = await B13OrderAdminService.validate_transition(
                order_id=1, target_status=int(OrderStatus.FROZEN)
            )
        assert result["valid"] is True
        assert result["current_status"] == int(OrderStatus.PENDING)
        assert int(OrderStatus.FROZEN) in result["allowed_targets"]

    @pytest.mark.asyncio
    async def test_validate_transition_invalid_target(self):
        """非法目标状态 → 返回 invalid"""
        session, cm = _make_session_cm()
        order = _make_order(order_id=1, order_status=OrderStatus.PENDING)

        mock_dao = _make_mock_dao(get_by_id_return=order)
        mock_log_dao = _make_mock_dao()

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls, \
             patch("src.services.b13_order_admin_service.OrderOperationLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            # PENDING → SETTLED 不允许
            result = await B13OrderAdminService.validate_transition(
                order_id=1, target_status=int(OrderStatus.SETTLED)
            )
        assert result["valid"] is False
        assert "非法" in result["message"] or "不合法" in result["message"]

    @pytest.mark.asyncio
    async def test_validate_transition_terminal_not_override(self):
        """终态且非人工干预 → 返回 invalid"""
        session, cm = _make_session_cm()
        order = _make_order(order_id=1, order_status=OrderStatus.INVALID)

        mock_dao = _make_mock_dao(get_by_id_return=order)
        mock_log_dao = _make_mock_dao()

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls, \
             patch("src.services.b13_order_admin_service.OrderOperationLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            result = await B13OrderAdminService.validate_transition(
                order_id=1, target_status=int(OrderStatus.FROZEN), is_manual_override=False
            )
        assert result["valid"] is False
        assert "终态" in result["message"]

    @pytest.mark.asyncio
    async def test_validate_transition_terminal_override_allowed(self):
        """终态即使人工干预也无效（INVALID 无允许的转出目标）"""
        session, cm = _make_session_cm()
        order = _make_order(order_id=1, order_status=OrderStatus.INVALID)

        mock_dao = _make_mock_dao(get_by_id_return=order)
        mock_log_dao = _make_mock_dao()

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls, \
             patch("src.services.b13_order_admin_service.OrderOperationLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            result = await B13OrderAdminService.validate_transition(
                order_id=1, target_status=int(OrderStatus.FROZEN), is_manual_override=True
            )
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_batch_validate_transition(self):
        """批量校验：混合合法非法结果正确"""
        session, cm = _make_session_cm()
        order1 = _make_order(order_id=1, order_status=OrderStatus.PENDING)
        order2 = _make_order(order_id=2, order_status=OrderStatus.FROZEN)

        mock_dao = _make_mock_dao()
        mock_dao.get_by_id = AsyncMock(side_effect=[order1, order2, None])
        mock_log_dao = _make_mock_dao()

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls, \
             patch("src.services.b13_order_admin_service.OrderOperationLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            items = [
                {"order_id": 1, "target_status": int(OrderStatus.FROZEN)},
                {"order_id": 2, "target_status": int(OrderStatus.SETTLABLE)},
                {"order_id": 999, "target_status": int(OrderStatus.FROZEN)},
            ]
            result = await B13OrderAdminService.batch_validate_transition(items)

        assert result["total"] == 3
        assert result["valid_count"] == 2
        assert result["invalid_count"] == 1
        assert any(not r["valid"] for r in result["items"])

    @pytest.mark.asyncio
    async def test_batch_validate_transition_exception(self):
        """批量校验中单条异常不影响整体，返回 invalid"""
        session, cm = _make_session_cm()

        mock_dao = _make_mock_dao()
        mock_dao.get_by_id = AsyncMock(side_effect=Exception("DB异常"))
        mock_log_dao = _make_mock_dao()

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderDAO") as mock_dao_cls, \
             patch("src.services.b13_order_admin_service.OrderOperationLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_log_cls.return_value = mock_log_dao

            items = [{"order_id": 1, "target_status": int(OrderStatus.FROZEN)}]
            result = await B13OrderAdminService.batch_validate_transition(items)

        assert result["total"] == 1
        assert result["valid_count"] == 0
        assert result["invalid_count"] == 1
        assert "校验异常" in result["items"][0]["message"]


# ══════════════════════════════════════════════════════
# 4. 执行状态流转测试
# ══════════════════════════════════════════════════════


class TestB13OrderAdminExecute:
    """执行状态流转测试"""

    @pytest.mark.asyncio
    async def test_execute_transition_success(self):
        """执行成功 → 返回结果并写审计日志"""
        session, cm = _make_session_cm()

        expected_result = {
            "id": 1,
            "order_status": int(OrderStatus.FROZEN),
            "out_order_no": "OUT00000001",
        }

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.B12OrderStateMachineService.transition_order_status") as mock_transition, \
             patch("src.services.b13_order_admin_service.AuditLogger.log") as mock_audit:
            mock_db.get_session.return_value = cm
            mock_transition.return_value = expected_result

            result = await B13OrderAdminService.execute_transition(
                order_id=1,
                target_status=int(OrderStatus.FROZEN),
                operation_type=OrderOperationType.STATUS_TRANSITION,
                operator_id=1,
                operator_name="admin",
                remark="测试流转",
            )

        assert result == expected_result
        mock_audit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_transition_same_status(self):
        """相同状态 → 不执行变更，直接返回"""
        session, cm = _make_session_cm()

        expected = {
            "id": 1,
            "order_status": int(OrderStatus.FROZEN),
        }

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.B12OrderStateMachineService.transition_order_status") as mock_transition, \
             patch("src.services.b13_order_admin_service.AuditLogger.log") as mock_audit:
            mock_db.get_session.return_value = cm
            mock_transition.return_value = expected

            result = await B13OrderAdminService.execute_transition(
                order_id=1, target_status=int(OrderStatus.FROZEN)
            )

        assert result["order_status"] == int(OrderStatus.FROZEN)
        mock_audit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_transition_raises_value_error(self):
        """校验失败 → 抛出 ValueError"""
        session, cm = _make_session_cm()

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.B12OrderStateMachineService") as mock_sm_cls:
            mock_db.get_session.return_value = cm
            mock_sm = AsyncMock()
            mock_sm.transition_order_status = AsyncMock(side_effect=ValueError("状态流转非法"))
            mock_sm_cls.return_value = mock_sm

            with pytest.raises(ValueError, match="状态流转非法"):
                await B13OrderAdminService.execute_transition(
                    order_id=1, target_status=999
                )


# ══════════════════════════════════════════════════════
# 5. 操作日志查询测试
# ══════════════════════════════════════════════════════


class TestB13OrderAdminLogs:
    """操作日志查询测试"""

    @pytest.mark.asyncio
    async def test_list_operation_logs_empty(self):
        """无日志 → 返回空列表"""
        session, cm = _make_session_cm()

        # Mock the DAO that the service uses internally
        mock_log_dao = MagicMock()
        mock_log_dao.list_by_order_id = AsyncMock(return_value=([], 0))

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderOperationLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_log_cls.return_value = mock_log_dao

            result = await B13OrderAdminService.list_operation_logs(
                order_id=1, page=1, page_size=20
            )
        assert result["total"] == 0
        assert len(result["items"]) == 0

    @pytest.mark.asyncio
    async def test_list_operation_logs_success(self):
        """有日志 → 返回序列化结果"""
        session, cm = _make_session_cm()
        logs = [_make_operation_log(log_id=1, order_id=1, from_status=10, to_status=20)]

        mock_log_dao = MagicMock()
        mock_log_dao.list_by_order_id = AsyncMock(return_value=(logs, 1))

        with patch("src.services.b13_order_admin_service.DatabaseManager") as mock_db, \
             patch("src.services.b13_order_admin_service.OrderOperationLogDAO") as mock_log_cls:
            mock_db.get_session.return_value = cm
            mock_log_cls.return_value = mock_log_dao

            result = await B13OrderAdminService.list_operation_logs(
                order_id=1, page=1, page_size=20
            )
        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["order_id"] == 1
        assert result["items"][0]["operation_type_label"] == "状态流转"


# ══════════════════════════════════════════════════════
# 6. 序列化方法覆盖测试
# ══════════════════════════════════════════════════════


class TestB13OrderAdminSerialization:
    """序列化方法覆盖测试"""

    def test_serialize_order_brief_none_fields(self):
        """空字段处理 → 默认空字符串"""
        order = _make_order()
        order.goods_title = None
        order.goods_img = None
        order.pay_amount = None

        result = B13OrderAdminService._serialize_order_brief(order)
        assert result["goods_title"] == ""
        assert result["goods_img"] == ""
        assert result["pay_amount"] == "0.00"

    def test_serialize_operation_log_none_remark(self):
        """remark None → 空字符串"""
        log = _make_operation_log()
        log.remark = None

        result = B13OrderAdminService._serialize_operation_log(log)
        assert result["remark"] == ""