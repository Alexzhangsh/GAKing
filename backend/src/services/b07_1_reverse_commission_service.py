# @ai-generated
"""
B07-1 退款逆向佣金冲减服务层

职责：
1. 退款订单识别 —— 扫描 REFUNDED 状态且无冲减记录的订单
2. 冻结用户收益 —— 创建冲减记录并标记 FROZEN
3. 平台回扣佣金 —— 调用 B05-6 扣减逻辑执行实际冲减
4. 异常捕获与重试 —— 失败记录自动/手动重试
5. 手动调整 —— 管理员手动调整冲减金额

依赖：
- B05-6 RefundDeductionService 执行实际扣减（复用现有能力）
- ReverseCommissionRecordDAO 管理冲减记录生命周期
- ReverseCommissionQueryDAO 查询退款订单
"""
import logging
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config.b07_1_constants import (
    MAX_RETRY_COUNT,
    REVERSE_STATUS_LABELS,
    ReverseCommissionStatus,
    SYSTEM_OPERATOR_ID,
    SYSTEM_OPERATOR_NAME,
    TASK_REVERSE_COMMISSION_BATCH_SIZE,
)
from src.config.constants import OrderStatus
from src.dao.b07_1_reverse_commission_dao import (
    ReverseCommissionQueryDAO,
    ReverseCommissionRecordDAO,
)
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.order_dao import OrderDAO
from src.services.refund_deduction_service import RefundDeductionService

logger = logging.getLogger("service.b07_1_reverse_commission")


