# @ai-generated
"""
B10 站内消息 DAO
继承 BaseDAO；提供消息创建/列表/已读/未读计数/批量推送查询等能力
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.business.b10_user_message_model import UserMessage

logger = logging.getLogger("dao.b10_user_message")


class UserMessageDAO(BaseDAO):
    """站内消息 DAO"""

    model_class = UserMessage

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 创建消息 ─────────────────────────────────────────

    async def create_message(self, data: Dict[str, Any]) -> UserMessage:
        """创建站内消息并返回实例

        Args:
            data: 消息数据字典
        Returns:
            消息实例
        """
        return await self.create(data)

    # ── 批量创建消息 ─────────────────────────────────────

    async def batch_create_messages(self, messages: List[Dict[str, Any]]) -> int:
        """批量创建站内消息

        Args:
            messages: 消息数据字典列表
        Returns:
            创建成功条数
        """
        count = 0
        for msg in messages:
            try:
                await self.create(msg)
                count += 1
            except Exception as e:
                logger.error("[batch_create] 消息创建失败: %s", e, exc_info=True)
        return count

    # ── 用户消息列表查询 ─────────────────────────────────

    async def list_by_user_id(
        self,
        user_id: int,
        *,
        message_type: Optional[str] = None,
        is_read: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[UserMessage], int]:
        """按用户分页查询消息列表（按创建时间倒序）

        Args:
            user_id: 用户ID
            message_type: 消息类型筛选（可选）
            is_read: 已读状态筛选（可选，0=未读 1=已读）
            page: 页码
            page_size: 每页条数
        Returns:
            (消息列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query().where(UserMessage.user_id == user_id)
        conditions = []
        if message_type is not None:
            conditions.append(UserMessage.message_type == message_type)
        if is_read is not None:
            conditions.append(UserMessage.is_read == is_read)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(UserMessage.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    # ── 未读消息计数 ─────────────────────────────────────

    async def count_unread_by_user(self, user_id: int) -> int:
        """查询用户未读消息数

        Args:
            user_id: 用户ID
        Returns:
            未读消息数量
        """
        stmt = (
            select(func.count())
            .select_from(UserMessage)
            .where(
                and_(
                    UserMessage.user_id == user_id,
                    UserMessage.is_read == 0,
                    UserMessage.is_delete == False,  # noqa: E712
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ── 标记已读 ─────────────────────────────────────────

    async def mark_as_read(self, message_id: int, user_id: int) -> Optional[UserMessage]:
        """标记单条消息为已读（校验 user_id 归属）

        Args:
            message_id: 消息ID
            user_id: 用户ID（归属校验）
        Returns:
            更新后的消息实例 或 None（不存在/不归属）
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stmt = (
            update(UserMessage)
            .where(
                and_(
                    UserMessage.id == message_id,
                    UserMessage.user_id == user_id,
                    UserMessage.is_delete == False,  # noqa: E712
                )
            )
            .values(is_read=1, read_time=now_str)
        )
        await self.session.execute(stmt)
        await self.session.commit()
        # 返回更新后的记录
        return await self.get_by_id(message_id)

    async def mark_all_as_read(self, user_id: int) -> int:
        """标记用户全部消息为已读

        Args:
            user_id: 用户ID
        Returns:
            更新的记录数
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stmt = (
            update(UserMessage)
            .where(
                and_(
                    UserMessage.user_id == user_id,
                    UserMessage.is_read == 0,
                    UserMessage.is_delete == False,  # noqa: E712
                )
            )
            .values(is_read=1, read_time=now_str)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    # ── 后台管理查询 ─────────────────────────────────────

    async def list_with_filters(
        self,
        *,
        user_id: Optional[int] = None,
        message_type: Optional[str] = None,
        is_read: Optional[int] = None,
        push_status: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[UserMessage], int]:
        """多条件分页查询（后台消息管理用）

        Args:
            user_id: 用户ID筛选
            message_type: 消息类型筛选
            is_read: 已读状态筛选
            push_status: 推送状态筛选
            start_time: 创建时间起始
            end_time: 创建时间截止
            page: 页码
            page_size: 每页条数
        Returns:
            (消息列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query()
        conditions = []
        if user_id is not None:
            conditions.append(UserMessage.user_id == user_id)
        if message_type is not None:
            conditions.append(UserMessage.message_type == message_type)
        if is_read is not None:
            conditions.append(UserMessage.is_read == is_read)
        if push_status is not None:
            conditions.append(UserMessage.push_status == push_status)
        if start_time is not None:
            conditions.append(UserMessage.create_time >= start_time)
        if end_time is not None:
            conditions.append(UserMessage.create_time < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(UserMessage.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    # ── 待推送消息查询 ───────────────────────────────────

    async def list_pending_push(
        self,
        limit: int = 100,
    ) -> List[UserMessage]:
        """查询待推送消息（push_status=0，按创建时间升序，先进先出）

        Args:
            limit: 最大返回条数
        Returns:
            待推送消息列表
        """
        stmt = (
            self._active_query()
            .where(UserMessage.push_status == 0)
            .order_by(UserMessage.create_time.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_push_success(self, message_id: int) -> None:
        """标记消息推送成功

        Args:
            message_id: 消息ID
        """
        stmt = (
            update(UserMessage)
            .where(UserMessage.id == message_id)
            .values(push_status=1)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def mark_push_failed(self, message_id: int, error: str) -> None:
        """标记消息推送失败

        Args:
            message_id: 消息ID
            error: 失败原因
        """
        stmt = (
            update(UserMessage)
            .where(UserMessage.id == message_id)
            .values(push_status=2, push_error=error[:512])
        )
        await self.session.execute(stmt)
        await self.session.commit()