# @ai-generated
"""
X02-1 用户会员记录 DAO（新建文件）
继承 BaseDAO；提供会员记录分页查询、有效会员查询、到期批量标记能力
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select

from src.dao.base_dao import BaseDAO
from src.models.business.user_member_record_model import UserMemberRecord

logger = logging.getLogger("dao.user_member_record")


class UserMemberRecordDAO(BaseDAO):
    """用户会员记录 DAO"""

    model_class = UserMemberRecord

    # ── 有效会员查询 ──────────────────────────────────────

    async def get_active_record(self, user_id: int) -> Optional[UserMemberRecord]:
        """查询用户当前生效中的会员记录（status=active 且未到期）"""
        now = datetime.now()
        stmt = (
            self._active_query()
            .where(
                and_(
                    UserMemberRecord.user_id == user_id,
                    UserMemberRecord.status == "active",
                    UserMemberRecord.expire_at > now,
                )
            )
            .order_by(UserMemberRecord.expire_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 分页查询 ──────────────────────────────────────────

    async def paginate_records(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        package_id: Optional[int] = None,
        keyword: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[List[UserMemberRecord], int]:
        """分页查询会员记录（支持用户/状态/套餐/关键字/时间筛选）"""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query()
        conditions = []
        if user_id is not None:
            conditions.append(UserMemberRecord.user_id == user_id)
        if status:
            conditions.append(UserMemberRecord.status == status)
        if package_id is not None:
            conditions.append(UserMemberRecord.package_id == package_id)
        if keyword:
            like = f"%{keyword}%"
            conditions.append(UserMemberRecord.package_name.like(like))
        if start_time is not None:
            conditions.append(UserMemberRecord.started_at >= start_time)
        if end_time is not None:
            conditions.append(UserMemberRecord.started_at < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(UserMemberRecord.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    # ── 到期批量标记（定时任务） ──────────────────────────

    async def mark_expired_before(self, cutoff: datetime) -> int:
        """将已到期的 active 会员记录批量标记为 expired

        Args:
            cutoff: 到期时间阈值（早于该时间且 status=active 的记录置为 expired）
        Returns:
            更新的记录数
        """
        stmt = (
            select(UserMemberRecord)
            .where(
                and_(
                    UserMemberRecord.is_delete == False,  # noqa: E712
                    UserMemberRecord.status == "active",
                    UserMemberRecord.expire_at <= cutoff,
                )
            )
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())

        for record in records:
            record.status = "expired"
            record.update_time = datetime.now()

        if records:
            await self.session.commit()
            logger.info(
                "[dao] 会员到期标记 count=%s cutoff=%s", len(records), cutoff
            )

        return len(records)

    # ── 导出全量查询 ──────────────────────────────────────

    async def list_for_export(
        self,
        *,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        package_id: Optional[int] = None,
        keyword: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[UserMemberRecord]:
        """导出用全量查询（与分页查询同条件，无分页总数统计）"""
        stmt = self._active_query()
        conditions = []
        if user_id is not None:
            conditions.append(UserMemberRecord.user_id == user_id)
        if status:
            conditions.append(UserMemberRecord.status == status)
        if package_id is not None:
            conditions.append(UserMemberRecord.package_id == package_id)
        if keyword:
            like = f"%{keyword}%"
            conditions.append(UserMemberRecord.package_name.like(like))
        if start_time is not None:
            conditions.append(UserMemberRecord.started_at >= start_time)
        if end_time is not None:
            conditions.append(UserMemberRecord.started_at < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = (
            stmt.order_by(UserMemberRecord.create_time.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
