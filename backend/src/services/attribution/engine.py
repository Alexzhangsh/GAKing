# @ai-generated
"""
跟单引擎 —— 组合多种跟单策略，按需切换

职责：
1. 管理多个跟单策略的注册与调度
2. 按优先级依次尝试各策略，直到匹配成功
3. 匹配失败时，通过回调将订单写入异常订单库
4. 支持运行时切换默认策略（short_link → relation_id）

当前默认策略链：
1. ShortLinkAttributionStrategy（短链+点击日志模式）
2. RelationIdAttributionStrategy（预留，relation-id 模式）
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.b05_4_constants import (
    ATTRIBUTION_STRATEGY_DEFAULT,
    ABNORMAL_REASON_NO_CLICK,
)
from src.dao.abnormal_order_dao import AbnormalOrderDAO
from src.services.attribution.base_strategy import (
    BaseAttributionStrategy,
    MatchResult,
)
from src.services.attribution.short_link_strategy import (
    ShortLinkAttributionStrategy,
)
from src.services.attribution.relation_id_strategy import (
    RelationIdAttributionStrategy,
)

logger = logging.getLogger("service.attribution.engine")


class AttributionEngine:
    """跟单引擎

    Usage:
        engine = AttributionEngine(db)
        # 默认使用 short_link 策略
        result = await engine.resolve_user(
            out_order_no="123456",
            goods_id="item_abc",
            channel_code="myq",
            order_data={...},
        )
        if result.is_matched:
            user_id = result.user_id
        else:
            # 自动写入异常订单表
            abnormal = await engine.save_abnormal_order(
                out_order_no="123456",
                channel_code="myq",
                order_data={...},
                match_result=result,
            )
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.abnormal_dao = AbnormalOrderDAO(db)
        self._strategies: List[BaseAttributionStrategy] = []
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """注册默认策略链（按优先级）"""
        self._strategies = [
            ShortLinkAttributionStrategy(self.db),
            RelationIdAttributionStrategy(self.db),
        ]

    def register_strategy(self, strategy: BaseAttributionStrategy) -> None:
        """注册额外策略（可扩展）"""
        self._strategies.append(strategy)

    def set_strategies(self, strategies: List[BaseAttributionStrategy]) -> None:
        """替换整个策略链（运行时切换）"""
        self._strategies = strategies

    async def resolve_user(
        self,
        out_order_no: str,
        goods_id: str,
        channel_code: str,
        order_data: Optional[Dict[str, Any]] = None,
    ) -> MatchResult:
        """按策略链依次匹配用户

        按注册顺序依次尝试各策略，第一个匹配成功即返回。
        所有策略均未匹配 → 返回 user_id=0 的 MatchResult。

        Args:
            out_order_no: 渠道订单号
            goods_id: 商品ID
            channel_code: 渠道标识
            order_data: 原始订单数据
        Returns:
            MatchResult
        """
        for strategy in self._strategies:
            try:
                result = await strategy.resolve_user(
                    out_order_no=out_order_no,
                    goods_id=goods_id,
                    channel_code=channel_code,
                    order_data=order_data,
                )
                if result.is_matched:
                    logger.info(
                        "[attribution_engine] 策略 %s 匹配成功: "
                        "out_order_no=%s user_id=%s confidence=%s",
                        strategy.get_strategy_name(),
                        out_order_no, result.user_id, result.confidence,
                    )
                    return result

                logger.info(
                    "[attribution_engine] 策略 %s 未匹配: "
                    "out_order_no=%s extra=%s",
                    strategy.get_strategy_name(),
                    out_order_no, result.extra,
                )
            except Exception as e:
                logger.error(
                    "[attribution_engine] 策略 %s 执行异常: "
                    "out_order_no=%s err=%s",
                    strategy.get_strategy_name(),
                    out_order_no, e,
                    exc_info=True,
                )

        # 所有策略均未匹配
        return MatchResult(
            user_id=0,
            extra={
                "reason": ABNORMAL_REASON_NO_CLICK,
                "out_order_no": out_order_no,
                "goods_id": goods_id,
                "channel_code": channel_code,
            },
        )

    async def save_abnormal_order(
        self,
        out_order_no: str,
        channel_code: str,
        order_data: Optional[Dict[str, Any]] = None,
        match_result: Optional[MatchResult] = None,
        goods_id: str = "",
        goods_title: str = "",
        pay_amount: str = "0.00",
        total_commission: str = "0.00",
        order_status: str = "",
        pay_time: Optional[str] = None,
    ) -> Any:
        """将无法归属的订单存入异常订单表

        Args:
            out_order_no: 渠道订单号
            channel_code: 渠道标识
            order_data: 原始订单数据
            match_result: 匹配结果
            goods_id: 商品ID
            goods_title: 商品标题
            pay_amount: 支付金额
            total_commission: 总佣金
            order_status: 渠道原始状态
            pay_time: 支付时间
        Returns:
            AbnormalOrder 实例
        """
        # 检查是否已存在
        existing = await self.abnormal_dao.get_by_out_order_no(out_order_no)
        if existing:
            logger.info(
                "[attribution_engine] 异常订单已存在，跳过: out_order_no=%s",
                out_order_no,
            )
            return existing

        reason = ABNORMAL_REASON_NO_CLICK
        matched_click_key = ""
        matched_user_id = 0
        if match_result:
            reason = match_result.extra.get("reason", ABNORMAL_REASON_NO_CLICK)
            matched_click_key = match_result.matched_key
            matched_user_id = match_result.user_id

        # 解析支付时间
        parsed_pay_time = None
        if pay_time:
            try:
                parsed_pay_time = datetime.fromisoformat(
                    pay_time.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        data = {
            "out_order_no": out_order_no,
            "channel_code": channel_code or "",
            "order_data": json.dumps(order_data, ensure_ascii=False, default=str) if order_data else "",
            "goods_id": goods_id or "",
            "goods_title": goods_title or "",
            "pay_amount": pay_amount,
            "total_commission": total_commission,
            "order_status": order_status or "",
            "pay_time": parsed_pay_time,
            "abnormal_reason": reason,
            "matched_click_key": matched_click_key,
            "matched_user_id": matched_user_id,
            "review_status": "PENDING",
        }
        abnormal = await self.abnormal_dao.create(data)
        logger.info(
            "[attribution_engine] 异常订单已入库: out_order_no=%s reason=%s "
            "matched_user_id=%s",
            out_order_no, reason, matched_user_id,
        )
        return abnormal