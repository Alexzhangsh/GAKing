# @ai-generated
"""
用户提现申请 DAO
继承 BaseDAO；状态变更后失效对应用户账户缓存（余额联动兜底）；不含业务逻辑
仅做数据存取，业务规则（状态机校验、手续费计算）在 Service 层
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.redis_client import RedisClient
from src.config.constants import CACHE_KEY_USER_ACCOUNT
from src.dao.base_dao import BaseDAO
from src.models.business.user_withdraw_apply_model import UserWithdrawApply

logger = logging.getLogger("dao.user_withdraw_apply")


class UserWithdrawApplyDAO(BaseDAO):
    """用户提现申请 DAO"""

    model_class = UserWithdrawApply

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 专属扩展方法 ────────────────────────────────────

    async def get_by_apply_no(self, apply_no: str) -> Optional[UserWithdrawApply]:
        """按提现单号查询（自动过滤软删除）

        Args:
            apply_no: 提现单号
        Returns:
            申请实例 或 None
        """
        stmt = self._active_query().where(UserWithdrawApply.apply_no == apply_no)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[UserWithdrawApply], int]:
        """按用户分页查询提现记录（按创建时间倒序）

        Args:
            user_id: 平台用户ID
            page: 页码
            page_size: 每页条数
        Returns:
            (申请列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query().where(UserWithdrawApply.user_id == user_id)

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(UserWithdrawApply.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    async def list_with_filters(
        self,
        *,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[UserWithdrawApply], int]:
        """多条件分页查询（后台审核列表用）

        Args:
            user_id: 平台用户ID筛选（可选）
            status: 提现状态筛选（可选）
            page: 页码
            page_size: 每页条数
        Returns:
            (申请列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query()
        conditions = []
        if user_id is not None:
            conditions.append(UserWithdrawApply.user_id == user_id)
        if status is not None:
            conditions.append(UserWithdrawApply.status == status)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(UserWithdrawApply.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    # ── 覆写基类写方法：状态变更后失效对应用户账户缓存 ──

    async def create(self, data: Dict[str, Any]) -> UserWithdrawApply:
        """覆写基类：提现申请创建后失效对应用户账户缓存

        发起提现时账户余额已变动（Service 先调 adjust_balance），此处兜底失效账户缓存，
        确保后续查询读到最新可用/冻结余额。
        """
        result = await super().create(data)
        await RedisClient.delete(f"{CACHE_KEY_USER_ACCOUNT}{result.user_id}")
        logger.info(
            "[cache_invalidate] user_account user_id=%s (withdraw_apply create)",
            result.user_id,
        )
        return result

    async def update_by_id(
        self,
        item_id: int,
        data: Dict[str, Any],
    ) -> Optional[UserWithdrawApply]:
        """覆写基类：提现申请状态变更后失效对应用户账户缓存

        审核通过/驳回/打款完成等状态变更可能联动余额变动（Service 层先调 adjust_balance），
        此处兜底失效账户缓存。
        """
        result = await super().update_by_id(item_id, data)
        if result is not None:
            await RedisClient.delete(f"{CACHE_KEY_USER_ACCOUNT}{result.user_id}")
            logger.info(
                "[cache_invalidate] user_account user_id=%s (withdraw_apply update)",
                result.user_id,
            )
        return result

    # ══════════════════════════════════════════════════════
    # B09 新增：单日累计提现金额查询（提现规则校验器使用）
    # ══════════════════════════════════════════════════════

    async def sum_apply_amount_by_user_and_date(
        self,
        user_id: int,
        target_date: date,
    ) -> "Decimal":
        """查询用户指定日期的累计提现金额（不含 REJECTED 驳回单）

        统计状态：PENDING / APPROVED / PROCESSING / SUCCESS（驳回单 REJECTED 不计入）
        SQL 语义：
            SELECT COALESCE(SUM(apply_amount), 0)
            FROM user_withdraw_apply
            WHERE user_id = :user_id
              AND DATE(create_time) = :target_date
              AND status != 'REJECTED'
              AND is_delete = 0

        Args:
            user_id: 平台用户ID
            target_date: 目标日期
        Returns:
            累计提现金额 (Decimal)，无记录返回 Decimal("0")
        """
        from datetime import timedelta
        from decimal import Decimal

        # 构造当日 0:00 ~ 次日 0:00 时间范围（左闭右开，利用 create_time 索引）
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

        stmt = select(func.coalesce(func.sum(UserWithdrawApply.apply_amount), 0)).where(
            and_(
                UserWithdrawApply.user_id == user_id,
                UserWithdrawApply.create_time >= start,
                UserWithdrawApply.create_time < end,
                UserWithdrawApply.status != "REJECTED",
                UserWithdrawApply.is_delete == False,  # noqa: E712
            )
        )
        result = await self.session.execute(stmt)
        total = result.scalar()
        if total is None:
            return Decimal("0")
        try:
            return Decimal(str(total))
        except Exception:
            return Decimal("0")
