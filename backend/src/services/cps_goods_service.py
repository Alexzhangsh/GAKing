# @ai-generated
"""
CPS 商品服务层
职责：调 B02 双层缓存 + B01 适配器，抹平渠道差异，对外提供商品搜索/转链能力

依赖关系：
- B01 适配器（AdapterFactory 选择）→ 实际回源拉取
- B02 缓存（GoodsCacheManager）→ 双层缓存 + 防穿透/击穿
- 渠道异常（CpsChannelException）→ 降级为业务异常
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.cps.adapter.base_adapter import BaseCpsAdapter
from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
from src.cps.adapter.dto import GoodsDTO, GoodsSearchResult
from src.cps.adapter_factory import AdapterFactory
from src.cps.cache.goods_cache import GoodsCacheManager
from src.dao.goods_management_dao import GoodsManagementDAO
from src.db.init_db import DatabaseManager
from src.schemas.cps_goods import (
    BizException,
    ConvertLinkRequest,
    ConvertLinkResponse,
    GoodsItemResponse,
    GoodsSearchRequest,
    GoodsSearchResponse,
)

logger = logging.getLogger("service.cps_goods")


class CpsGoodsService:
    """CPS 商品服务

    对外提供商品搜索、链接转链能力
    - 搜索：自动走 B02 缓存，未命中走 B01 适配器回源
    - 转链：直接走 B01 适配器（转链结果因 user_channel_id 差异不缓存）
    """

    def __init__(self) -> None:
        # channel_code → GoodsCacheManager（每个渠道独立缓存管理器）
        self._cache_managers: dict = {}

    # ── 内部工具 ────────────────────────────────────────

    def _get_cache_manager(self, channel_code: str) -> GoodsCacheManager:
        """获取指定渠道的缓存管理器（延迟绑定适配器）"""
        if channel_code not in self._cache_managers:
            adapter = AdapterFactory.get_adapter(channel_code)
            self._cache_managers[channel_code] = GoodsCacheManager(adapter=adapter)
        return self._cache_managers[channel_code]

    @staticmethod
    def _goods_dto_to_response(goods: GoodsDTO) -> GoodsItemResponse:
        """GoodsDTO → 出参响应项"""
        return GoodsItemResponse(
            goods_id=goods.goods_id,
            goods_title=goods.goods_title,
            goods_img=goods.goods_img,
            original_price=float(goods.original_price),
            sale_price=float(goods.sale_price),
            commission_rate=float(goods.commission_rate),
            estimate_commission=float(goods.estimate_commission),
            category=goods.category,
            promote_url=goods.promote_url,
            shop_name=goods.shop_name,
            sales_volume=goods.sales_volume,
            source_channel=goods.source_channel,
        )

    # ════════════════════════════════════════════════════
    # 本地管理表覆盖（管理端编辑 → 小程序生效）
    # ════════════════════════════════════════════════════

    @staticmethod
    async def _apply_local_overrides(
        items: List[GoodsDTO], channel_code: str
    ) -> List[GoodsDTO]:
        """用本地 goods_management 管理表覆盖 CPS 渠道返回的商品字段，并过滤下架商品

        管理端在后台编辑的价格/佣金/标题/主图/类目/店铺等字段存储在本地管理表，
        CPS 搜索结果需应用这些覆盖；shelf_status=off_shelf 的商品从小程序搜索中移除。
        覆盖在缓存读取之后执行，因此管理端编辑无需主动失效缓存即可实时生效。
        """
        if not items:
            return items

        goods_ids = [g.goods_id for g in items if g.goods_id]
        if not goods_ids:
            return items

        async with DatabaseManager.get_session() as session:
            dao = GoodsManagementDAO(session)
            managed_list = await dao.list_by_goods_ids(goods_ids, channel_code)

        managed_map: Dict[str, Any] = {m.goods_id: m for m in managed_list}

        result: List[GoodsDTO] = []
        for goods in items:
            m = managed_map.get(goods.goods_id)
            if m is None:
                # 未纳入本地管理，保留渠道原始数据
                result.append(goods)
                continue

            # 下架商品直接过滤
            if m.shelf_status == "off_shelf":
                continue

            # 本地管理表字段非空/非零时覆盖渠道原始值
            overrides: Dict[str, Any] = {}
            if m.goods_title:
                overrides["goods_title"] = m.goods_title
            if m.goods_img:
                overrides["goods_img"] = m.goods_img
            if m.sale_price is not None and m.sale_price > 0:
                overrides["sale_price"] = Decimal(str(m.sale_price))
            if m.commission_rate is not None and m.commission_rate > 0:
                overrides["commission_rate"] = Decimal(str(m.commission_rate))
            if m.category:
                overrides["category"] = m.category
            if m.shop_name:
                overrides["shop_name"] = m.shop_name

            # 价格或佣金被覆盖时，重算预估佣金 = 售价 × 佣金率 / 100
            if "sale_price" in overrides or "commission_rate" in overrides:
                new_price = overrides.get("sale_price", goods.sale_price)
                new_rate = overrides.get("commission_rate", goods.commission_rate)
                overrides["estimate_commission"] = (
                    new_price * new_rate / Decimal("100")
                ).quantize(Decimal("0.01"))

            if overrides:
                goods = goods.model_copy(update=overrides)
            result.append(goods)

        return result

    # ════════════════════════════════════════════════════
    # 商品搜索
    # ════════════════════════════════════════════════════

    async def search_goods(
        self,
        request: GoodsSearchRequest,
    ) -> GoodsSearchResponse:
        """商品搜索（走 B02 双层缓存）

        Args:
            request: 搜索请求参数
        Returns:
            搜索响应（含 cache_hit 标记）
        Raises:
            BizException: 渠道异常降级
        """
        channel_code = request.channel_code
        keyword = request.keyword

        # 获取缓存管理器（绑定对应渠道适配器）
        try:
            cache_mgr = self._get_cache_manager(channel_code)
        except ValueError as e:
            raise BizException(code=400, msg=str(e))

        # 调 B02 缓存（未命中自动走 B01 适配器回源）
        try:
            result: GoodsSearchResult = await cache_mgr.search_goods(
                keyword=keyword,
                page=request.page,
                size=request.size,
            )
        except CpsChannelException as e:
            logger.warning(
                f"search_goods channel exception: channel={channel_code} "
                f"keyword={keyword} error_type={e.error_type} msg={e}",
                exc_info=True,
            )
            raise self._convert_channel_exception(e) from e
        except Exception as e:
            logger.error(
                f"search_goods unexpected error: channel={channel_code} "
                f"keyword={keyword} err={e}",
                exc_info=True,
            )
            raise BizException(code=500, msg="商品搜索服务异常") from e

        # 应用本地管理表覆盖（价格/佣金/标题等），过滤下架商品
        overridden_items = await self._apply_local_overrides(
            result.items, channel_code
        )

        # 转换出参
        items: List[GoodsItemResponse] = [
            self._goods_dto_to_response(g) for g in overridden_items
        ]

        return GoodsSearchResponse(
            items=items,
            total=result.total,
            page=result.page,
            size=result.size,
            cache_hit=len(items) > 0,  # 简化标记：有数据则视为命中
        )

    # ════════════════════════════════════════════════════
    # 链接转链
    # ════════════════════════════════════════════════════

    async def convert_link(
        self,
        request: ConvertLinkRequest,
    ) -> ConvertLinkResponse:
        """链接转链（直调 B01 适配器，不缓存）

        转链结果因 user_channel_id 差异不缓存，每次走适配器实时获取

        Args:
            request: 转链请求
        Returns:
            转链响应
        Raises:
            BizException: 渠道异常降级
        """
        channel_code = request.channel_code

        try:
            adapter = AdapterFactory.get_adapter(channel_code)
        except ValueError as e:
            raise BizException(code=400, msg=str(e))

        try:
            convert_result = await adapter.convert_link(
                original_url=request.original_url,
                user_channel_id=request.user_channel_id,
            )
        except CpsChannelException as e:
            logger.warning(
                f"convert_link channel exception: channel={channel_code} "
                f"url={request.original_url} error_type={e.error_type} msg={e}",
                exc_info=True,
            )
            raise self._convert_channel_exception(e) from e
        except Exception as e:
            logger.error(
                f"convert_link unexpected error: channel={channel_code} "
                f"url={request.original_url} err={e}",
                exc_info=True,
            )
            raise BizException(code=500, msg="链接转链服务异常") from e

        return ConvertLinkResponse(
            promote_url=convert_result.promote_url,
            tpwd=convert_result.tpwd,
            channel_pid=convert_result.channel_pid,
            estimate_commission=float(convert_result.estimate_commission),
            goods_id=convert_result.goods_id,
            channel_code=channel_code,
        )

    # ════════════════════════════════════════════════════
    # 异常转换
    # ════════════════════════════════════════════════════

    @staticmethod
    def _convert_channel_exception(e: CpsChannelException) -> BizException:
        """将 B01 渠道异常转换为对外业务异常

        渠道限流 → 429
        密钥失效 → 503（上游不可用）
        接口超时 → 504
        商品/订单不存在 → 404
        其他渠道错误 → 502（上游错误）
        """
        error_type = e.error_type
        if error_type == CpsErrorType.RATE_LIMITED:
            return BizException(code=429, msg=f"渠道接口限流: {e}")
        if error_type == CpsErrorType.INVALID_API_KEY:
            return BizException(code=503, msg="渠道密钥失效，服务暂不可用")
        if error_type == CpsErrorType.REQUEST_TIMEOUT:
            return BizException(code=504, msg="渠道接口响应超时")
        if error_type == CpsErrorType.GOODS_NOT_FOUND:
            return BizException(code=404, msg="商品不存在")
        if error_type == CpsErrorType.NO_ORDER_FOUND:
            return BizException(code=404, msg="订单不存在")
        if error_type == CpsErrorType.NETWORK_ERROR:
            return BizException(code=502, msg=f"渠道网络异常: {e}")
        # API_ERROR / PARSE_ERROR 等
        return BizException(code=502, msg=f"渠道接口异常: {e}")