class ReverseCommissionService:
    """逆向佣金冲减业务服务

    通过构造函数注入所需 DAO / Service
    所有 DAO 共享同一 session（由 API 层或定时任务注入）
    """

    def __init__(
        self,
        record_dao: ReverseCommissionRecordDAO,
        query_dao: ReverseCommissionQueryDAO,
        order_dao: OrderDAO,
        flow_dao: CommissionFlowDAO,
        deduction_service: RefundDeductionService,
    ):
        self.record_dao = record_dao
        self.query_dao = query_dao
        self.order_dao = order_dao
        self.flow_dao = flow_dao
        self.deduction_service = deduction_service

    # ════════════════════════════════════════════════════════════
    # 1. 退款订单识别
    # ════════════════════════════════════════════════════════════

    async def identify_refund_orders(
        self,
        limit: int = TASK_REVERSE_COMMISSION_BATCH_SIZE,
        operator_id: int = SYSTEM_OPERATOR_ID,
        operator_name: str = SYSTEM_OPERATOR_NAME,
    ) -> Dict[str, Any]:
        """识别退款订单并创建冲减记录

        流程：
        1. 查询 REFUNDED 状态且无冲减记录的订单
        2. 查询订单关联的佣金流水
        3. 为每个符合条件的订单创建 IDENTIFIED 状态记录

        Args:
            limit: 单次处理上限
            operator_id: 操作人ID（0=系统自动）
            operator_name: 操作人姓名
        Returns:
            {"status": "success"|"partial",
             "identified": int, "skipped": int,
             "details": List[dict]}
        """
        task_name = "reverse_commission:identify"
        result: Dict[str, Any] = {
            "status": "success",
            "identified": 0,
            "skipped": 0,
            "details": [],
        }

        try:
            # 1. 查询待处理的退款订单
            orders = await self.query_dao.list_refunded_orders_without_record(
                limit=limit
            )

            if not orders:
                logger.info("[%s] 无待处理的退款订单", task_name)
                result["message"] = "无待处理的退款订单"
                return result

            logger.info(
                "[%s] 发现 %s 笔待处理退款订单",
                task_name, len(orders),
            )

            # 2. 逐单创建冲减记录
            for order in orders:
                detail: Dict[str, Any] = {
                    "order_id": order.id,
                    "out_order_no": order.out_order_no,
                    "status": "identified",
                }

                try:
                    # 查询佣金流水
                    flows = await self.query_dao.get_commission_flows_by_order_id(
                        order.id
                    )
                    order_flows = [f for f in flows if f.flow_type == "ORDER"]

                    if not order_flows:
                        # 无 ORDER 流水，跳过
                        logger.info(
                            "[%s] 订单 %s 无 ORDER 流水，跳过",
                            task_name, order.id,
                        )
                        detail["status"] = "skipped"
                        detail["reason"] = "无 ORDER 流水"
                        result["skipped"] += 1
                        result["details"].append(detail)
                        continue

                    original_flow = order_flows[0]

                    # 检查是否已有冲减记录
                    if await self.record_dao.exists_by_order_id(order.id):
                        detail["status"] = "skipped"
                        detail["reason"] = "已有冲减记录"
                        result["skipped"] += 1
                        result["details"].append(detail)
                        continue

                    # 创建冲减记录
                    await self.record_dao.create_record(
                        order_id=order.id,
                        out_order_no=order.out_order_no or "",
                        user_id=order.user_id,
                        channel_code=order.channel_code or "",
                        original_commission=order.user_commission or Decimal("0"),
                        flow_type=original_flow.flow_type,
                        flow_transfer_status=original_flow.transfer_status,
                        operator_id=operator_id,
                        operator_name=operator_name,
                        remark=f"系统自动识别退款订单冲减",
                    )

                    result["identified"] += 1
                    logger.info(
                        "[%s] 订单 %s 冲减记录已创建 user_id=%s commission=%s",
                        task_name, order.id, order.user_id, order.user_commission,
                    )

                except Exception as e:
                    detail["status"] = "failed"
                    detail["error"] = str(e)
                    logger.error(
                        "[%s] 订单 %s 识别异常: %s",
                        task_name, order.id, e, exc_info=True,
                    )
                    result["skipped"] += 1

                result["details"].append(detail)

            # 3. 汇总
            result["message"] = (
                f"识别完成: 新增 {result['identified']} 条, "
                f"跳过 {result['skipped']} 条"
            )
            if result["identified"] == 0 and result["skipped"] > 0:
                result["status"] = "partial"

            logger.info("[%s] %s", task_name, result["message"])

        except Exception as e:
            logger.error("[%s] 识别任务异常: %s\n%s", task_name, e, traceback.format_exc())
            result["status"] = "failed"
            result["message"] = str(e)

        return result

    # ════════════════════════════════════════════════════════════
    # 2. 执行单条冲减
    # ════════════════════════════════════════════════════════════

    async def execute_reverse_commission(
        self,
        record_id: int,
        operator_id: int = SYSTEM_OPERATOR_ID,
        operator_name: str = SYSTEM_OPERATOR_NAME,
    ) -> Dict[str, Any]:
        """执行单条逆向冲减

        流程：
        1. 查询冲减记录
        2. 标记 FROZEN（冻结）
        3. 调用 B05-6 RefundDeductionService 执行扣减
        4. 成功 → 标记 CLAWBACK_DONE
        5. 失败 → 标记 FAILED + 递增重试次数

        Args:
            record_id: 冲减记录ID
            operator_id: 操作人ID
            operator_name: 操作人姓名
        Returns:
            {"status": "success"|"failed"|"skipped",
             "record_id": int, "message": str, ...}
        """
        record = await self.record_dao.get_by_id(record_id)
        if record is None:
            return {
                "status": "failed",
                "record_id": record_id,
                "message": f"冲减记录不存在: record_id={record_id}",
            }

        # 检查状态是否可执行
        if record.status in (ReverseCommissionStatus.CLAWBACK_DONE.value, ReverseCommissionStatus.ADJUSTED.value):
            return {
                "status": "skipped",
                "record_id": record_id,
                "message": f"冲减记录已完成，无需重复处理 (status={record.status})",
            }

        # 检查重试次数
        if record.retry_count >= record.max_retry:
            return {
                "status": "failed",
                "record_id": record_id,
                "message": f"重试次数已达上限 ({record.retry_count}/{record.max_retry})",
            }

        try:
            # 1. 标记 FROZEN
            await self.record_dao.update_status(
                record_id=record_id,
                status=ReverseCommissionStatus.FROZEN.value,
                operator_id=operator_id,
                operator_name=operator_name,
            )

            # 2. 调用 B05-6 扣减逻辑
            deduct_result = await self.deduction_service.execute_refund_deduction(
                order_id=record.order_id,
                operator_id=operator_id,
                remark=f"B07-1 逆向冲减: {operator_name}",
            )

            if deduct_result.status == "success":
                # 成功 → CLAWBACK_DONE
                deducted = Decimal(str(deduct_result.deduct_amount))
                deduct_flow_id = deduct_result.deduct_flow_id
                await self.record_dao.update_status(
                    record_id=record_id,
                    status=ReverseCommissionStatus.CLAWBACK_DONE.value,
                    deducted_amount=deducted,
                    deduct_flow_id=deduct_flow_id,
                    operator_id=operator_id,
                    operator_name=operator_name,
                )
                logger.info(
                    "[reverse_commission] 冲减成功 record_id=%s order_id=%s "
                    "amount=%s flow_id=%s",
                    record_id, record.order_id, deducted, deduct_flow_id,
                )
                return {
                    "status": "success",
                    "record_id": record_id,
                    "order_id": record.order_id,
                    "deducted_amount": float(deducted),
                    "deduct_flow_id": deduct_flow_id,
                    "message": f"冲减成功，扣减金额 {float(deducted):.2f} 元",
                }
            elif deduct_result.status == "skipped":
                # 跳过（无流水或已扣减）
                await self.record_dao.update_status(
                    record_id=record_id,
                    status=ReverseCommissionStatus.CLAWBACK_DONE.value,
                    deducted_amount=Decimal("0.00"),
                    operator_id=operator_id,
                    operator_name=operator_name,
                    remark=deduct_result.message,
                )
                return {
                    "status": "success",
                    "record_id": record_id,
                    "order_id": record.order_id,
                    "deducted_amount": 0.0,
                    "message": f"无需扣减: {deduct_result.message}",
                }
            else:
                # 异常状态
                raise ValueError(f"扣减返回异常状态: {deduct_result.status}")

        except Exception as e:
            error_msg = str(e)
            logger.error(
                "[reverse_commission] 冲减失败 record_id=%s order_id=%s: %s\n%s",
                record_id, record.order_id, error_msg, traceback.format_exc(),
            )

            # 标记失败 + 递增重试
            await self.record_dao.increment_retry(record_id, error_msg)

            return {
                "status": "failed",
                "record_id": record_id,
                "order_id": record.order_id,
                "message": error_msg,
                "retry_count": record.retry_count + 1,
                "max_retry": record.max_retry,
            }

    # ════════════════════════════════════════════════════════════
    # 3. 批量执行冲减
    # ════════════════════════════════════════════════════════════

    async def batch_execute(
        self,
        limit: int = TASK_REVERSE_COMMISSION_BATCH_SIZE,
        operator_id: int = SYSTEM_OPERATOR_ID,
        operator_name: str = SYSTEM_OPERATOR_NAME,
    ) -> Dict[str, Any]:
        """批量执行逆向冲减

        先处理 IDENTIFIED 状态的记录，再处理可重试的失败记录。

        Args:
            limit: 单次处理上限
            operator_id: 操作人ID
            operator_name: 操作人姓名
        Returns:
            {"status": "success"|"partial",
             "total": int, "success": int, "failed": int,
             "details": List[dict]}
        """
        task_name = "reverse_commission:batch_execute"
        result: Dict[str, Any] = {
            "status": "success",
            "total": 0,
            "success": 0,
            "failed": 0,
            "details": [],
        }

        try:
            # 1. 查询待处理的 IDENTIFIED 记录
            pending_records = await self.record_dao.list_by_status(
                status=ReverseCommissionStatus.IDENTIFIED.value,
                limit=limit,
            )

            # 2. 查询可重试的失败记录
            retryable_records = await self.record_dao.list_retryable(limit=limit)

            all_records = pending_records + retryable_records
            if not all_records:
                result["message"] = "无待处理的冲减记录"
                return result

            # 限制总处理量
            if len(all_records) > limit:
                all_records = all_records[:limit]

            result["total"] = len(all_records)
            logger.info(
                "[%s] 批量处理 %s 条（待处理 %s, 可重试 %s）",
                task_name, len(all_records), len(pending_records), len(retryable_records),
            )

            # 3. 逐条执行
            for record in all_records:
                exec_result = await self.execute_reverse_commission(
                    record_id=record.id,
                    operator_id=operator_id,
                    operator_name=operator_name,
                )
                result["details"].append(exec_result)
                if exec_result["status"] == "success":
                    result["success"] += 1
                else:
                    result["failed"] += 1

            # 4. 汇总
            result["message"] = (
                f"批量处理完成: 共 {result['total']} 条, "
                f"成功 {result['success']} 条, 失败 {result['failed']} 条"
            )
            if result["failed"] > 0:
                result["status"] = "partial"

            logger.info("[%s] %s", task_name, result["message"])

        except Exception as e:
            logger.error(
                "[%s] 批量执行异常: %s\n%s",
                task_name, e, traceback.format_exc(),
            )
            result["status"] = "failed"
            result["message"] = str(e)

        return result

    # ════════════════════════════════════════════════════════════
    # 4. 手动重试
    # ════════════════════════════════════════════════════════════

    async def retry_failed(
        self,
        record_id: int,
        operator_id: int,
        operator_name: str,
    ) -> Dict[str, Any]:
        """手动重试失败的冲减记录

        Args:
            record_id: 冲减记录ID
            operator_id: 操作人管理员ID
            operator_name: 操作人姓名
        Returns:
            同 execute_reverse_commission 返回结构
        """
        return await self.execute_reverse_commission(
            record_id=record_id,
            operator_id=operator_id,
            operator_name=operator_name,
        )

    # ════════════════════════════════════════════════════════════
    # 5. 手动调整
    # ════════════════════════════════════════════════════════════

    async def adjust_commission(
        self,
        record_id: int,
        adjust_amount: Decimal,
        operator_id: int,
        operator_name: str,
        remark: str = "",
    ) -> Dict[str, Any]:
        """手动调整冲减金额

        适用场景：自动扣减失败后，管理员手动确认扣减金额。
        仅对 FAILED 状态的记录可调整。

        Args:
            record_id: 冲减记录ID
            adjust_amount: 手动调整的扣减金额
            operator_id: 操作人管理员ID
            operator_name: 操作人姓名
            remark: 调整备注
        Returns:
            {"status": "success"|"failed",
             "record_id": int, "message": str, ...}
        """
        record = await self.record_dao.get_by_id(record_id)
        if record is None:
            return {
                "status": "failed",
                "record_id": record_id,
                "message": f"冲减记录不存在: record_id={record_id}",
            }

        if record.status not in (ReverseCommissionStatus.FAILED.value, ReverseCommissionStatus.IDENTIFIED.value):
            return {
                "status": "failed",
                "record_id": record_id,
                "message": f"仅 FAILED/IDENTIFIED 状态的记录可手动调整 (当前: {record.status})",
            }

        if adjust_amount < Decimal("0"):
            return {
                "status": "failed",
                "record_id": record_id,
                "message": "调整金额不能为负数",
            }

        try:
            await self.record_dao.update_status(
                record_id=record_id,
                status=ReverseCommissionStatus.ADJUSTED.value,
                deducted_amount=adjust_amount,
                operator_id=operator_id,
                operator_name=operator_name,
                remark=remark or f"手动调整冲减金额为 {adjust_amount} 元",
            )

            logger.info(
                "[reverse_commission] 手动调整 record_id=%s order_id=%s "
                "amount=%s operator=%s",
                record_id, record.order_id, adjust_amount, operator_name,
            )

            return {
                "status": "success",
                "record_id": record_id,
                "order_id": record.order_id,
                "original_commission": float(record.original_commission),
                "adjusted_amount": float(adjust_amount),
                "message": f"手动调整成功，冲减金额 {float(adjust_amount):.2f} 元",
            }

        except Exception as e:
            logger.error(
                "[reverse_commission] 手动调整失败 record_id=%s: %s\n%s",
                record_id, e, traceback.format_exc(),
            )
            return {
                "status": "failed",
                "record_id": record_id,
                "message": str(e),
            }

    # ════════════════════════════════════════════════════════════
    # 6. 定时任务完整流程（识别 + 批量执行）
    # ════════════════════════════════════════════════════════════

    async def scheduled_reverse_commission(
        self,
    ) -> Dict[str, Any]:
        """定时任务入口：识别退款订单 → 批量执行冲减

        两步串行执行：
        1. identify_refund_orders() 识别新退款订单
        2. batch_execute() 处理所有待冲减记录

        Returns:
            {"status": "success"|"partial"|"failed",
             "identify_result": dict, "execute_result": dict}
        """
        task_name = "scheduled_reverse_commission"
        logger.info("[%s] 定时任务开始执行", task_name)

        result: Dict[str, Any] = {
            "status": "success",
            "identify_result": None,
            "execute_result": None,
        }

        try:
            # 第一步：识别
            identify_result = await self.identify_refund_orders()
            result["identify_result"] = identify_result

            # 第二步：批量执行
            execute_result = await self.batch_execute()
            result["execute_result"] = execute_result

            # 汇总状态
            if identify_result.get("status") == "failed" and execute_result.get("status") == "failed":
                result["status"] = "failed"
            elif identify_result.get("status") == "failed" or execute_result.get("status") == "failed":
                result["status"] = "partial"

            result["message"] = (
                f"识别: {identify_result.get('identified', 0)} 条新增, "
                f"执行: {execute_result.get('success', 0)} 条成功, "
                f"{execute_result.get('failed', 0)} 条失败"
            )

            logger.info("[%s] %s", task_name, result["message"])

        except Exception as e:
            logger.error(
                "[%s] 定时任务异常: %s\n%s",
                task_name, e, traceback.format_exc(),
            )
            result["status"] = "failed"
            result["message"] = str(e)

        return result

    # ════════════════════════════════════════════════════════════
    # 7. 统计概览
    # ════════════════════════════════════════════════════════════

    async def get_statistics(self) -> Dict[str, Any]:
        """获取冲减统计概览"""
        stats: Dict[str, Any] = {
            "total_pending": 0,   # 待处理（IDENTIFIED）
            "total_frozen": 0,    # 冻结中（FROZEN）
            "total_done": 0,      # 已完成（CLAWBACK_DONE）
            "total_failed": 0,    # 失败（FAILED）
            "total_adjusted": 0,  # 已调整（ADJUSTED）
            "pending_refund_orders": 0,  # 待识别的退款订单数
        }

        try:
            for status in (
                ReverseCommissionStatus.IDENTIFIED,
                ReverseCommissionStatus.FROZEN,
                ReverseCommissionStatus.CLAWBACK_DONE,
                ReverseCommissionStatus.FAILED,
                ReverseCommissionStatus.ADJUSTED,
            ):
                count = await self.record_dao.count_by_status(status.value)
                key = {
                    ReverseCommissionStatus.IDENTIFIED: "total_pending",
                    ReverseCommissionStatus.FROZEN: "total_frozen",
                    ReverseCommissionStatus.CLAWBACK_DONE: "total_done",
                    ReverseCommissionStatus.FAILED: "total_failed",
                    ReverseCommissionStatus.ADJUSTED: "total_adjusted",
                }[status]
                stats[key] = count

            # 待识别的退款订单数
            stats["pending_refund_orders"] = (
                await self.query_dao.count_refunded_orders_without_record()
            )

        except Exception as e:
            logger.error("[reverse_commission] 获取统计异常: %s", e)

        return stats