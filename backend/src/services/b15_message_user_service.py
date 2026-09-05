# @ai-generated
"""
F05 营销消息用户端 Service 层
订阅模板查询 + 订阅授权记录 + 订阅状态查询 + 取消订阅
Session 内部管理（与 B15MessageService 模式一致）
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.dao.message_template_dao import (
    MessageTemplateDao,
    SubscribeBindingDao,
)
from src.db.base import DatabaseManager
from src.models.system.message_template import (
    MessageTemplate,
    SubscribeBinding,
)

logger = logging.getLogger("service.b15_message_user")

# 微信一次性订阅消息模板有效期（天）
SUBSCRIBE_TEMPLATE_VALID_DAYS = 7


class B15MessageUserService:
    """营销消息用户端 Service"""

    @staticmethod
    def _serialize_template(t: MessageTemplate) -> Dict[str, Any]:
        return {
            "id": t.id,
            "template_name": t.template_name,
            "template_type": t.template_type,
            "tmpl_id": t.tmpl_id,
            "title": t.title,
            "content": t.content,
            "keywords": t.keywords,
            "status": t.status,
            "create_time": t.create_time.strftime("%Y-%m-%d %H:%M:%S") if t.create_time else None,
        }

    @staticmethod
    def _serialize_binding(b: SubscribeBinding) -> Dict[str, Any]:
        return {
            "id": b.id,
            "user_id": b.user_id,
            "template_id": b.template_id,
            "subscribe_status": b.subscribe_status,
            "subscribe_time": b.subscribe_time.strftime("%Y-%m-%d %H:%M:%S") if b.subscribe_time else None,
            "expire_time": b.expire_time.strftime("%Y-%m-%d %H:%M:%S") if b.expire_time else None,
        }

    # ── 1. 可订阅模板列表 ────────────────────────────────

    @classmethod
    async def list_subscribe_templates(cls) -> List[Dict[str, Any]]:
        """查询启用中的微信订阅消息模板（template_type=1, status=1）

        Returns:
            可订阅模板列表（仅返回渲染所需字段）
        """
        async with DatabaseManager.get_session() as session:
            dao = MessageTemplateDao(session)
            items, _ = await dao.list_templates(
                page=1, page_size=100, template_type=1, status=1
            )
            return [
                {
                    "id": t.id,
                    "template_name": t.template_name,
                    "tmpl_id": t.tmpl_id,
                    "title": t.title,
                    "content": t.content,
                    "keywords": t.keywords,
                }
                for t in items
            ]

    # ── 2. 订阅状态查询 ──────────────────────────────────

    @classmethod
    async def get_user_subscribe_status(cls, user_id: int) -> List[Dict[str, Any]]:
        """查询用户对启用中微信订阅模板的订阅状态

        返回每个模板的订阅状态 + 是否已过期（一次性模板7天有效期）。
        Returns:
            [{
              template_id, template_name, tmpl_id,
              subscribe_status(1=已订阅 0=未订阅),
              subscribe_time, expire_time, expired(bool)
            }]
        """
        async with DatabaseManager.get_session() as session:
            template_dao = MessageTemplateDao(session)
            binding_dao = SubscribeBindingDao(session)

            templates, _ = await template_dao.list_templates(
                page=1, page_size=100, template_type=1, status=1
            )
            now = datetime.now()

            result: List[Dict[str, Any]] = []
            for t in templates:
                binding = await binding_dao.get_by_user_and_template(user_id, t.id)
                status = 0
                subscribe_time = None
                expire_time = None
                expired = False
                if binding is not None:
                    status = binding.subscribe_status
                    subscribe_time = (
                        binding.subscribe_time.strftime("%Y-%m-%d %H:%M:%S")
                        if binding.subscribe_time else None
                    )
                    expire_time = (
                        binding.expire_time.strftime("%Y-%m-%d %H:%M:%S")
                        if binding.expire_time else None
                    )
                    # 已订阅但已过期 → 标记过期（前端提示重新订阅）
                    if (
                        binding.subscribe_status == 1
                        and binding.expire_time is not None
                        and binding.expire_time < now
                    ):
                        expired = True

                result.append(
                    {
                        "template_id": t.id,
                        "template_name": t.template_name,
                        "tmpl_id": t.tmpl_id,
                        "subscribe_status": status,
                        "subscribe_time": subscribe_time,
                        "expire_time": expire_time,
                        "expired": expired,
                    }
                )
            return result

    # ── 3. 订阅授权记录 ──────────────────────────────────

    @classmethod
    async def record_subscribe(
        cls,
        user_id: int,
        template_id: int,
        action: str,
        tmpl_id: str = "",
    ) -> Dict[str, Any]:
        """记录订阅授权结果

        Args:
            user_id: 用户ID
            template_id: 消息模板ID
            action: accept=已同意 / reject=用户拒绝 / expired=授权过期或不可用
            tmpl_id: 微信订阅消息模板ID（冗余存储，可选）
        Returns:
            订阅绑定 dict
        Raises:
            ValueError: 模板不存在或非微信订阅模板
        """
        async with DatabaseManager.get_session() as session:
            template_dao = MessageTemplateDao(session)
            binding_dao = SubscribeBindingDao(session)

            template = await template_dao.get_by_id(template_id)
            if template is None or template.template_type != 1:
                raise ValueError(f"消息模板不存在或非微信订阅模板: id={template_id}")

            now = datetime.now()
            if action == "accept":
                subscribe_status = 1
                # 一次性订阅模板有效期 7 天
                expire_time = now + timedelta(days=SUBSCRIBE_TEMPLATE_VALID_DAYS)
            else:
                # reject / expired → 未订阅状态
                subscribe_status = 0
                expire_time = None

            binding = await binding_dao.upsert_binding(
                user_id=user_id,
                template_id=template_id,
                subscribe_status=subscribe_status,
                subscribe_time=now,
                expire_time=expire_time,
            )

            logger.info(
                "[subscribe] 订阅授权记录 user_id=%s template_id=%s action=%s status=%s",
                user_id, template_id, action, subscribe_status,
            )
            return cls._serialize_binding(binding)

    # ── 4. 取消订阅 ──────────────────────────────────────

    @classmethod
    async def unsubscribe(cls, user_id: int, template_id: int) -> Dict[str, Any]:
        """取消订阅（将绑定状态置为 0）

        Args:
            user_id: 用户ID
            template_id: 消息模板ID
        Returns:
            更新后的订阅绑定 dict
        """
        async with DatabaseManager.get_session() as session:
            binding_dao = SubscribeBindingDao(session)
            binding = await binding_dao.get_by_user_and_template(user_id, template_id)
            if binding is None:
                # 无绑定记录也返回成功（幂等）
                return {
                    "user_id": str(user_id),
                    "template_id": str(template_id),
                    "subscribe_status": 0,
                    "subscribe_time": None,
                    "expire_time": None,
                }
            binding.subscribe_status = 0
            binding.expire_time = None
            try:
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise

            logger.info(
                "[subscribe] 取消订阅 user_id=%s template_id=%s",
                user_id, template_id,
            )
            return cls._serialize_binding(binding)
