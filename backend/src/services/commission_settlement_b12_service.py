# @ai-generated
"""
佣金结算状态机编排 Service（B12 新建）

职责：
1. SETTLABLE 订单冻结入账（创建结算单 + PENDING 流水 + frozen += amount）
2. SETTLED 订单解冻转可用（SETTLABLE→SETTLED + PENDING→SUCCESS 流水 + frozen→available）
3. 提现成功联动标记已打款（SETTLED→PAID）
4. 批量冻结/解冻定时任务入口（逐单 try/except，单条失败不阻断）
5. 后台分页查询 + 导出筛选 + 超期预警 + 操作历史
6. 状态机严格守护（ORDERED→SETTLABLE→SETTLED→PAID 不可回退）
7. Redis 幂等锁（gaking:prod 前缀）防重复操作
8. B04 熔断兜底（连续失败触发熔断，跳过该渠道结算）

设计要点：
1. 不修改 B01-B11 任何基线代码，通过依赖注入组合现有 DAO
2. 冻结/解冻用 SettlementAtomicDAO 单事务原子操作（FOR UPDATE + 流水 + 余额 + commit）
3. 提前写 commission_flow(ORDER, PENDING) 使 B07 的"无 ORDER 流水"条件不匹配，B07 优雅跳过
4. 异常统一抛 ValueError，由 API 层转 BizException
5. 操作日志失败不阻断主流程，仅记 warning

约束：严禁修改 B01-B11 任何基线代码，全部新建独立文件
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.common.lock_util import LockUtil
from src.config.b12_constants import (
    ACTION_CREATE_SETTLEMENT,
    ACTION_FREEZE,
    ACTION_MARK_PAID,
    ACTION_UNFREEZE,
    LOCK_KEY_SETTLEMENT_OP,
    SETTLEMENT_BREAKER_CHANNEL,
    SETTLEMENT_NO_PREFIX,
    SETTLEMENT_OP_LOCK_TIMEOUT,
    SettlementStatus,
)
from src.config.constants import OrderStatus
from src.cps.circuit_breaker import CircuitBreaker
from src.dao.order_dao import OrderDAO
from src.dao.settlement_atomic_dao import SettlementAtomicDAO
from src.dao.settlement_operation_log_dao import SettlementOperationLogDAO
from src.dao.settlement_record_dao import SettlementRecordDAO
from src.services.settlement_state_machine import SettlementStateMachine

logger = logging.getLogger("service.settlement_b12")


class CommissionSettlementB12Service:
    """佣金结算状态机编排 Service

    通过构造函数注入 OrderDAO / SettlementRecordDAO / SettlementAtomicDAO /
    SettlementOperationLogDAO / CircuitBreaker，所有 DAO 共享同一 session
    """

    def __init__(
        self,
        order_dao: OrderDAO,
        settlement_dao: SettlementRecordDAO,
        atomic_dao: SettlementAtomicDAO,
        log_dao: SettlementOperationLogDAO,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        """初始化结算编排服务

        Args:
            order_dao: 订单 DAO
            settlement_dao: 结算单 DAO
            atomic_dao: 原子操作 DAO（冻结/解冻）
            log_dao: 操作日志 DAO
            circuit_breaker: B04 熔断器（None 则不熔断，测试用）
        """
        self.order_dao = order_dao
        self.settlement_dao = settlement_dao
        self.atomic_dao = atomic_dao
        self.log_dao = log_dao
        self.circuit_breaker = circuit_breaker

    # ══════════════════════════════════════════════════════
    # 1. 单笔冻结入账（SETTLABLE 订单 → 创建结算单 + frozen += amount）
    # ══════════════════════════════════════════════════════

    async def freeze_on_settlable(
        self,
        order_id: int,
        *,
        delay_days: int = 30,
        operator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """单笔冻结入账（ORDERED → SETTLABLE）

        流程：
        1. 幂等锁（settlement_op:{order_id}:FREEZE）
        2. 熔断检查
        3. 查订单，校验 SETTLABLE(30) 状态
        4. 幂等校验：已存在结算单则跳过
        5. 原子冻结入账（创建结算单 + PENDING 流水 + frozen += amount）
        6. 记录操作日志（CREATE_SETTLEMENT + FREEZE）
        7. 熔断 record_success

        Args:
            order_id: 订单ID
            delay_days: 延迟天数配置快照
            operator_id: 操作人ID（定时任务为空）
        Returns:
            {"status": "success"|"skipped"|"failed", "order_id": int,
             "settlement_id": int, "settlement_no": str, "amount": str}
        Raises:
            ValueError: 幂等拦截 / 熔断中 / 状态机校验失败
        """
        # 1. 幂等锁
        lock_owner = await self._acquire_op_lock(order_id, ACTION_FREEZE)
        try:
            # 2. 熔断检查
            await self._check_breaker()

            # 3. 查订单
            order = await self.order_dao.get_by_id(order_id)
            if order is None:
                raise ValueError(f"订单不存在: order_id={order_id}")

            if order.order_status != int(OrderStatus.SETTLABLE):
                raise ValueError(
                    f"订单状态非 SETTLABLE: order_id={order_id}, "
                    f"status={order.order_status}"
                )

            # 4. 幂等校验
            existing = await self.settlement_dao.get_by_order_id(order_id)
            if existing is not None:
                logger.info(
                    "[freeze] 订单已有结算单，幂等跳过 order_id=%s settlement_id=%s",
                    order_id,
                    existing.id,
                )
                return {
                    "status": "skipped",
                    "order_id": order_id,
                    "settlement_id": existing.id,
                    "settlement_no": existing.settlement_no,
                    "amount": str(existing.user_commission),
                    "message": "订单已有结算单，幂等跳过",
                }

            # 5. 原子冻结入账
            user_commission = Decimal(str(order.user_commission))
            platform_commission = Decimal(str(order.platform_commission))
            settlement_no = self._generate_settlement_no(order_id)

            settlement, flow = await self.atomic_dao.freeze_atomic(
                order=order,
                user_commission=user_commission,
                platform_commission=platform_commission,
                settlement_no=settlement_no,
                delay_days=delay_days,
            )

            # 6. 记录操作日志
            await self._log_operation(
                settlement_id=settlement.id,
                order_id=order_id,
                from_status=SettlementStatus.ORDERED.value,
                to_status=SettlementStatus.SETTLABLE.value,
                action=ACTION_FREEZE,
                amount=user_commission,
                operator_id=operator_id,
                flow_id=flow.id,
                remark=f"确认收货冻结入账 settlement_no={settlement_no}",
            )
            # 创建结算单日志（CREATE_SETTLEMENT）
            await self._log_operation(
                settlement_id=settlement.id,
                order_id=order_id,
                from_status=SettlementStatus.ORDERED.value,
                to_status=SettlementStatus.ORDERED.value,
                action=ACTION_CREATE_SETTLEMENT,
                amount=user_commission,
                operator_id=operator_id,
                flow_id=flow.id,
                remark=f"创建结算单 settlement_no={settlement_no}",
            )

            # 7. 熔断 record_success
            await self._record_success()

            logger.info(
                "[freeze] 冻结入账成功 order_id=%s settlement_id=%s amount=%s",
                order_id,
                settlement.id,
                user_commission,
            )
            return {
                "status": "success",
                "order_id": order_id,
                "settlement_id": settlement.id,
                "settlement_no": settlement_no,
                "amount": str(user_commission),
                "flow_id": flow.id,
            }

        except Exception as e:
            # 熔断 record_failure（非幂等拦截/非状态机校验的异常）
            await self._record_failure()
            raise
        finally:
            await self._release_op_lock(order_id, ACTION_FREEZE, lock_owner)

    # ══════════════════════════════════════════════════════
    # 2. 单笔解冻转可用（SETTLED 订单 → frozen → available）
    # ══════════════════════════════════════════════════════

    async def unfreeze_on_settled(
        self,
        order_id: int,
        *,
        operator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """单笔解冻转可用（SETTLABLE → SETTLED）

        流程：
        1. 幂等锁（settlement_op:{order_id}:UNFREEZE）
        2. 熔断检查
        3. 查结算单，状态机校验（SETTLABLE → SETTLED）
        4. 查订单，校验 SETTLED(40) 状态
        5. 原子解冻（更新结算单 + PENDING→SUCCESS 流水 + frozen→available）
        6. 记录操作日志（UNFREEZE）
        7. 熔断 record_success

        Args:
            order_id: 订单ID
            operator_id: 操作人ID
        Returns:
            {"status": "success"|"skipped"|"failed", ...}
        Raises:
            ValueError: 幂等拦截 / 熔断中 / 状态机校验失败 / 冻结余额不足
        """
        lock_owner = await self._acquire_op_lock(order_id, ACTION_UNFREEZE)
        try:
            await self._check_breaker()

            # 3. 查结算单
            settlement = await self.settlement_dao.get_by_order_id(order_id)
            if settlement is None:
                raise ValueError(f"结算单不存在，无法解冻: order_id={order_id}")

            # 状态机校验
            SettlementStateMachine.validate_transition(
                settlement.settlement_status, SettlementStatus.SETTLED.value
            )

            # 4. 查订单
            order = await self.order_dao.get_by_id(order_id)
            if order is None:
                raise ValueError(f"订单不存在: order_id={order_id}")

            if order.order_status != int(OrderStatus.SETTLED):
                raise ValueError(
                    f"订单状态非 SETTLED: order_id={order_id}, "
                    f"status={order.order_status}"
                )

            # 5. 原子解冻
            settlement, flow = await self.atomic_dao.unfreeze_atomic(
                settlement=settlement,
                order=order,
            )

            # 6. 记录操作日志
            await self._log_operation(
                settlement_id=settlement.id,
                order_id=order_id,
                from_status=SettlementStatus.SETTLABLE.value,
                to_status=SettlementStatus.SETTLED.value,
                action=ACTION_UNFREEZE,
                amount=Decimal(str(settlement.user_commission)),
                operator_id=operator_id,
                flow_id=flow.id,
                remark=f"渠道返利到账解冻转可用 settle_time={settlement.settle_time}",
            )

            await self._record_success()

            logger.info(
                "[unfreeze] 解冻成功 order_id=%s settlement_id=%s amount=%s",
                order_id,
                settlement.id,
                settlement.user_commission,
            )
            return {
                "status": "success",
                "order_id": order_id,
                "settlement_id": settlement.id,
                "settlement_no": settlement.settlement_no,
                "amount": str(settlement.user_commission),
                "flow_id": flow.id,
            }

        except Exception:
            await self._record_failure()
            raise
        finally:
            await self._release_op_lock(order_id, ACTION_UNFREEZE, lock_owner)

    # ══════════════════════════════════════════════════════
    # 3. 标记已打款（SETTLED → PAID，提现成功联动）
    # ══════════════════════════════════════════════════════

    async def mark_paid(
        self,
        settlement_id: int,
        *,
        operator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """标记结算单已打款（SETTLED → PAID）

        由提现成功回调联动触发（B11 on_transfer_success 可调用）

        Args:
            settlement_id: 结算单ID
            operator_id: 操作人ID
        Returns:
            {"status": "success"|"skipped", ...}
        Raises:
            ValueError: 结算单不存在 / 状态机校验失败
        """
        settlement = await self.settlement_dao.get_by_id(settlement_id)
        if settlement is None:
            raise ValueError(f"结算单不存在: settlement_id={settlement_id}")

        # 终态幂等跳过
        if SettlementStateMachine.is_terminal(settlement.settlement_status):
            return {
                "status": "skipped",
                "settlement_id": settlement_id,
                "message": f"结算单已为终态 {settlement.settlement_status}，跳过",
            }

        # 状态机校验
        SettlementStateMachine.validate_transition(
            settlement.settlement_status, SettlementStatus.PAID.value
        )

        # 更新结算单
        updated = await self.settlement_dao.update_by_id(
            settlement_id,
            {
                "settlement_status": SettlementStatus.PAID.value,
                "paid_time": datetime.now(),
                "remark": "用户提现成功，标记已打款",
            },
        )

        # 记录操作日志
        await self._log_operation(
            settlement_id=settlement_id,
            order_id=settlement.order_id,
            from_status=SettlementStatus.SETTLED.value,
            to_status=SettlementStatus.PAID.value,
            action=ACTION_MARK_PAID,
            amount=Decimal("0"),
            operator_id=operator_id,
            flow_id=None,
            remark="提现成功联动标记已打款",
        )

        logger.info(
            "[mark_paid] 标记已打款 settlement_id=%s order_id=%s",
            settlement_id,
            settlement.order_id,
        )
        return {
            "status": "success",
            "settlement_id": settlement_id,
            "order_id": settlement.order_id,
            "settlement_no": (
                updated.settlement_no if updated else settlement.settlement_no
            ),
        }

    # ══════════════════════════════════════════════════════
    # 4. 批量冻结（定时任务调用）
    # ══════════════════════════════════════════════════════

    async def batch_freeze_settlable(
        self,
        limit: int = 200,
        delay_days: int = 30,
    ) -> Dict[str, Any]:
        """批量冻结 SETTLABLE 订单（定时任务入口）

        逐单 try/except，单条失败不阻断整体执行

        Args:
            limit: 单轮处理上限
            delay_days: 延迟天数配置快照
        Returns:
            {status, total, success_count, failed_count, skipped_count, details}
        """
        orders, total = (
            await self.settlement_dao.list_settlable_orders_without_settlement(
                page=1, page_size=limit
            )
        )

        if not orders:
            logger.info("[batch_freeze] 无待冻结订单")
            return self._empty_batch_result()

        success_count = 0
        failed_count = 0
        skipped_count = 0
        details: List[Dict[str, Any]] = []

        for order in orders:
            try:
                result = await self.freeze_on_settlable(
                    order_id=order.id,
                    delay_days=delay_days,
                )
                if result["status"] == "skipped":
                    skipped_count += 1
                else:
                    success_count += 1
                details.append(result)
            except Exception as e:
                failed_count += 1
                logger.error(
                    "[batch_freeze] 单笔冻结失败 order_id=%s error=%s",
                    order.id,
                    e,
                    exc_info=True,
                )
                details.append(
                    {
                        "status": "failed",
                        "order_id": order.id,
                        "message": str(e),
                    }
                )

        status = "success" if failed_count == 0 else "partial"
        logger.info(
            "[batch_freeze] 完成 total=%s success=%s failed=%s skipped=%s",
            total,
            success_count,
            failed_count,
            skipped_count,
        )
        return {
            "status": status,
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "details": details,
        }

    # ══════════════════════════════════════════════════════
    # 5. 批量解冻（定时任务调用）
    # ══════════════════════════════════════════════════════

    async def batch_unfreeze_settled(
        self,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """批量解冻 SETTLED 订单（定时任务入口）

        逐单 try/except，单条失败不阻断整体执行

        Args:
            limit: 单轮处理上限
        Returns:
            {status, total, success_count, failed_count, skipped_count, details}
        """
        settlements, total = await self.settlement_dao.list_settled_pending_unfreeze(
            page=1, page_size=limit
        )

        if not settlements:
            logger.info("[batch_unfreeze] 无待解冻结算单")
            return self._empty_batch_result()

        success_count = 0
        failed_count = 0
        skipped_count = 0
        details: List[Dict[str, Any]] = []

        for settlement in settlements:
            try:
                result = await self.unfreeze_on_settled(
                    order_id=settlement.order_id,
                )
                if result["status"] == "skipped":
                    skipped_count += 1
                else:
                    success_count += 1
                details.append(result)
            except Exception as e:
                failed_count += 1
                logger.error(
                    "[batch_unfreeze] 单笔解冻失败 settlement_id=%s order_id=%s error=%s",
                    settlement.id,
                    settlement.order_id,
                    e,
                    exc_info=True,
                )
                details.append(
                    {
                        "status": "failed",
                        "settlement_id": settlement.id,
                        "order_id": settlement.order_id,
                        "message": str(e),
                    }
                )

        status = "success" if failed_count == 0 else "partial"
        logger.info(
            "[batch_unfreeze] 完成 total=%s success=%s failed=%s skipped=%s",
            total,
            success_count,
            failed_count,
            skipped_count,
        )
        return {
            "status": status,
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "details": details,
        }

    # ══════════════════════════════════════════════════════
    # 6. 后台查询接口
    # ══════════════════════════════════════════════════════

    async def list_settlements_with_filters(
        self,
        *,
        settlement_no: Optional[str] = None,
        order_id: Optional[int] = None,
        user_id: Optional[int] = None,
        channel_code: Optional[str] = None,
        settlement_status: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """后台结算单分页查询（支持多条件筛选 + 导出）

        Returns:
            {"list": [...], "total": int, "page": int, "page_size": int}
        """
        items, total = await self.settlement_dao.list_with_filters(
            settlement_no=settlement_no,
            order_id=order_id,
            user_id=user_id,
            channel_code=channel_code,
            settlement_status=settlement_status,
            min_amount=min_amount,
            max_amount=max_amount,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        return {
            "list": [it.to_dict() for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_overdue_settlable(
        self,
        delay_days: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """超期未解冻结算单查询（后台预警）

        Args:
            delay_days: 超期阈值天数
        Returns:
            {"list": [...], "total": int, "page": int, "page_size": int}
        """
        items, total = await self.settlement_dao.list_overdue_settlable(
            delay_days, page=page, page_size=page_size
        )
        return {
            "list": [it.to_dict() for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_settlement_detail(
        self,
        settlement_id: int,
    ) -> Dict[str, Any]:
        """结算单详情（含操作历史）

        Args:
            settlement_id: 结算单ID
        Returns:
            {"settlement": {...}, "logs": [...]}
        Raises:
            ValueError: 结算单不存在
        """
        settlement = await self.settlement_dao.get_by_id(settlement_id)
        if settlement is None:
            raise ValueError(f"结算单不存在: settlement_id={settlement_id}")

        logs, log_total = await self.log_dao.list_by_settlement_id(
            settlement_id, page=1, page_size=50
        )
        return {
            "settlement": settlement.to_dict(),
            "logs": [log.to_dict() for log in logs],
            "log_total": log_total,
        }

    async def get_settlement_logs(
        self,
        settlement_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """查询结算单操作历史"""
        items, total = await self.log_dao.list_by_settlement_id(
            settlement_id, page=page, page_size=page_size
        )
        return {
            "list": [it.to_dict() for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_operation_logs_with_filters(
        self,
        *,
        settlement_id: Optional[int] = None,
        order_id: Optional[int] = None,
        action: Optional[str] = None,
        operator_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """多条件查询结算操作日志（后台审计/导出）"""
        items, total = await self.log_dao.list_with_filters(
            settlement_id=settlement_id,
            order_id=order_id,
            action=action,
            operator_id=operator_id,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        return {
            "list": [it.to_dict() for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ══════════════════════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════════════════════

    async def _acquire_op_lock(self, order_id: int, action: str) -> Optional[str]:
        """获取单订单结算操作幂等锁

        锁 key：gaking:prod:lock:settlement_op:{order_id}:{action}
        TTL：60s（防止定时任务与手动操作并发处理同一订单）

        Raises:
            ValueError: 锁已被占用
        """
        lock_key = f"{LOCK_KEY_SETTLEMENT_OP}{order_id}:{action}"
        lock_owner = await LockUtil.acquire_lock(
            lock_key, timeout=SETTLEMENT_OP_LOCK_TIMEOUT
        )
        if lock_owner is None:
            raise ValueError(
                f"该订单结算操作正在处理中，请勿重复操作: order_id={order_id} action={action}"
            )
        return lock_owner

    async def _release_op_lock(
        self, order_id: int, action: str, lock_owner: Optional[str]
    ) -> None:
        """释放单订单结算操作幂等锁"""
        if lock_owner is None:
            return
        lock_key = f"{LOCK_KEY_SETTLEMENT_OP}{order_id}:{action}"
        await LockUtil.release_lock(lock_key, lock_owner)

    async def _check_breaker(self) -> None:
        """熔断检查（熔断中抛 ValueError）"""
        if self.circuit_breaker is None:
            return
        allowed = await self.circuit_breaker.allow_request(SETTLEMENT_BREAKER_CHANNEL)
        if not allowed:
            raise ValueError(
                f"结算熔断中，跳过处理: channel={SETTLEMENT_BREAKER_CHANNEL}"
            )

    async def _record_success(self) -> None:
        """记录熔断成功"""
        if self.circuit_breaker is None:
            return
        try:
            await self.circuit_breaker.record_success(SETTLEMENT_BREAKER_CHANNEL)
        except Exception as e:
            logger.warning("[breaker] record_success 失败: %s", e)

    async def _record_failure(self) -> None:
        """记录熔断失败"""
        if self.circuit_breaker is None:
            return
        try:
            await self.circuit_breaker.record_failure(SETTLEMENT_BREAKER_CHANNEL)
        except Exception as e:
            logger.warning("[breaker] record_failure 失败: %s", e)

    async def _log_operation(
        self,
        settlement_id: int,
        order_id: int,
        from_status: str,
        to_status: str,
        action: str,
        amount: Decimal,
        operator_id: Optional[int] = None,
        flow_id: Optional[int] = None,
        remark: str = "",
    ) -> None:
        """记录结算操作日志（失败不阻断主流程）"""
        try:
            log_data = {
                "settlement_id": settlement_id,
                "order_id": order_id,
                "from_status": from_status,
                "to_status": to_status,
                "action": action,
                "operator_id": operator_id,
                "amount": amount,
                "flow_id": flow_id,
                "remark": remark,
            }
            await self.log_dao.create(log_data)
            logger.debug(
                "[settlement_log] settlement_id=%s %s→%s action=%s",
                settlement_id,
                from_status,
                to_status,
                action,
            )
        except Exception as e:
            logger.warning(
                "[settlement_log] 操作日志记录失败 settlement_id=%s action=%s: %s",
                settlement_id,
                action,
                e,
                exc_info=True,
            )

    @staticmethod
    def _generate_settlement_no(order_id: int) -> str:
        """生成结算单号：GAKS + YYYYMMDDHHMMSS + _ + order_id"""
        return (
            f"{SETTLEMENT_NO_PREFIX}"
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{order_id}"
        )

    @staticmethod
    def _empty_batch_result() -> Dict[str, Any]:
        """空批次结果"""
        return {
            "status": "success",
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "details": [],
        }
