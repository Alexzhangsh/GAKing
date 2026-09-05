# @ai-generated
"""
B05-5 佣金流水结算前置校验服务层
职责：校验订单状态、佣金金额合法性、拦截重复生成佣金流水，记录校验日志
不包含数据存取逻辑（下沉 DAO），不包含 HTTP 处理（上浮 API 层）
金额统一 Decimal 精确计算
"""
import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config.constants import OrderStatus
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_flow_validation_log_dao import CommissionFlowValidationLogDAO
from src.dao.order_dao import OrderDAO
from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.order_model import Order
from src.schemas.commission_flow_validation import (
    CheckItemDetail,
    CommissionFlowPreValidateResponse,
)

logger = logging.getLogger("service.commission_flow_validation")

# 校验类型常量
VALIDATION_TYPE_PRE_SETTLE = "PRE_SETTLE"
VALIDATION_TYPE_PRE_DEDUCT = "PRE_DEDUCT"

# 校验结果常量
VALIDATION_RESULT_PASS = "PASS"
VALIDATION_RESULT_FAIL = "FAIL"

# 流水类型常量
FLOW_TYPE_ORDER = "ORDER"


class CommissionFlowValidationService:
    """佣金流水结算前置校验服务

    通过构造函数注入 OrderDAO / CommissionFlowDAO / CommissionFlowValidationLogDAO
    所有 DAO 共享同一 session（由 API 层的 get_db 注入）
    """

    def __init__(
        self,
        order_dao: OrderDAO,
        flow_dao: CommissionFlowDAO,
        validation_log_dao: CommissionFlowValidationLogDAO,
    ):
        self.order_dao = order_dao
        self.flow_dao = flow_dao
        self.validation_log_dao = validation_log_dao

    # ── 1. 结算前置校验核心方法 ────────────────────────────────────

    async def pre_validate_settle(
        self,
        order_id: int,
        operator_id: int = 0,
    ) -> CommissionFlowPreValidateResponse:
        """结算前置校验：校验订单状态、佣金金额合法性、拦截重复流水

        校验项：
        1. 订单存在性校验
        2. 订单状态校验（必须为 SETTLED 40）
        3. 佣金金额合法性校验（user_commission > 0）
        4. 佣金金额超限校验（user_commission <= total_commission）
        5. 重复流水拦截（已有 ORDER 类型流水）
        6. 用户归属校验（user_id 必须 > 0）

        Args:
            order_id: 订单ID
            operator_id: 操作人管理员ID（0=系统自动）
        Returns:
            CommissionFlowPreValidateResponse 包含各项校验明细
        """
        check_items: List[CheckItemDetail] = []
        all_passed = True
        error_messages: List[str] = []

        # 1. 订单存在性校验
        order = await self.order_dao.get_by_id(order_id)
        check_items.append(
            CheckItemDetail(
                name="order_exists",
                passed=order is not None,
                current_value=order_id,
                expected_value="有效订单",
                message="订单存在" if order is not None else "订单不存在",
            )
        )
        if order is None:
            all_passed = False
            error_messages.append("订单不存在")
            await self._save_validation_log(
                order_id=order_id,
                user_id=0,
                check_items=check_items,
                all_passed=False,
                error_message="; ".join(error_messages),
                operator_id=operator_id,
            )
            return CommissionFlowPreValidateResponse(
                order_id=order_id,
                validation_result=VALIDATION_RESULT_FAIL,
                check_items=check_items,
                error_message="; ".join(error_messages),
            )

        user_id = order.user_id

        # 2. 订单状态校验
        status_check = self._check_order_status(order)
        check_items.append(status_check)
        if not status_check.passed:
            all_passed = False
            error_messages.append(status_check.message)

        # 3. 佣金金额合法性校验（user_commission > 0）
        amount_check = self._check_commission_amount(order)
        check_items.append(amount_check)
        if not amount_check.passed:
            all_passed = False
            error_messages.append(amount_check.message)

        # 4. 佣金金额超限校验（user_commission <= total_commission）
        overrun_check = self._check_commission_overrun(order)
        check_items.append(overrun_check)
        if not overrun_check.passed:
            all_passed = False
            error_messages.append(overrun_check.message)

        # 5. 重复流水拦截（已有 ORDER 类型流水）
        duplicate_check = await self._check_duplicate_flow(order_id)
        check_items.append(duplicate_check)
        if not duplicate_check.passed:
            all_passed = False
            error_messages.append(duplicate_check.message)

        # 6. 用户归属校验（user_id > 0）
        user_check = self._check_user_id(user_id)
        check_items.append(user_check)
        if not user_check.passed:
            all_passed = False
            error_messages.append(user_check.message)

        # 记录校验日志
        await self._save_validation_log(
            order_id=order_id,
            user_id=user_id,
            check_items=check_items,
            all_passed=all_passed,
            error_message="; ".join(error_messages) if error_messages else "",
            operator_id=operator_id,
        )

        return CommissionFlowPreValidateResponse(
            order_id=order_id,
            validation_result=VALIDATION_RESULT_PASS if all_passed else VALIDATION_RESULT_FAIL,
            check_items=check_items,
            error_message="; ".join(error_messages) if error_messages else "",
        )

    # ── 2. 单项校验方法 ────────────────────────────────────────────

    @staticmethod
    def _check_order_status(order: Order) -> CheckItemDetail:
        """校验订单状态必须为 SETTLED(40)"""
        expected = int(OrderStatus.SETTLED)
        actual = order.order_status
        passed = actual == expected
        status_map = {
            10: "PENDING(待付款)",
            20: "FROZEN(冻结)",
            30: "SETTLABLE(可结算)",
            40: "SETTLED(已结算)",
            50: "INVALID(失效)",
            60: "REFUNDED(已退款)",
        }
        return CheckItemDetail(
            name="order_status",
            passed=passed,
            current_value=f"{actual}({status_map.get(actual, '未知')})",
            expected_value=f"{expected}({status_map.get(expected)})",
            message="订单状态为 SETTLED，校验通过" if passed
            else f"订单状态为 {status_map.get(actual, '未知')}，需要 SETTLED(已结算) 状态才能结算",
        )

    @staticmethod
    def _check_commission_amount(order: Order) -> CheckItemDetail:
        """校验佣金金额必须大于 0"""
        amount = Decimal(str(order.user_commission))
        passed = amount > 0
        return CheckItemDetail(
            name="commission_amount",
            passed=passed,
            current_value=float(amount),
            expected_value="> 0",
            message=f"用户佣金金额 {amount:.2f} 元，金额合法" if passed
            else f"用户佣金金额 {amount:.2f} 元 <= 0，无法结算",
        )

    @staticmethod
    def _check_commission_overrun(order: Order) -> CheckItemDetail:
        """校验用户佣金不超过总佣金"""
        user_comm = Decimal(str(order.user_commission))
        total_comm = Decimal(str(order.total_commission))
        passed = user_comm <= total_comm
        return CheckItemDetail(
            name="commission_overrun",
            passed=passed,
            current_value=float(user_comm),
            expected_value=f"<= 总佣金 {float(total_comm)}",
            message=f"用户佣金 {user_comm:.2f} 元 <= 总佣金 {total_comm:.2f} 元" if passed
            else f"用户佣金 {user_comm:.2f} 元 > 总佣金 {total_comm:.2f} 元，数据异常",
        )

    async def _check_duplicate_flow(self, order_id: int) -> CheckItemDetail:
        """校验是否已有 ORDER 类型流水（拦截重复生成）"""
        existing_flows = await self.flow_dao.list_by_order_id(order_id)
        order_flows = [f for f in existing_flows if f.flow_type == FLOW_TYPE_ORDER]
        passed = len(order_flows) == 0
        flow_statuses = [f.transfer_status for f in order_flows] if order_flows else []
        return CheckItemDetail(
            name="duplicate_flow",
            passed=passed,
            current_value=f"已有 {len(order_flows)} 条 ORDER 流水" if order_flows else "无重复流水",
            expected_value="无重复 ORDER 流水",
            message="无重复 ORDER 流水，可以生成" if passed
            else f"已存在 {len(order_flows)} 条 ORDER 类型流水（状态: {flow_statuses}），重复生成被拦截",
        )

    @staticmethod
    def _check_user_id(user_id: int) -> CheckItemDetail:
        """校验用户ID有效"""
        passed = user_id > 0
        return CheckItemDetail(
            name="user_id_valid",
            passed=passed,
            current_value=user_id,
            expected_value="> 0",
            message=f"用户ID {user_id} 有效" if passed
            else f"用户ID {user_id} 无效，订单无归属用户",
        )

    # ── 3. 批量校验（供定时任务批量调用） ──────────────────────────

    async def batch_pre_validate(
        self,
        order_ids: List[int],
        operator_id: int = 0,
    ) -> Dict[str, Any]:
        """批量前置校验

        Args:
            order_ids: 订单ID列表
            operator_id: 操作人管理员ID
        Returns:
            {total, passed_count, failed_count, details}
        """
        total = len(order_ids)
        passed_count = 0
        failed_count = 0
        details: List[Dict[str, Any]] = []

        for order_id in order_ids:
            try:
                result = await self.pre_validate_settle(order_id, operator_id)
                if result.validation_result == VALIDATION_RESULT_PASS:
                    passed_count += 1
                else:
                    failed_count += 1
                details.append({
                    "order_id": order_id,
                    "validation_result": result.validation_result,
                    "error_message": result.error_message,
                })
            except Exception as e:
                failed_count += 1
                logger.error(
                    "[batch_pre_validate] 校验失败 order_id=%s error=%s",
                    order_id, e, exc_info=True,
                )
                details.append({
                    "order_id": order_id,
                    "validation_result": VALIDATION_RESULT_FAIL,
                    "error_message": str(e),
                })

        logger.info(
            "[batch_pre_validate] 完成 total=%s passed=%s failed=%s",
            total, passed_count, failed_count,
        )
        return {
            "total": total,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "details": details,
        }

    # ── 4. 校验日志记录 ────────────────────────────────────────────

    # ── 5. 扣减前置校验（B05-6 新增） ──────────────────────────

    async def pre_validate_deduct(
        self,
        order_id: int,
        operator_id: int = 0,
    ) -> CommissionFlowPreValidateResponse:
        """扣减前置校验：校验订单状态、佣金流水状态、拦截重复扣减

        校验项：
        1. 订单存在性校验
        2. 订单状态校验（必须为 REFUNDED 60）
        3. 佣金流水存在性校验（至少有一条 ORDER 类型流水）
        4. 佣金流水状态校验（SUCCESS 或 PENDING，均需处理）
        5. 重复扣减拦截（已有 DEDUCT 类型流水）
        6. 用户归属校验（user_id 必须 > 0）

        Args:
            order_id: 订单ID
            operator_id: 操作人管理员ID（0=系统自动）
        Returns:
            CommissionFlowPreValidateResponse 包含各项校验明细
        """
        check_items: List[CheckItemDetail] = []
        all_passed = True
        error_messages: List[str] = []

        # 1. 订单存在性校验
        order = await self.order_dao.get_by_id(order_id)
        check_items.append(
            CheckItemDetail(
                name="order_exists",
                passed=order is not None,
                current_value=order_id,
                expected_value="有效订单",
                message="订单存在" if order is not None else "订单不存在",
            )
        )
        if order is None:
            all_passed = False
            error_messages.append("订单不存在")
            await self._save_validation_log(
                order_id=order_id,
                user_id=0,
                validation_type=VALIDATION_TYPE_PRE_DEDUCT,
                check_items=check_items,
                all_passed=False,
                error_message="; ".join(error_messages),
                operator_id=operator_id,
            )
            return CommissionFlowPreValidateResponse(
                order_id=order_id,
                validation_result=VALIDATION_RESULT_FAIL,
                check_items=check_items,
                error_message="; ".join(error_messages),
            )

        user_id = order.user_id

        # 2. 订单状态校验（必须为 REFUNDED 60）
        status_check = self._check_deduct_order_status(order)
        check_items.append(status_check)
        if not status_check.passed:
            all_passed = False
            error_messages.append(status_check.message)

        # 3. 佣金流水存在性校验
        flow_check = await self._check_order_flow_exists(order_id)
        check_items.append(flow_check)
        if not flow_check.passed:
            all_passed = False
            error_messages.append(flow_check.message)

        # 4. 佣金流水转账状态
        flows = await self.flow_dao.list_by_order_id(order_id)
        order_flows = [f for f in flows if f.flow_type == FLOW_TYPE_ORDER]
        if order_flows:
            transfer_status_check = self._check_flow_transfer_status(order_flows[0])
            check_items.append(transfer_status_check)
            if not transfer_status_check.passed:
                all_passed = False
                error_messages.append(transfer_status_check.message)

        # 5. 重复扣减拦截（已有 DEDUCT 类型流水）
        duplicate_check = await self._check_duplicate_deduct(order_id)
        check_items.append(duplicate_check)
        if not duplicate_check.passed:
            all_passed = False
            error_messages.append(duplicate_check.message)

        # 6. 用户归属校验（user_id > 0）
        user_check = self._check_user_id(user_id)
        check_items.append(user_check)
        if not user_check.passed:
            all_passed = False
            error_messages.append(user_check.message)

        # 记录校验日志
        await self._save_validation_log(
            order_id=order_id,
            user_id=user_id,
            validation_type=VALIDATION_TYPE_PRE_DEDUCT,
            check_items=check_items,
            all_passed=all_passed,
            error_message="; ".join(error_messages) if error_messages else "",
            operator_id=operator_id,
        )

        return CommissionFlowPreValidateResponse(
            order_id=order_id,
            validation_result=VALIDATION_RESULT_PASS if all_passed else VALIDATION_RESULT_FAIL,
            check_items=check_items,
            error_message="; ".join(error_messages) if error_messages else "",
        )

    @staticmethod
    def _check_deduct_order_status(order: Order) -> CheckItemDetail:
        """校验订单状态必须为 REFUNDED(60)"""
        expected = int(OrderStatus.REFUNDED)
        actual = order.order_status
        passed = actual == expected
        status_map = {
            10: "PENDING(待付款)",
            20: "FROZEN(冻结)",
            30: "SETTLABLE(可结算)",
            40: "SETTLED(已结算)",
            50: "INVALID(失效)",
            60: "REFUNDED(已退款)",
        }
        return CheckItemDetail(
            name="order_status",
            passed=passed,
            current_value=f"{actual}({status_map.get(actual, '未知')})",
            expected_value=f"{expected}({status_map.get(expected)})",
            message="订单状态为 REFUNDED，校验通过" if passed
            else f"订单状态为 {status_map.get(actual, '未知')}，需要 REFUNDED(已退款) 状态才能扣减",
        )

    async def _check_order_flow_exists(self, order_id: int) -> CheckItemDetail:
        """校验订单是否存在 ORDER 类型佣金流水"""
        flows = await self.flow_dao.list_by_order_id(order_id)
        order_flows = [f for f in flows if f.flow_type == FLOW_TYPE_ORDER]
        passed = len(order_flows) > 0
        return CheckItemDetail(
            name="order_flow_exists",
            passed=passed,
            current_value=f"有 {len(order_flows)} 条 ORDER 流水" if order_flows else "无 ORDER 流水",
            expected_value="至少 1 条 ORDER 流水",
            message=f"存在 {len(order_flows)} 条 ORDER 流水" if passed
            else "订单无 ORDER 类型佣金流水，无需扣减",
        )

    @staticmethod
    def _check_flow_transfer_status(flow) -> CheckItemDetail:
        """校验原始流水转账状态（PENDING 或 SUCCESS 均可处理）"""
        status = flow.transfer_status
        passed = status in ("PENDING", "SUCCESS")
        status_map = {
            "PENDING": "待转账",
            "PROCESSING": "转账中",
            "SUCCESS": "已到账",
            "FAILED": "转账失败",
        }
        return CheckItemDetail(
            name="flow_transfer_status",
            passed=passed,
            current_value=f"{status}({status_map.get(status, '未知')})",
            expected_value="PENDING 或 SUCCESS",
            message=f"流水状态为 {status_map.get(status, status)}，可以处理" if passed
            else f"流水状态为 {status_map.get(status, status)}，不可扣减",
        )

    async def _check_duplicate_deduct(self, order_id: int) -> CheckItemDetail:
        """校验是否已有 DEDUCT 类型流水（拦截重复扣减）"""
        flows = await self.flow_dao.list_by_order_id(order_id)
        deduct_flows = [f for f in flows if f.flow_type == "DEDUCT"]
        passed = len(deduct_flows) == 0
        flow_statuses = [f.transfer_status for f in deduct_flows] if deduct_flows else []
        return CheckItemDetail(
            name="duplicate_deduct",
            passed=passed,
            current_value=f"已有 {len(deduct_flows)} 条 DEDUCT 流水" if deduct_flows else "无重复扣减",
            expected_value="无 DEDUCT 流水",
            message="无重复 DEDUCT 流水，可以扣减" if passed
            else f"已存在 {len(deduct_flows)} 条 DEDUCT 类型流水（状态: {flow_statuses}），重复扣减被拦截",
        )

    async def _save_validation_log(
        self,
        order_id: int,
        user_id: int,
        check_items: List[CheckItemDetail],
        all_passed: bool,
        error_message: str = "",
        operator_id: int = 0,
        validation_type: str = VALIDATION_TYPE_PRE_SETTLE,
    ) -> None:
        """保存校验日志到数据库

        Args:
            order_id: 订单ID
            user_id: 用户ID
            check_items: 各项校验明细列表
            all_passed: 是否全部通过
            error_message: 总体错误信息
            operator_id: 操作人管理员ID
            validation_type: 校验类型（PRE_SETTLE/PRE_DEDUCT）
        """
        try:
            check_items_dict = [
                {
                    "name": item.name,
                    "passed": item.passed,
                    "current_value": str(item.current_value) if item.current_value is not None else None,
                    "expected_value": str(item.expected_value) if item.expected_value is not None else None,
                    "message": item.message,
                }
                for item in check_items
            ]
            await self.validation_log_dao.create_log(
                order_id=order_id,
                user_id=user_id,
                validation_type=validation_type,
                validation_result=VALIDATION_RESULT_PASS if all_passed else VALIDATION_RESULT_FAIL,
                check_items=json.dumps(check_items_dict, ensure_ascii=False),
                error_message=error_message,
                operator_id=operator_id,
            )
        except Exception as e:
            logger.error(
                "[save_validation_log] 保存校验日志失败 order_id=%s error=%s",
                order_id, e, exc_info=True,
            )