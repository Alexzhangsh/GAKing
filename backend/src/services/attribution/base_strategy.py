# @ai-generated
"""
跟单匹配策略抽象基类
定义统一接口，所有跟单策略必须实现 resolve_user 方法
当前默认实现：短链+点击日志模式（ShortLinkAttributionStrategy）
未来可扩展：relation-id 模式（RelationIdAttributionStrategy）
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple


class MatchResult:
    """跟单匹配结果

    Attributes:
        user_id: 匹配到的用户ID（0 表示未匹配到）
        matched_key: 匹配使用的 key（短链 key / relation_id 等）
        matched_at: 匹配时间
        confidence: 匹配置信度（0.0 ~ 1.0）
        extra: 额外信息
    """

    def __init__(
        self,
        user_id: int = 0,
        matched_key: str = "",
        matched_at: Optional[str] = None,
        confidence: float = 0.0,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.user_id = user_id
        self.matched_key = matched_key
        self.matched_at = matched_at
        self.confidence = confidence
        self.extra = extra or {}

    @property
    def is_matched(self) -> bool:
        """是否成功匹配到用户"""
        return self.user_id > 0

    def __repr__(self) -> str:
        return (
            f"MatchResult(user_id={self.user_id}, matched_key={self.matched_key}, "
            f"confidence={self.confidence})"
        )


class BaseAttributionStrategy(ABC):
    """跟单匹配策略抽象基类"""

    @abstractmethod
    def get_strategy_name(self) -> str:
        """获取策略名称"""
        ...

    @abstractmethod
    async def resolve_user(
        self,
        out_order_no: str,
        goods_id: str,
        channel_code: str,
        order_data: Optional[Dict[str, Any]] = None,
    ) -> MatchResult:
        """解析订单归属用户

        根据订单信息（商品ID、渠道等），在跟单窗口期内查找匹配的用户。

        Args:
            out_order_no: 渠道订单号
            goods_id: 商品ID
            channel_code: 渠道标识
            order_data: 原始订单数据（可选，策略可能需要）
        Returns:
            MatchResult 匹配结果
        """
        ...