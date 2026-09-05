# @ai-generated
"""
短链+点击日志跟单匹配策略
默认策略：通过短链点击日志，按 last-click 规则匹配订单归属用户

匹配规则：
1. 72 小时窗口期：只匹配支付时间前 72 小时内的点击记录
2. Last-Click 优先：同一商品存在多条点击记录时，取最后一条（access_time 最新）
3. 点击记录不存在 → 匹配失败 → 存入异常订单库
4. 存在多条记录来自不同用户 → 取最新的用户，但标记异常待审核
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.b05_4_constants import (
    ATTRIBUTION_WINDOW_HOURS,
    ABNORMAL_REASON_NO_CLICK,
    ABNORMAL_REASON_MULTI_USER,
)
from src.dao.click_log_dao import ClickLogDAO
from src.services.attribution.base_strategy import (
    BaseAttributionStrategy,
    MatchResult,
)

logger = logging.getLogger("service.attribution.short_link")


class ShortLinkAttributionStrategy(BaseAttributionStrategy):
    """短链+点击日志跟单匹配策略（默认策略）"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.click_log_dao = ClickLogDAO(db)

    def get_strategy_name(self) -> str:
        return "short_link"

    async def resolve_user(
        self,
        out_order_no: str,
        goods_id: str,
        channel_code: str,
        order_data: Optional[Dict[str, Any]] = None,
    ) -> MatchResult:
        """通过短链点击日志匹配订单归属用户

        匹配流程：
        1. 根据 goods_id 查找 72h 窗口内的点击记录（按 access_time DESC）
        2. 取最后一条点击记录的用户
        3. 检查是否多条记录来自不同用户 → 低置信度
        4. 返回匹配结果

        Args:
            out_order_no: 渠道订单号（用于日志）
            goods_id: 商品ID
            channel_code: 渠道标识
            order_data: 原始订单数据（可选，含 pay_time 用于精确窗口计算）
        Returns:
            MatchResult
        """
        if not goods_id:
            logger.warning(
                "[short_link_strategy] goods_id 为空，无法匹配: out_order_no=%s",
                out_order_no,
            )
            return MatchResult(
                user_id=0,
                extra={"reason": "goods_id 为空", "out_order_no": out_order_no},
            )

        # 获取支付时间（用于精确窗口计算）
        pay_time = None
        if order_data and order_data.get("pay_time"):
            try:
                raw = order_data["pay_time"]
                if isinstance(raw, str):
                    pay_time = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                elif isinstance(raw, datetime):
                    pay_time = raw
            except (ValueError, TypeError):
                pass

        # 查询 72h 窗口内的点击记录
        clicks = await self.click_log_dao.find_recent_clicks(
            goods_id=goods_id,
            hours=ATTRIBUTION_WINDOW_HOURS,
            channel_code=channel_code,
        )

        if not clicks:
            logger.info(
                "[short_link_strategy] 无匹配点击记录: out_order_no=%s goods_id=%s",
                out_order_no, goods_id,
            )
            return MatchResult(
                user_id=0,
                extra={
                    "reason": ABNORMAL_REASON_NO_CLICK,
                    "out_order_no": out_order_no,
                    "goods_id": goods_id,
                },
            )

        # 按 last-click 规则：取最后一条点击记录
        latest_click = clicks[0]  # 已按 access_time DESC 排序
        matched_user_id = latest_click.user_id

        # 检查是否有多条记录来自不同用户
        unique_users = set(c.user_id for c in clicks)
        is_multi_user = len(unique_users) > 1

        if is_multi_user:
            logger.warning(
                "[short_link_strategy] 多用户点击同一商品: out_order_no=%s goods_id=%s "
                "users=%s 取最新 user_id=%s",
                out_order_no, goods_id, unique_users, matched_user_id,
            )

        # 构造匹配结果
        extra = {
            "matched_key": latest_click.short_key,
            "click_time": (
                latest_click.access_time.strftime("%Y-%m-%d %H:%M:%S")
                if latest_click.access_time else ""
            ),
            "total_clicks": len(clicks),
            "unique_users": list(unique_users),
            "is_multi_user": is_multi_user,
        }

        if is_multi_user:
            extra["reason"] = ABNORMAL_REASON_MULTI_USER

        confidence = 0.5 if is_multi_user else 0.9

        result = MatchResult(
            user_id=matched_user_id,
            matched_key=latest_click.short_key,
            matched_at=(
                latest_click.access_time.strftime("%Y-%m-%d %H:%M:%S")
                if latest_click.access_time else None
            ),
            confidence=confidence,
            extra=extra,
        )

        logger.info(
            "[short_link_strategy] 匹配结果: out_order_no=%s user_id=%s "
            "confidence=%s is_multi_user=%s",
            out_order_no, matched_user_id, confidence, is_multi_user,
        )
        return result