# @ai-generated
"""
CPS 渠道熔断包装适配器

装饰器模式：包装 B01 原始适配器，在调用前后接入熔断器
- 调用前：检查熔断状态，OPEN 时返回兜底数据
- 调用后：成功记录 success，失败记录 failure
- 实现 BaseCpsAdapter 全部接口，上层（B02 缓存/B03 服务层）无感知

不修改 B01 适配器内部代码，仅做包装增强
"""
import logging
from datetime import datetime
from typing import Optional

from src.cps.adapter.base_adapter import BaseCpsAdapter
from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
from src.cps.adapter.dto import (
    ConvertLinkResult,
    GoodsDTO,
    GoodsSearchResult,
    OrderPullResult,
)
from src.cps.circuit_breaker import CircuitBreaker

logger = logging.getLogger("cps.circuit_breaker_adapter")


class CircuitBreakerAdapter(BaseCpsAdapter):
    """熔断包装适配器

    包装任意 BaseCpsAdapter 子类，接入熔断降级
    对外接口与原始适配器完全一致

    Args:
        adapter: 被包装的原始适配器（B01 实现）
        breaker: 熔断器实例（可选，默认全局单例）
    """

    # 全局熔断器单例（所有渠道共用同一实例，状态按 channel_code 隔离）
    _default_breaker: Optional[CircuitBreaker] = None

    @classmethod
    def get_default_breaker(cls) -> CircuitBreaker:
        """获取全局熔断器单例"""
        if cls._default_breaker is None:
            cls._default_breaker = CircuitBreaker()
        return cls._default_breaker

    @classmethod
    def reset_default_breaker(cls) -> None:
        """重置全局熔断器（测试用）"""
        cls._default_breaker = None

    def __init__(
        self,
        adapter: BaseCpsAdapter,
        breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self._adapter = adapter
        self._breaker = breaker or self.get_default_breaker()

    # ── 基础信息透传 ────────────────────────────────────

    def get_channel_name(self) -> str:
        return self._adapter.get_channel_name()

    def get_channel_code(self) -> str:
        return self._adapter.get_channel_code()

    def get_pid(self) -> str:
        return self._adapter.get_pid()

    def get_api_key(self) -> str:
        return self._adapter.get_api_key()

    def get_goods_by_id(self, goods_id: str) -> Optional[GoodsDTO]:
        # 同步方法无法接入异步熔断，直接透传（单商品详情走 search 兜底）
        return self._adapter.get_goods_by_id(goods_id)

    # ── 熔断保护的异步接口 ──────────────────────────────

    async def search_goods(
        self,
        keyword: str,
        page: int = 1,
        size: int = 20,
    ) -> GoodsSearchResult:
        """商品搜索（熔断保护 + 兜底空结果）"""
        channel = self.get_channel_code()
        if not await self._breaker.allow_request(channel):
            logger.warning(
                f"search_goods fallback (breaker open): "
                f"channel={channel} keyword={keyword}"
            )
            # 兜底：返回空结果，不抛异常
            return GoodsSearchResult(page=page, size=size)

        try:
            result = await self._adapter.search_goods(keyword, page, size)
            await self._breaker.record_success(channel)
            return result
        except Exception as e:
            await self._breaker.record_failure(channel)
            logger.warning(f"search_goods failure recorded: channel={channel} err={e}")
            raise

    async def convert_link(
        self,
        original_url: str,
        user_channel_id: str,
    ) -> ConvertLinkResult:
        """链接转链（熔断保护 + 抛异常降级）"""
        channel = self.get_channel_code()
        if not await self._breaker.allow_request(channel):
            logger.warning(f"convert_link rejected (breaker open): channel={channel}")
            raise CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message=f"渠道[{self.get_channel_name()}]熔断中，请稍后重试",
                channel_name=self.get_channel_name(),
            )

        try:
            result = await self._adapter.convert_link(original_url, user_channel_id)
            await self._breaker.record_success(channel)
            return result
        except Exception as e:
            await self._breaker.record_failure(channel)
            logger.warning(f"convert_link failure recorded: channel={channel} err={e}")
            raise

    async def pull_order(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> OrderPullResult:
        """订单拉取（熔断保护 + 兜底空结果）"""
        channel = self.get_channel_code()
        if not await self._breaker.allow_request(channel):
            logger.warning(f"pull_order fallback (breaker open): channel={channel}")
            return OrderPullResult(start_time=start_time, end_time=end_time)

        try:
            result = await self._adapter.pull_order(start_time, end_time)
            await self._breaker.record_success(channel)
            return result
        except Exception as e:
            await self._breaker.record_failure(channel)
            logger.warning(f"pull_order failure recorded: channel={channel} err={e}")
            raise

    async def health_check(self) -> bool:
        """健康探测（熔断 OPEN 时直接返回 False）"""
        channel = self.get_channel_code()
        if not await self._breaker.allow_request(channel):
            return False

        try:
            result = await self._adapter.health_check()
            if result:
                await self._breaker.record_success(channel)
            else:
                await self._breaker.record_failure(channel)
            return result
        except Exception as e:
            await self._breaker.record_failure(channel)
            logger.warning(f"health_check failure recorded: channel={channel} err={e}")
            return False
