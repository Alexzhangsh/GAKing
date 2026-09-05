# @ai-generated
"""
relation-id 跟单匹配策略（预留）
当前 CPS 渠道使用普通自助推广 PID，不支持 relation-id 模式。
该策略为未来渠道升级（渠道-分销类型推广位）预留实现入口。

启用条件：
1. CPS 渠道推广位升级为渠道-分销类型
2. 渠道 API 支持传入 relation_id 参数进行溯源
3. EnvConfig 或后台配置启用 relation-id 模式
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.attribution.base_strategy import (
    BaseAttributionStrategy,
    MatchResult,
)

logger = logging.getLogger("service.attribution.relation_id")


class RelationIdAttributionStrategy(BaseAttributionStrategy):
    """relation-id 跟单匹配策略（预留实现）

    当渠道升级为渠道-分销类型推广位时，渠道 API 返回的订单中
    会包含 relation_id 参数，通过该参数可直接映射到平台 user_id。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def get_strategy_name(self) -> str:
        return "relation_id"

    async def resolve_user(
        self,
        out_order_no: str,
        goods_id: str,
        channel_code: str,
        order_data: Optional[Dict[str, Any]] = None,
    ) -> MatchResult:
        """通过 relation-id 匹配订单归属用户（预留）

        当前实现：返回未匹配，提示需升级渠道。

        TODO: 当渠道升级后，在此处实现：
        1. 从 order_data / channel_pid 中提取 relation_id
        2. 通过 relation_id → user_id 映射表查询
        3. 返回匹配结果

        Args:
            out_order_no: 渠道订单号
            goods_id: 商品ID
            channel_code: 渠道标识
            order_data: 原始订单数据
        Returns:
            MatchResult
        """
        logger.info(
            "[relation_id_strategy] relation-id 模式未启用（预留）: "
            "out_order_no=%s channel=%s",
            out_order_no, channel_code,
        )
        return MatchResult(
            user_id=0,
            extra={
                "reason": "relation-id 模式未启用（预留策略）",
                "out_order_no": out_order_no,
                "channel_code": channel_code,
            },
        )