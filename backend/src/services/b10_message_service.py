# @ai-generated
"""
B10 站内消息业务服务层

职责：
1. 消息生产：为各业务模块（佣金/提现/订单/退款）提供统一的消息创建入口
2. 消息消费：用户消息列表查询、未读计数、标记已读/全部已读
3. 消息推送：定时巡检待推送消息，调用微信订阅消息推送
4. 后台管理：多条件分页查询消息列表

设计约定：
1. Session 通过参数注入（与 B09 withdraw_service 风格一致），由 API 层 Depends 管理
2. 消息创建后自动失效未读计数缓存（Redis），确保下次查询最新值
3. 推送失败不阻塞消息创建，记日志后继续
4. 消息创建与业务操作解耦——业务方创建消息后不影响主流程
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.redis_client import RedisClient
from src.config.b10_constants import (
    CACHE_KEY_USER_UNREAD_COUNT,
    CACHE_TTL_UNREAD_COUNT,
    MESSAGE_TYPE_ROUTE_MAP,
    MessageType,
)
from src.dao.b10_user_message_dao import UserMessageDAO
from src.models.business.b10_user_message_model import UserMessage

logger = logging.getLogger("service.b10_message")


class B10MessageService:
    """站内消息业务服务

    通过构造函数注入 UserMessageDAO（由 API 层 Depends 提供 AsyncSession）
    """

    def __init__(self, dao: UserMessageDAO):
        self.dao = dao

    # ── 内部工具方法 ────────────────────────────────────

    @staticmethod
    def _serialize(msg: UserMessage) -> Dict[str, Any]:
        """序列化消息实例为字典"""
        d = msg.to_dict()
        # 补充前端跳转路由
        d["route_url"] = MESSAGE_TYPE_ROUTE_MAP.get(msg.message_type, "")
        return d

    @staticmethod
    async def _invalidate_unread_cache(user_id: int) -> None:
        """失效用户未读消息计数缓存"""
        await RedisClient.delete(f"{CACHE_KEY_USER_UNREAD_COUNT}{user_id}")

    @staticmethod
    async def _get_cached_unread(user_id: int) -> Optional[int]:
        """读取缓存中的未读计数"""
        raw = await RedisClient.get(f"{CACHE_KEY_USER_UNREAD_COUNT}{user_id}")
        if raw is not None:
            try:
                return int(raw)
            except (ValueError, TypeError):
                return None
        return None

    @staticmethod
    async def _set_cached_unread(user_id: int, count: int) -> None:
        """写入未读计数缓存（TTL 10分钟）"""
        await RedisClient.set(
            f"{CACHE_KEY_USER_UNREAD_COUNT}{user_id}",
            str(count),
            expire=CACHE_TTL_UNREAD_COUNT,
        )

    # ── 1. 消息生产 ─────────────────────────────────────

    async def create_message(
        self,
        user_id: int,
        message_type: str,
        title: str,
        content: str,
        biz_id: str = "",
    ) -> Dict[str, Any]:
        """创建单条站内消息

        Args:
            user_id: 接收用户ID
            message_type: 消息类型（MessageType 枚举值）
            title: 消息标题
            content: 消息内容
            biz_id: 关联业务ID（可选）
        Returns:
            消息详情 dict
        Raises:
            ValueError: message_type 不合法
        """
        # 校验消息类型
        valid_types = {t.value for t in MessageType}
        if message_type not in valid_types:
            raise ValueError(f"消息类型不合法: {message_type}，可选: {sorted(valid_types)}")

        data = {
            "user_id": user_id,
            "message_type": message_type,
            "title": title,
            "content": content,
            "biz_id": biz_id,
            "is_read": 0,
            "push_status": 0,
        }
        msg = await self.dao.create_message(data)

        # 失效未读计数缓存
        await self._invalidate_unread_cache(user_id)

        logger.info(
            "[message] 创建消息成功 user_id=%s type=%s title=%s biz_id=%s msg_id=%s",
            user_id, message_type, title, biz_id, msg.id,
        )
        return self._serialize(msg)

    async def batch_create_messages(
        self,
        messages: List[Dict[str, Any]],
    ) -> int:
        """批量创建消息（相同类型批量通知）

        Args:
            messages: 消息数据字典列表，每项含 user_id/message_type/title/content/biz_id
        Returns:
            创建成功条数
        """
        count = await self.dao.batch_create_messages(messages)

        # 批量失效涉及用户的未读计数缓存
        user_ids = {m.get("user_id") for m in messages if m.get("user_id")}
        for uid in user_ids:
            await self._invalidate_unread_cache(uid)

        logger.info("[message] 批量创建消息成功 count=%s users=%s", count, len(user_ids))
        return count

    # ── 2. 消息消费 ─────────────────────────────────────

    async def list_user_messages(
        self,
        user_id: int,
        *,
        message_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """查询用户消息列表（分页，按创建时间倒序）

        Args:
            user_id: 用户ID
            message_type: 消息类型筛选（可选）
            page: 页码
            page_size: 每页条数
        Returns:
            {"list": [...], "total": int, "page": int, "page_size": int}
        """
        items, total = await self.dao.list_by_user_id(
            user_id, message_type=message_type, page=page, page_size=page_size,
        )
        return {
            "list": [self._serialize(it) for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_unread_count(self, user_id: int) -> int:
        """查询用户未读消息数（读穿缓存）

        策略：Redis 缓存优先 → 未命中查 DAO → 回写缓存
        """
        cached = await self._get_cached_unread(user_id)
        if cached is not None:
            return cached

        count = await self.dao.count_unread_by_user(user_id)
        await self._set_cached_unread(user_id, count)
        return count

    async def mark_as_read(self, user_id: int, message_id: Optional[int] = None) -> int:
        """标记消息已读

        Args:
            user_id: 用户ID
            message_id: 消息ID（None 时标记全部已读）
        Returns:
            更新的记录数
        """
        if message_id is not None:
            result = await self.dao.mark_as_read(message_id, user_id)
            updated = 1 if result is not None else 0
        else:
            updated = await self.dao.mark_all_as_read(user_id)

        if updated > 0:
            await self._invalidate_unread_cache(user_id)

        logger.info(
            "[message] 标记已读 user_id=%s message_id=%s updated=%s",
            user_id, message_id, updated,
        )
        return updated

    # ── 3. 后台管理 ─────────────────────────────────────

    async def list_messages_for_admin(
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
    ) -> Dict[str, Any]:
        """后台消息管理列表（多条件分页查询）

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
            {"list": [...], "total": int, "page": int, "page_size": int}
        """
        items, total = await self.dao.list_with_filters(
            user_id=user_id,
            message_type=message_type,
            is_read=is_read,
            push_status=push_status,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        return {
            "list": [self._serialize(it) for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ── 4. 消息推送（供定时任务调用） ────────────────────

    async def process_pending_push(self, limit: int = 100) -> Dict[str, Any]:
        """处理待推送消息

        由定时任务 scheduler 周期性调用，扫描 push_status=0 的消息，
        尝试推送（当前阶段仅标记已推送，后续接入微信订阅消息后实现实际推送）。

        Returns:
            {"processed": int, "success": int, "failed": int, "errors": List[str]}
        """
        pending = await self.dao.list_pending_push(limit)
        if not pending:
            return {"processed": 0, "success": 0, "failed": 0, "errors": []}

        success = 0
        failed = 0
        errors: List[str] = []

        for msg in pending:
            try:
                # TODO(接入微信订阅消息后): 调用微信订阅消息推送接口
                # 当前阶段仅标记已推送，实际推送待微信订阅消息能力接入后实现
                await self.dao.mark_push_success(msg.id)
                success += 1
            except Exception as e:
                failed += 1
                err_msg = f"msg_id={msg.id} push failed: {e}"
                errors.append(err_msg)
                logger.error("[message_push] %s", err_msg, exc_info=True)
                try:
                    await self.dao.mark_push_failed(msg.id, str(e))
                except Exception:
                    logger.error("[message_push] 标记失败状态异常", exc_info=True)

        logger.info(
            "[message_push] 巡检完成 processed=%s success=%s failed=%s",
            len(pending), success, failed,
        )
        return {
            "processed": len(pending),
            "success": success,
            "failed": failed,
            "errors": errors[:10],  # 最多返回10条错误
        }