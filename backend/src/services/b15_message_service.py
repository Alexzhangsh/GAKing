# @ai-generated
"""
F04 营销消息模块 Service 层
消息模板CRUD + 启停 + 推送记录查询 + 订阅绑定查询
Session 内部管理（与 B13 GoodsAdminService 模式一致）
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.dao.message_template_dao import (
    MessageTemplateDao,
    PushRecordDao,
    SubscribeBindingDao,
)
from src.db.base import DatabaseManager
from src.models.system.message_template import (
    MessageTemplate,
    PushRecord,
    SubscribeBinding,
)
from src.schemas.b15_message import (
    MessageTemplateCreate,
    MessageTemplateUpdate,
)

logger = logging.getLogger("service.b15_message")


class B15MessageService:
    """营销消息管理 Service"""

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
            "remark": t.remark,
            "create_time": t.create_time.strftime("%Y-%m-%d %H:%M:%S") if t.create_time else None,
            "update_time": t.update_time.strftime("%Y-%m-%d %H:%M:%S") if t.update_time else None,
        }

    @staticmethod
    def _serialize_push_record(r: PushRecord) -> Dict[str, Any]:
        return {
            "id": r.id,
            "template_id": r.template_id,
            "user_id": r.user_id,
            "push_status": r.push_status,
            "push_time": r.push_time.strftime("%Y-%m-%d %H:%M:%S") if r.push_time else None,
            "error_msg": r.error_msg,
            "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else None,
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
            "create_time": b.create_time.strftime("%Y-%m-%d %H:%M:%S") if b.create_time else None,
        }

    # ── 消息模板 CRUD ──────────────────────────────────

    @classmethod
    async def list_templates(
        cls,
        page: int = 1,
        page_size: int = 20,
        template_type: Optional[int] = None,
        status: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        async with DatabaseManager.get_session() as session:
            dao = MessageTemplateDao(session)
            items, total = await dao.list_templates(
                page=page, page_size=page_size, template_type=template_type, status=status
            )
            return [cls._serialize_template(t) for t in items], total

    @classmethod
    async def get_template(cls, template_id: int) -> Dict[str, Any]:
        async with DatabaseManager.get_session() as session:
            dao = MessageTemplateDao(session)
            t = await dao.get_by_id(template_id)
            if t is None:
                raise ValueError(f"消息模板不存在: id={template_id}")
            return cls._serialize_template(t)

    @classmethod
    async def create_template(cls, body: MessageTemplateCreate) -> Dict[str, Any]:
        # 微信订阅消息必须有 tmpl_id
        if body.template_type == 1 and not body.tmpl_id:
            raise ValueError("微信订阅消息模板必须填写 tmpl_id")

        async with DatabaseManager.get_session() as session:
            dao = MessageTemplateDao(session)
            data = body.model_dump()
            t = await dao.create(data)
            return cls._serialize_template(t)

    @classmethod
    async def update_template(
        cls, template_id: int, body: MessageTemplateUpdate
    ) -> Dict[str, Any]:
        async with DatabaseManager.get_session() as session:
            dao = MessageTemplateDao(session)
            data = body.model_dump(exclude_unset=True)
            if not data:
                raise ValueError("无更新字段")
            t = await dao.update_by_id(template_id, data)
            if t is None:
                raise ValueError(f"消息模板不存在: id={template_id}")
            return cls._serialize_template(t)

    @classmethod
    async def delete_template(cls, template_id: int) -> None:
        async with DatabaseManager.get_session() as session:
            dao = MessageTemplateDao(session)
            ok = await dao.logic_delete_by_id(template_id)
            if not ok:
                raise ValueError(f"消息模板不存在: id={template_id}")

    @classmethod
    async def toggle_template_status(cls, template_id: int) -> Dict[str, Any]:
        async with DatabaseManager.get_session() as session:
            dao = MessageTemplateDao(session)
            t = await dao.toggle_status(template_id)
            if t is None:
                raise ValueError(f"消息模板不存在: id={template_id}")
            return cls._serialize_template(t)

    # ── 推送记录查询 ──────────────────────────────────

    @classmethod
    async def list_push_records(
        cls,
        page: int = 1,
        page_size: int = 20,
        template_id: Optional[int] = None,
        user_id: Optional[int] = None,
        push_status: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        async with DatabaseManager.get_session() as session:
            dao = PushRecordDao(session)
            items, total = await dao.list_records(
                page=page, page_size=page_size, template_id=template_id,
                user_id=user_id, push_status=push_status,
            )
            return [cls._serialize_push_record(r) for r in items], total

    # ── 订阅绑定查询 ──────────────────────────────────

    @classmethod
    async def list_subscribe_bindings(
        cls,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        template_id: Optional[int] = None,
        subscribe_status: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        async with DatabaseManager.get_session() as session:
            dao = SubscribeBindingDao(session)
            items, total = await dao.list_bindings(
                page=page, page_size=page_size, user_id=user_id,
                template_id=template_id, subscribe_status=subscribe_status,
            )
            return [cls._serialize_binding(b) for b in items], total
