# @ai-generated
"""
B05-6 退款冲减业务服务层
职责：复用 B05-5 校验服务 + 编排 B07 冲减逻辑 + 写入退款操作日志
不包含数据存取逻辑（下沉 DAO），不包含 HTTP 处理（上浮 API 层）
金额统一 Decimal 精确计算
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config.constants import OrderStatus
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_flow_validation_log_dao import CommissionFlowValidationLogDAO
from src.dao.commission_settlement_dao import (
    FLOW_TYPE_DEDUCT,
    FLOW_TYPE_ORDER,
    TRANSFER_STATUS_PENDING,
    TRANSFER_STATUS_SUCCESS,
    CommissionSettlementDAO,
)
from src.dao.order_dao import OrderDAO
from src.dao.order_refund_operation_log_dao import OrderRefundOperationLogDAO
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.order_model import Order
from src.schemas.refund_deduction import (
    RefundCheckItemDetail,
    RefundDeductionPreValidateResponse,
    RefundDeductionExecuteResponse,
)
from src.services.commission_flow_validation_service import (
    VALIDATION_RESULT_FAIL,
    CommissionFlowValidationService,
)

logger = logging.getLogger("service.refund_deduction")


class RefundDeductionService:
    """退款冲减业务服务

    通过构造函数注入所需 DAO + 校验服务
    所有 DAO 共享同一 session（由 API 层的 get_db 注入）
    """

    def __init__(
        self,
        order_dao: OrderDAO,
        flow_dao: CommissionFlowDAO,
        settlement_dao: CommissionSettlementDAO,
        account_dao: UserCommissionAccountDAO,
        log_dao: OrderRefundOperationLogDAO,
        validation_service: CommissionFlowValidationService,
    ):
        self.order_dao = order_dao
        self.flow_dao = flow_dao
        self.settlement_dao = settlement_dao
        self.account_dao = account_dao
        self.log_dao = log_dao
        self.validation_service = validation_service

    # ── 1. 退款扣减前置校验 ────────────────────────────────────

    async def pre_validate_deduct(
        self,
        order_id: int,
        operator_id: int = 0,
    ) -> RefundDeductionPreValidateResponse:
        """退款扣减前置校验

        复用 CommissionFlowValidationService.pre_validate_deduct 的校验能力，
        将响应转换为 RefundDeductionPreValidateResponse 格式。

        Args:
            order_id: 订单ID
            operator_id: 操作人管理员ID
        Returns:
            RefundDeductionPreValidateResponse
        """
        result = await self.validation_service.pre_validate_deduct(
            order_id=order_id,
            operator_id=operator_id,
        )

        return RefundDeductionPreValidateResponse(
            order_id=result.order_id,
            validation_result=result.validation_result,
            check_items=[
                RefundCheckItemDetail(
                    name=item.name,
                    passed=item.passed,
                    current_value=item.current_value,
                    expected_value=item.expected_value,
                    message=item.message,
                )
                for item in result.check_items
            ],
            error_message=result.error_message,
        )

    # ── 2. 执行退款扣减 ────────────────────────────────────────

    async def execute_refund_deduction(
        self,
        order_id: int,
        operator_id: int,
        remark: str = "",
    ) -> RefundDeductionExecuteResponse:
        """执行单订单退款扣减（校验 + 冲减 + 写日志）

        流程：
        1. 前置校验（复用 pre_validate_deduct）
        2. 校验未通过 → 返回失败
        3. 校验通过 → 调用 CommissionSettlementService.process_single_refund 逻辑
        4. 查询账户余额，记录操作日志

        Args:
            order_id: 订单ID
            operator_id: 操作人管理员ID
            remark: 操作备注
        Returns:
            RefundDeductionExecuteResponse
        Raises:
            ValueError: 校验失败或扣减异常
        """
        # 1. 前置校验
        validate_result = await self.pre_validate_deduct(
            order_id=order_id,
            operator_id=operator_id,
        )
        if validate_result.validation_result == VALIDATION_RESULT_FAIL:
            raise ValueError(
                f"退款扣减前置校验未通过: {validate_result.error_message}"
            )

        # 2. 获取订单及流水信息
        order = await self.order_dao.get_by_id(order_id)
        if order is None:
            raise ValueError(f"订单不存在: order_id={order_id}")

        flows = await self.flow_dao.list_by_order_id(order_id)
        order_flows = [f for f in flows if f.flow_type == FLOW_TYPE_ORDER]
        deduct_flows = [f for f in flows if f.flow_type == FLOW_TYPE_DEDUCT]

        # 无 ORDER 流水 → 跳过
        if not order_flows:
            logger.info("[refund_deduct] 订单无佣金流水，跳过扣减 order_id=%s", order_id)
            return RefundDeductionExecuteResponse(
                order_id=order_id,
                status="skipped",
                message="订单无佣金流水，无需扣减",
            )

        # 已有 DEDUCT 流水 → 幂等跳过
        if deduct_flows:
            logger.info("[refund_deduct] 已存在扣减流水，幂等跳过 order_id=%s", order_id)
            return RefundDeductionExecuteResponse(
                order_id=order_id,
                status="skipped",
                message="已存在扣减流水，幂等跳过",
            )

        # 3. 获取原始流水和账户信息
        original_flow = order_flows[0]
        user_id = order.user_id

        # 查询账户余额（扣减前）
        account = await self.account_dao.get_by_user_id(user_id)
        old_available = Decimal(str(account.available_balance)) if account else Decimal("0")
        old_total = Decimal(str(account.total_balance)) if account else Decimal("0")

        # 4. 执行原子扣减
        deduct_amount = Decimal(str(original_flow.amount))

        if original_flow.transfer_status == TRANSFER_STATUS_PENDING:
            # PENDING 分支：在途扣减，标记 FAILED，不动余额
            deduct_flow = await self.settlement_dao.deduct_on_refund_atomic(
                order, original_flow
            )
            # 更新订单状态为 REFUNDED（已由渠道同步完成，此处确保状态一致）
            await self.order_dao.update_by_id(order_id, {
                "order_status": int(OrderStatus.REFUNDED),
            })

            # 写操作日志
            log_entry = await self.log_dao.create_log(
                order_id=order_id,
                operator_id=operator_id,
                operation_type="DEDUCT",
                order_status_before=order.order_status,
                order_status_after=int(OrderStatus.REFUNDED),
                deduct_amount=deduct_amount,
                flow_type=original_flow.flow_type,
                flow_transfer_status=original_flow.transfer_status,
                old_available_balance=old_available,
                new_available_balance=old_available,  # PENDING 分支不动余额
                old_total_balance=old_total,
                new_total_balance=old_total,  # PENDING 分支不动总额
                deduct_flow_id=None,
                remark=remark or f"退款冲减（在途标记失败）: {order.internal_order_no}",
            )

            logger.info(
                "[refund_deduct] PENDING→FAILED order_id=%s user_id=%s amount=%s",
                order_id, user_id, deduct_amount,
            )
            return RefundDeductionExecuteResponse(
                order_id=order_id,
                status="success",
                deduct_flow_id=None,
                deduct_amount=float(deduct_amount),
                old_available_balance=float(old_available),
                new_available_balance=float(old_available),
                message=f"在途流水标记 FAILED，未动余额（原状态: {original_flow.transfer_status}）",
                log_id=log_entry.id,
            )

        # SUCCESS 分支：已到账，需扣减余额
        deduct_flow = await self.settlement_dao.deduct_on_refund_atomic(
            order, original_flow
        )

        if deduct_flow is None:
            raise ValueError(f"退款扣减原子操作返回空: order_id={order_id}")

        # 查扣减后余额
        account_after = await self.account_dao.get_by_user_id(user_id)
        new_available = Decimal(str(account_after.available_balance)) if account_after else old_available
        new_total = Decimal(str(account_after.total_balance)) if account_after else old_total - deduct_amount

        # 写操作日志
        log_entry = await self.log_dao.create_log(
            order_id=order_id,
            operator_id=operator_id,
            operation_type="DEDUCT",
            order_status_before=order.order_status,
            order_status_after=int(OrderStatus.REFUNDED),
            deduct_amount=deduct_amount,
            flow_type=original_flow.flow_type,
            flow_transfer_status=original_flow.transfer_status,
            old_available_balance=old_available,
            new_available_balance=new_available,
            old_total_balance=old_total,
            new_total_balance=new_total,
            deduct_flow_id=deduct_flow.id,
            remark=remark or f"退款佣金冲减: {order.internal_order_no}",
        )

        logger.info(
            "[refund_deduct] SUCCESS 扣减成功 order_id=%s user_id=%s amount=%s "
            "available: %s→%s total: %s→%s flow_id=%s",
            order_id, user_id, deduct_amount,
            old_available, new_available,
            old_total, new_total,
            deduct_flow.id,
        )

        return RefundDeductionExecuteResponse(
            order_id=order_id,
            status="success",
            deduct_flow_id=deduct_flow.id,
            deduct_amount=float(deduct_amount),
            old_available_balance=float(old_available),
            new_available_balance=float(new_available),
            message=f"已到账佣金扣减成功（可用余额: {old_available:.2f} → {new_available:.2f}）",
            log_id=log_entry.id,
        )