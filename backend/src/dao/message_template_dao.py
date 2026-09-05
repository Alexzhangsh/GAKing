# @ai-generated
"""
F04 营销消息模块 DAO 层
复用 BaseDAO 通用增删改查/分页/软删除能力
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.system.message_template import (
    MessageTemplate,
    PushRecord,
    SubscribeBinding,
)

logger = logging.getLogger("dao.message_template")


class MessageTemplateDao(BaseDAO):
    """消息模板 DAO"""

    model_class = MessageTemplate

    async def list_templates(
        self,
        page: int = 1,
        page_size: int = 20,
        template_type: Optional[int] = None,
        status: Optional[int] = None,
    ) -> Tuple[List[MessageTemplate], int]:
        """分页查询消息模板列表（支持按类型+状态筛选）"""
        filters: Dict[str, Any] = {}
        if template_type is not None:
            filters["template_type"] = template_type
        if status is not None:
            filters["status"] = status
        return await self.paginate_list(
            page=page, page_size=page_size, filters=filters or None, order_by="-create_time"
        )

    async def toggle_status(self, template_id: int) -> Optional[MessageTemplate]:
        """切换模板启停状态"""
        obj = await self.get_by_id(template_id)
        if obj is None:
            return None
        obj.status = 0 if obj.status == 1 else 1
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return obj


class PushRecordDao(BaseDAO):
    """推送记录 DAO（无软删除）"""

    model_class = PushRecord

    async def list_records(
        self,
        page: int = 1,
        page_size: int = 20,
        template_id: Optional[int] = None,
        user_id: Optional[int] = None,
        push_status: Optional[int] = None,
    ) -> Tuple[List[PushRecord], int]:
        """分页查询推送记录（支持按模板+用户+状态筛选）"""
        stmt = select(self.model_class)
        conditions = []
        if template_id is not None:
            conditions.append(self.model_class.template_id == str(template_id))
        if user_id is not None:
            conditions.append(self.model_class.user_id == str(user_id))
        if push_status is not None:
            conditions.append(self.model_class.push_status == push_status)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 统计总数
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        stmt = stmt.order_by(self.model_class.create_time.desc()).offset(offset).limit(page_size)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total


class SubscribeBindingDao(BaseDAO):
    """订阅消息绑定 DAO（无软删除）"""

    model_class = SubscribeBinding

    async def get_by_user_and_template(
        self, user_id: int, template_id: int
    ) -> Optional[SubscribeBinding]:
        """按用户+模板查询单条订阅绑定（F05 用户端订阅状态查询）"""
        stmt = select(self.model_class).where(
            and_(
                self.model_class.user_id == str(user_id),
                self.model_class.template_id == str(template_id),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_binding(
        self,
        user_id: int,
        template_id: int,
        subscribe_status: int,
        subscribe_time: Optional[datetime] = None,
        expire_time: Optional[datetime] = None,
    ) -> SubscribeBinding:
        """创建或更新订阅绑定（F05 用户端订阅授权）

        已存在记录 → 更新状态/时间；不存在 → 新增。
        微信一次性订阅模板有效期 7 天，expire_time 由调用方计算。
        """
        binding = await self.get_by_user_and_template(user_id, template_id)
        if binding is None:
            binding = SubscribeBinding(
                user_id=str(user_id),
                template_id=str(template_id),
                subscribe_status=subscribe_status,
                subscribe_time=subscribe_time or datetime.now(),
                expire_time=expire_time,
            )
            self.session.add(binding)
        else:
            binding.subscribe_status = subscribe_status
            if subscribe_time is not None:
                binding.subscribe_time = subscribe_time
            binding.expire_time = expire_time
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "upsert_binding 提交失败已回滚: user=%s template=%s",
                user_id, template_id, exc_info=True,
            )
            raise
        return binding

    async def list_bindings(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        template_id: Optional[int] = None,
        subscribe_status: Optional[int] = None,
    ) -> Tuple[List[SubscribeBinding], int]:
        """分页查询订阅绑定（支持按用户+模板+状态筛选）"""
        stmt = select(self.model_class)
        conditions = []
        if user_id is not None:
            conditions.append(self.model_class.user_id == str(user_id))
        if template_id is not None:
            conditions.append(self.model_class.template_id == str(template_id))
        if subscribe_status is not None:
            conditions.append(self.model_class.subscribe_status == subscribe_status)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 统计总数
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        stmt = stmt.order_by(self.model_class.create_time.desc()).offset(offset).limit(page_size)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total
