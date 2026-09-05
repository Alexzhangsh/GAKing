# @ai-generated
"""
短链服务 —— 生成短链、记录点击、查询映射
职责：
1. 生成唯一短链 key（base62 编码），持久化短链映射记录
2. 短链访问时记录点击日志（user_id, goods_id, UA, IP, 访问时间）
3. 查询短链映射信息（用于重定向跳转）
4. 配合跟单引擎进行用户匹配

设计约定：
- 短链 key 使用 base62 编码（安全、短小、无特殊字符）
- 短链过期时间 = 72 小时（与跟单窗口期一致）
- 不依赖外部 ID 生成服务，使用时间戳 + 随机数生成唯一 key
"""
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.b05_4_constants import (
    SHORT_LINK_KEY_LENGTH,
    SHORT_LINK_EXPIRE_HOURS,
)
from src.dao.short_link_dao import ShortLinkDAO
from src.dao.click_log_dao import ClickLogDAO
from src.models.business.short_link_model import ShortLink
from src.models.business.click_log_model import ClickLog

logger = logging.getLogger("service.short_link")

# Base62 字母表
BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase


def _generate_short_key(length: int = SHORT_LINK_KEY_LENGTH) -> str:
    """生成随机的 base62 短链 key

    使用时间戳 + 随机数提高唯一性，避免碰撞。
    key 长度 8 位，62^8 ≈ 218 万亿组合，碰撞概率极低。

    Args:
        length: key 长度，默认 8
    Returns:
        base62 编码的短链 key
    """
    timestamp = int(datetime.now().timestamp() * 1000)
    random.seed(timestamp + random.randint(0, 1000000))
    return "".join(random.choices(BASE62_ALPHABET, k=length))


class ShortLinkService:
    """短链服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.short_link_dao = ShortLinkDAO(db)
        self.click_log_dao = ClickLogDAO(db)

    async def create_short_link(
        self,
        user_id: int,
        goods_id: str,
        goods_title: str = "",
        channel_code: str = "",
        source_url: str = "",
    ) -> ShortLink:
        """创建短链映射记录

        Args:
            user_id: 用户ID
            goods_id: 商品ID
            goods_title: 商品标题（可选）
            channel_code: 渠道标识（可选）
            source_url: 原始 CPS 推广链接（可选）
        Returns:
            创建的 ShortLink 实例
        """
        # 生成唯一 key（最多重试 5 次防碰撞）
        short_key = _generate_short_key()
        for attempt in range(5):
            existing = await self.short_link_dao.get_by_short_key(short_key)
            if existing is None:
                break
            logger.warning(
                "短链 key 碰撞 key=%s attempt=%s，重新生成", short_key, attempt + 1
            )
            short_key = _generate_short_key()
        else:
            # 极低概率：5 次均碰撞，使用更长的 key
            short_key = _generate_short_key(length=SHORT_LINK_KEY_LENGTH + 4)
            logger.info("短链 key 5 次碰撞后使用扩展长度 key=%s", short_key)

        expire_at = datetime.now() + timedelta(hours=SHORT_LINK_EXPIRE_HOURS)

        data = {
            "short_key": short_key,
            "user_id": user_id,
            "goods_id": goods_id,
            "goods_title": goods_title or "",
            "channel_code": channel_code or "",
            "source_url": source_url or "",
            "expire_at": expire_at,
            "click_count": 0,
        }
        link = await self.short_link_dao.create(data)
        logger.info(
            "创建短链: short_key=%s user_id=%s goods_id=%s expire_at=%s",
            short_key, user_id, goods_id, expire_at,
        )
        return link

    async def get_short_link(self, short_key: str) -> Optional[ShortLink]:
        """查询短链映射信息

        Args:
            short_key: 短链 key
        Returns:
            ShortLink 实例 或 None
        """
        return await self.short_link_dao.get_by_short_key(short_key)

    async def record_click(
        self,
        short_key: str,
        user_agent: str = "",
        ip_address: str = "",
        referer_url: str = "",
    ) -> Optional[ClickLog]:
        """记录短链点击行为

        流程：
        1. 查询短链映射
        2. 短链不存在或已过期 → 返回 None
        3. 更新短链点击计数
        4. 持久化点击日志

        Args:
            short_key: 短链 key
            user_agent: User-Agent
            ip_address: 请求 IP
            referer_url: 来源 URL
        Returns:
            ClickLog 实例 或 None（短链无效/过期）
        """
        link = await self.short_link_dao.get_by_short_key(short_key)
        if link is None:
            logger.warning("点击短链不存在: short_key=%s", short_key)
            return None

        # 检查是否过期
        if link.expire_at and datetime.now() > link.expire_at:
            logger.warning("点击已过期短链: short_key=%s expire_at=%s", short_key, link.expire_at)
            return None

        # 更新短链点击计数
        await self.short_link_dao.increment_click_count(link.id)

        # 持久化点击日志
        click_data = {
            "short_key": short_key,
            "user_id": link.user_id,
            "goods_id": link.goods_id,
            "goods_title": link.goods_title or "",
            "source_channel": link.channel_code or "",
            "user_agent": user_agent or "",
            "ip_address": ip_address or "",
            "referer_url": referer_url or "",
            "access_time": datetime.now(),
        }
        click_log = await self.click_log_dao.create(click_data)
        logger.debug(
            "记录点击: short_key=%s user_id=%s goods_id=%s",
            short_key, link.user_id, link.goods_id,
        )
        return click_log

    async def get_source_url_by_key(self, short_key: str) -> Optional[str]:
        """获取短链对应的原始推广链接

        Args:
            short_key: 短链 key
        Returns:
            原始推广链接 或 None
        """
        link = await self.short_link_dao.get_by_short_key(short_key)
        if link is None:
            return None
        return link.source_url or ""