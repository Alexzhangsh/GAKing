# @ai-generated
"""
B13-1 提现管理后台 Service
业务逻辑层：提现列表、详情、审核、转账信息更新
所有写操作自动记录审计日志
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select

from src.common.b14_audit_util import AuditLogger
from src.dao.user_withdraw_apply_dao import UserWithdrawApplyDAO
from src.dao.withdraw_review_log_dao import WithdrawReviewLogDAO
from src.db.base import DatabaseManager
from src.models.business.user_withdraw_apply_model import UserWithdrawApply

logger = logging.getLogger("services.b13_withdraw_admin")


class B13WithdrawAdminService:
    """提现管理后台 Service"""

    # ── 查询类方法 ────────────────────────────────────

    @classmethod
    async def list_withdraws(
        cls,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """提现列表（多条件分页查询）

        Args:
            user_id: 平台用户ID筛选
            status: 提现状态筛选
            start_time: 创建时间起始
            end_time: 创建时间截止
            page: 页码
            page_size: 每页条数
        Returns:
            (提现列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        async with DatabaseManager.get_session() as session:
            dao = UserWithdrawApplyDAO(session)
            stmt = dao._active_query()
            conditions = []

            if user_id is not None:
                conditions.append(UserWithdrawApply.user_id == user_id)
            if status is not None:
                conditions.append(UserWithdrawApply.status == status)
            if start_time is not None:
                conditions.append(UserWithdrawApply.create_time >= start_time)
            if end_time is not None:
                conditions.append(UserWithdrawApply.create_time < end_time)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            # 总记录数
            count_query = select(func.count()).select_from(stmt.subquery())
            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0

            # 分页查询
            offset = (page - 1) * page_size
            page_query = (
                stmt.order_by(UserWithdrawApply.create_time.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await session.execute(page_query)
            items = result.scalars().all()

            return [cls._to_withdraw_dict(item) for item in items], total

    @classmethod
    async def get_withdraw_detail(
        cls, apply_id: int
    ) -> Optional[Dict[str, Any]]:
        """提现详情

        Args:
            apply_id: 提现申请ID
        Returns:
            提现详情字典 或 None
        """
        async with DatabaseManager.get_session() as session:
            dao = UserWithdrawApplyDAO(session)
            item = await dao.get_by_id(apply_id)
            if item is None:
                return None
            return cls._to_withdraw_dict(item, detail=True)

    @classmethod
    async def get_review_logs(
        cls,
        apply_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取提现审核日志（按时间升序）

        Args:
            apply_id: 提现申请ID
            page: 页码
            page_size: 每页条数
        Returns:
            (日志列表, 总记录数)
        """
        async with DatabaseManager.get_session() as session:
            log_dao = WithdrawReviewLogDAO(session)
            items, total = await log_dao.list_by_apply_id(
                apply_id=apply_id,
                page=page,
                page_size=page_size,
            )
            result = []
            for item in items:
                result.append({
                    "id": item.id,
                    "apply_id": item.apply_id,
                    "from_status": item.from_status,
                    "to_status": item.to_status,
                    "action": item.action,
                    "operator_id": item.operator_id,
                    "remark": item.remark or "",
                    "transfer_batch_id": item.transfer_batch_id or "",
                    "create_time": item.create_time.isoformat() if item.create_time else None,
                })
            return result, total

    # ── 写操作类方法 ────────────────────────────────────

    @classmethod
    async def review_withdraw(
        cls,
        apply_id: int,
        action: str,
        review_remark: str,
        reject_reason: str,
        operator_id: int,
        operator_name: str = "",
    ) -> Dict[str, Any]:
        """审核提现（通过/驳回）

        状态机：
            approve: PENDING → APPROVED
            reject:  PENDING/APPROVED → REJECTED

        Args:
            apply_id: 提现申请ID
            action: 审核动作（approve/reject）
            review_remark: 审核备注
            reject_reason: 驳回原因
            operator_id: 操作人ID
            operator_name: 操作人姓名
        Returns:
            更新后的提现详情
        Raises:
            ValueError: 校验不通过时抛出
        """
        async with DatabaseManager.get_session() as session:
            dao = UserWithdrawApplyDAO(session)
            item = await dao.get_by_id(apply_id)
            if item is None:
                raise ValueError("提现申请不存在")

            # 状态机校验
            if action == "approve":
                if item.status not in ("PENDING",):
                    raise ValueError(f"当前状态 {item.status} 不允许审核通过")
                from_status = item.status
                to_status = "APPROVED"
                update_data: Dict[str, Any] = {
                    "status": to_status,
                    "review_user_id": operator_id,
                    "review_remark": review_remark,
                    "review_time": datetime.now(),
                }
            elif action == "reject":
                if item.status not in ("PENDING", "APPROVED"):
                    raise ValueError(f"当前状态 {item.status} 不允许驳回")
                from_status = item.status
                to_status = "REJECTED"
                update_data = {
                    "status": to_status,
                    "review_user_id": operator_id,
                    "review_remark": review_remark,
                    "reject_reason": reject_reason,
                    "review_time": datetime.now(),
                }
            else:
                raise ValueError(f"无效的审核动作: {action}")

            updated = await dao.update_by_id(apply_id, update_data)
            if updated is None:
                raise ValueError("更新提现申请失败")

            # 写入审核日志
            log_dao = WithdrawReviewLogDAO(session)
            log_data = {
                "apply_id": apply_id,
                "from_status": from_status,
                "to_status": to_status,
                "action": action.upper(),
                "operator_id": operator_id,
                "remark": review_remark or reject_reason,
            }
            await log_dao.create(log_data)

            # 审计日志
            await AuditLogger.log(
                action=f"WITHDRAW_{action.upper()}",
                target_type="withdraw_apply",
                target_id=apply_id,
                details={
                    "from_status": from_status,
                    "to_status": to_status,
                    "review_remark": review_remark[:200] if review_remark else "",
                    "reject_reason": reject_reason[:200] if reject_reason else "",
                },
                user_id=operator_id,
                user_name=operator_name,
            )

            logger.info(
                "[withdraw_review] apply_id=%s action=%s from=%s to=%s operator=%s",
                apply_id, action, from_status, to_status, operator_id,
            )

            return cls._to_withdraw_dict(updated, detail=True)

    @classmethod
    async def update_transfer_info(
        cls,
        apply_id: int,
        transfer_batch_id: str,
        operator_id: int,
        operator_name: str = "",
    ) -> Dict[str, Any]:
        """更新转账信息（微信打款后回调）

        状态流转：APPROVED/PROCESSING → PROCESSING（更新转账批次号和时间）

        Args:
            apply_id: 提现申请ID
            transfer_batch_id: 微信转账批次ID
            operator_id: 操作人ID
            operator_name: 操作人姓名
        Returns:
            更新后的提现详情
        Raises:
            ValueError: 校验不通过时抛出
        """
        async with DatabaseManager.get_session() as session:
            dao = UserWithdrawApplyDAO(session)
            item = await dao.get_by_id(apply_id)
            if item is None:
                raise ValueError("提现申请不存在")

            if item.status not in ("APPROVED", "PROCESSING"):
                raise ValueError(f"当前状态 {item.status} 不允许更新转账信息")

            from_status = item.status
            update_data = {
                "transfer_batch_id": transfer_batch_id,
                "status": "PROCESSING",
                "transfer_time": datetime.now(),
            }
            updated = await dao.update_by_id(apply_id, update_data)
            if updated is None:
                raise ValueError("更新转账信息失败")

            # 写入审核日志
            log_dao = WithdrawReviewLogDAO(session)
            log_data = {
                "apply_id": apply_id,
                "from_status": from_status,
                "to_status": "PROCESSING",
                "action": "TRANSFER",
                "operator_id": operator_id,
                "remark": f"更新转账批次: {transfer_batch_id}",
                "transfer_batch_id": transfer_batch_id,
            }
            await log_dao.create(log_data)

            # 审计日志
            await AuditLogger.log(
                action="WITHDRAW_TRANSFER",
                target_type="withdraw_apply",
                target_id=apply_id,
                details={
                    "transfer_batch_id": transfer_batch_id,
                    "from_status": from_status,
                    "to_status": "PROCESSING",
                },
                user_id=operator_id,
                user_name=operator_name,
            )

            logger.info(
                "[withdraw_transfer] apply_id=%s batch_id=%s operator=%s",
                apply_id, transfer_batch_id, operator_id,
            )

            return cls._to_withdraw_dict(updated, detail=True)

    # ── 内部工具方法 ────────────────────────────────────

    @classmethod
    def _to_withdraw_dict(
        cls, item: UserWithdrawApply, detail: bool = False
    ) -> Dict[str, Any]:
        """将模型实例转为响应字典

        Args:
            item: UserWithdrawApply 模型实例
            detail: 是否包含详情字段（如 transfer_batch_id）
        Returns:
            字典
        """
        result: Dict[str, Any] = {
            "id": item.id,
            "apply_no": item.apply_no,
            "user_id": item.user_id,
            "apply_amount": str(item.apply_amount) if item.apply_amount else "0.00",
            "fee": str(item.fee) if item.fee else "0.00",
            "actual_amount": str(item.actual_amount) if item.actual_amount else "0.00",
            "status": item.status,
            "review_user_id": item.review_user_id,
            "review_remark": item.review_remark or "",
            "review_time": item.review_time.isoformat() if item.review_time else None,
            "transfer_time": item.transfer_time.isoformat() if item.transfer_time else None,
            "reject_reason": item.reject_reason or "",
            "remark": item.remark or "",
            "create_time": item.create_time.isoformat() if item.create_time else None,
        }
        if detail:
            result["transfer_batch_id"] = item.transfer_batch_id or ""
        return result