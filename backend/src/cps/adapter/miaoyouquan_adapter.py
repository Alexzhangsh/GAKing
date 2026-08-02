# @ai-generated
"""
喵有券 CPS 渠道适配器
对接喵有券（ecapi）开放 API，完成搜索、转链、订单拉取全接口适配
字段映射对齐项目统一商品/订单 DTO
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.cps.adapter.base_adapter import BaseCpsAdapter
from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
from src.cps.adapter.dto import (
    GoodsDTO,
    GoodsSearchResult,
    ConvertLinkResult,
    OrderDTO,
    OrderPullResult,
)
from src.cps.adapter.http_client import post_json
from src.config.env_config import EnvConfig

logger = logging.getLogger("cps.miaoyouquan")


class MiaoyouquanAdapter(BaseCpsAdapter):
    """喵有券 CPS 适配器

    渠道地址：https://www.ecapi.cn
    核心鉴权：apkey（不可用 H5 Key 做服务端接口调用）
    """

    BASE_URL = "https://www.ecapi.cn"

    API_SEARCH = f"{BASE_URL}/api/goods/search"
    API_CONVERT = f"{BASE_URL}/api/tpwd/convert"
    API_ORDER_LIST = f"{BASE_URL}/api/order/list"
    API_HEALTH = f"{BASE_URL}/api/system/ping"

    def __init__(self, apkey: Optional[str] = None):
        self._apkey = apkey or EnvConfig.MIAO_QUAN_TOKEN
        self._h5_key = ""

    # ── 渠道基本信息 ──────────────────────────────────────

    def get_channel_name(self) -> str:
        return "喵有券"

    def get_channel_code(self) -> str:
        return "myq"

    def get_pid(self) -> str:
        return ""

    def get_api_key(self) -> str:
        return self._apkey

    def _build_params(self, params: Dict[str, str]) -> Dict[str, str]:
        """构建带 apkey 的请求参数"""
        full = {"apkey": self._apkey}
        full.update(params)
        return full

    # ── 商品搜索 ──────────────────────────────────────────

    async def search_goods(
        self,
        keyword: str,
        page: int = 1,
        size: int = 20,
    ) -> GoodsSearchResult:
        """商品物料查询接口

        对接喵有券商品搜索接口，字段映射：
        item_id → goods_id, price → original_price, coupon_price → sale_price 等
        """
        self._log(
            logging.INFO,
            "search_goods: keyword=%s page=%s size=%s",
            keyword,
            page,
            size,
        )

        params = self._build_params(
            {
                "keyword": keyword,
                "page": str(page),
                "size": str(size),
            }
        )

        data = await post_json(
            self.API_SEARCH,
            data=params,
            channel_name=self.get_channel_name(),
            logger_tag="search",
        )

        if data.get("code") != 10000:
            raise CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message=f"喵有券搜索接口错误: {data.get('msg', 'unknown')}",
                channel_name=self.get_channel_name(),
                raw_response=data,
            )

        raw_items: List[Dict[str, Any]] = data.get("data", {}).get("list", []) or []
        items: List[GoodsDTO] = []
        for item in raw_items:
            try:
                goods = GoodsDTO(
                    goods_id=str(item.get("item_id", "")),
                    goods_title=str(item.get("title", "")),
                    goods_img=str(item.get("pic_url", "")),
                    original_price=Decimal(str(item.get("price", "0"))),
                    sale_price=Decimal(str(item.get("coupon_price", "0"))),
                    commission_rate=Decimal(str(item.get("commission_rate", "0"))),
                    estimate_commission=Decimal(str(item.get("commission", "0"))),
                    category=str(item.get("category", "")),
                    promote_url=str(item.get("share_url", "")),
                    coupon_info=item.get("coupon_info"),
                    shop_name=str(item.get("shop_name", "")),
                    sales_volume=int(item.get("sales", 0)),
                    source_channel=self.get_channel_code(),
                )
                items.append(goods)
            except Exception as e:
                self._log(
                    logging.WARNING, "商品字段转换失败: %s, item=%s", e, str(item)[:100]
                )

        total = (
            data.get("data", {}).get("total", len(items))
            if data.get("data")
            else len(items)
        )
        self._log(
            logging.INFO, "search_goods result: items=%s total=%s", len(items), total
        )

        return GoodsSearchResult(
            items=items,
            total=int(total),
            page=page,
            size=size,
        )

    # ── 链接转链 ──────────────────────────────────────────

    async def convert_link(
        self,
        original_url: str,
        user_channel_id: str,
    ) -> ConvertLinkResult:
        """高佣转链接口

        对接喵有券转链接口，传入原始链接+渠道溯源标识
        """
        self._log(
            logging.INFO,
            "convert_link: url=%s channel_id=%s",
            original_url,
            user_channel_id,
        )

        params = self._build_params(
            {
                "url": original_url,
                "relation_id": user_channel_id,
            }
        )

        data = await post_json(
            self.API_CONVERT,
            data=params,
            channel_name=self.get_channel_name(),
            logger_tag="convert",
        )

        if data.get("code") != 10000:
            raise CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message=f"喵有券转链接口错误: {data.get('msg', 'unknown')}",
                channel_name=self.get_channel_name(),
                raw_response=data,
            )

        result_data = data.get("data", {})
        convert_result = ConvertLinkResult(
            promote_url=str(result_data.get("share_url", "")),
            channel_pid=str(result_data.get("relation_id", user_channel_id)),
            estimate_commission=Decimal(str(result_data.get("commission", "0"))),
            goods_id=str(result_data.get("item_id", "")),
            raw_data=data,
        )

        self._log(
            logging.INFO,
            "convert_link result: promote_url=%s commission=%s",
            convert_result.promote_url,
            convert_result.estimate_commission,
        )
        return convert_result

    # ── 订单同步拉取 ──────────────────────────────────────

    async def pull_order(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> OrderPullResult:
        """订单查询接口

        对接喵有券订单列表查询接口，批量拉取渠道订单原始数据
        字段映射：tb_order_id → origin_order_id, total_fee → order_amount 等
        """
        self._log(
            logging.INFO,
            "pull_order: start=%s end=%s",
            start_time.isoformat(),
            end_time.isoformat(),
        )

        params = self._build_params(
            {
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        data = await post_json(
            self.API_ORDER_LIST,
            data=params,
            channel_name=self.get_channel_name(),
            logger_tag="pull_order",
        )

        if data.get("code") != 10000:
            raise CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message=f"喵有券订单拉取接口错误: {data.get('msg', 'unknown')}",
                channel_name=self.get_channel_name(),
                raw_response=data,
            )

        raw_orders: List[Dict[str, Any]] = data.get("data", {}).get("list", []) or []
        orders: List[OrderDTO] = []
        for raw in raw_orders:
            try:
                order = self._parse_order(raw)
                orders.append(order)
            except Exception as e:
                self._log(
                    logging.WARNING, "订单字段转换失败: %s, raw=%s", e, str(raw)[:100]
                )

        self._log(logging.INFO, "pull_order result: orders=%s", len(orders))

        return OrderPullResult(
            orders=orders,
            total=len(orders),
            start_time=start_time,
            end_time=end_time,
        )

    def _parse_order(self, raw: Dict[str, Any]) -> OrderDTO:
        """解析喵有券原始订单数据为标准 DTO"""
        return OrderDTO(
            origin_order_id=str(raw.get("tb_order_id", "")),
            pay_time=self._parse_datetime(raw.get("pay_time")),
            confirm_time=self._parse_datetime(raw.get("confirm_time")),
            settle_time=self._parse_datetime(raw.get("settlement_time")),
            order_status=str(raw.get("order_status", "")),
            order_amount=Decimal(str(raw.get("total_fee", "0"))),
            channel_pid=str(raw.get("pid", "")),
            refund_info=raw.get("refund_info"),
            goods_id=str(raw.get("item_id", "")),
            goods_title=str(raw.get("title", "")),
            goods_img=str(raw.get("pic_url", "")),
            total_commission=Decimal(str(raw.get("commission", "0"))),
            channel_code=self.get_channel_code(),
            raw_data=raw,
        )

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """安全解析 datetime 字段"""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y%m%d%H%M%S"):
            try:
                return datetime.strptime(str(value), fmt)
            except (ValueError, TypeError):
                continue
        return None

    # ── 健康探测 ──────────────────────────────────────────

    async def health_check(self) -> bool:
        """探测喵有券接口连通性"""
        try:
            params = self._build_params({"test": "1"})
            data = await post_json(
                self.API_HEALTH,
                data=params,
                channel_name=self.get_channel_name(),
                logger_tag="health",
            )
            self._log(logging.INFO, "health_check result: %s", data.get("code"))
            return data.get("code") == 10000
        except CpsChannelException as e:
            self._log(logging.WARNING, "health_check failed: %s", e)
            return False
