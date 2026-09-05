# @ai-generated
"""
喵有券 CPS 渠道适配器（修复版）
对接喵有券（ecapi）开放 API，完成搜索、转链、订单拉取全接口适配
字段映射对齐项目统一商品/订单 DTO

修复说明（B01）：
1. BASE_URL: https://www.ecapi.cn → http://api.web.ecapi.cn
2. 请求方式: POST → GET（所有接口均为 GET + query params）
3. 响应码判断: code == 10000 → code == 200
4. 接口路径修正: 对接官方文档 ID=1(转链), ID=9(搜索), ID=83(订单)
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
from src.cps.adapter.http_client import get
from src.config.env_config import EnvConfig

logger = logging.getLogger("cps.miaoyouquan")


class MiaoyouquanAdapter(BaseCpsAdapter):
    """喵有券 CPS 适配器

    渠道地址：http://api.web.ecapi.cn
    核心鉴权：apkey（不可用 H5 Key 做服务端接口调用）
    官方文档：https://www.ecapi.cn/index/index/openapi.html
    """

    BASE_URL = "http://api.web.ecapi.cn"

    # 接口 ID=9：全网淘客商品查询 API（GET）
    API_SEARCH = f"{BASE_URL}/taoke/getTkMaterialItem"
    # 接口 ID=330：淘客万能转链 API（联盟版，GET，支持物料URL/口令/商品ID）
    API_CONVERT = f"{BASE_URL}/taoke/doTbHighCommissionPromotionUrl"
    # 接口 ID=83：淘宝客订单查询 API（GET）
    API_ORDER_LIST = f"{BASE_URL}/taoke/tbkOrderDetailsGet"

    def __init__(self, apkey: Optional[str] = None, tbname: Optional[str] = None, pid: Optional[str] = None):
        self._apkey = apkey or EnvConfig.MIAO_QUAN_TOKEN
        self._tbname = tbname or EnvConfig.MIAO_QUAN_TBNAME
        self._pid = pid or EnvConfig.MIAO_QUAN_PID
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
        """商品物料查询接口（ID=9）

        接口地址：http://api.web.ecapi.cn/taoke/getTkMaterialItem
        请求方式：GET
        响应码：200 表示成功
        字段映射：item_id→goods_id, reserve_price→original_price,
                 zk_final_price→sale_price, commission_rate→commission_rate,
                 pict_url→goods_img, volume→sales_volume, shop_title→shop_name,
                 url→promote_url, category_name→category
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
                "pageno": str(page),
                "pagesize": str(size),
                "ver_code": "101",  # 新版格式，带商品数量统计
                "tbname": self._tbname,  # 淘宝授权用户名
                # 不传 pid — 普通自助推广 PID 第三段会被 API 误作 relation_id 校验
                # 让 API 使用账号默认 PID 即可
            }
        )

        data = await get(
            self.API_SEARCH,
            params=params,
            channel_name=self.get_channel_name(),
            logger_tag="search",
        )

        if data.get("code") != 200:
            raise CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message=f"喵有券搜索接口错误: {data.get('msg', 'unknown')}",
                channel_name=self.get_channel_name(),
                raw_response=data,
            )

        # 新版格式(ver_code=101): data.data 为数组, data.totalcount 为总数
        # 若 data 外层有 totalcount 则用外层
        raw_items: List[Dict[str, Any]] = []
        total = 0

        inner_data = data.get("data", {})
        if isinstance(inner_data, dict):
            # 响应结构: data.list 为商品数组，data.totalcount 为总数
            raw_items = inner_data.get("list", []) or []
            total = int(inner_data.get("totalcount", 0) or 0)
        elif isinstance(inner_data, list):
            raw_items = inner_data
            total = len(raw_items)

        # 如果外层也有 totalcount，优先用外层
        outer_total = data.get("totalcount")
        if outer_total is not None:
            total = int(outer_total)

        items: List[GoodsDTO] = []
        for item in raw_items:
            try:
                # 处理 coupon_info：API 返回字符串（如"满50减5"），DTO 期望字典
                raw_coupon = item.get("coupon_info")
                coupon_info = None
                if isinstance(raw_coupon, dict):
                    coupon_info = raw_coupon
                elif isinstance(raw_coupon, str) and raw_coupon.strip():
                    coupon_info = {"desc": raw_coupon.strip()}

                # 处理 commission_rate：API 返回万分比（900=9.00%），DTO 期望百分比（9.00）
                raw_rate = Decimal(str(item.get("commission_rate", "0")))
                commission_rate = raw_rate / Decimal("100")

                # 处理 promote_url：API 返回 click_url
                promote_url = str(item.get("url", "") or item.get("click_url", ""))

                # 处理 sales_volume：API 返回 volume 可能为0，优先用 tk_total_sales
                raw_volume = item.get("volume", 0) or item.get("tk_total_sales", 0)
                try:
                    sales_volume = int(raw_volume)
                except (ValueError, TypeError):
                    sales_volume = 0

                goods = GoodsDTO(
                    goods_id=str(item.get("item_id", "")),
                    goods_title=str(item.get("title", "")),
                    goods_img=str(item.get("pict_url", "")),
                    original_price=Decimal(str(item.get("reserve_price", "0"))),
                    sale_price=Decimal(str(item.get("zk_final_price", "0"))),
                    commission_rate=commission_rate,
                    estimate_commission=Decimal(str(item.get("commission_amount", "0"))),
                    category=str(item.get("category_name", "")),
                    promote_url=promote_url,
                    coupon_info=coupon_info,
                    shop_name=str(item.get("shop_title", "")),
                    sales_volume=sales_volume,
                    source_channel=self.get_channel_code(),
                )
                items.append(goods)
            except Exception as e:
                self._log(
                    logging.WARNING, "商品字段转换失败: %s, item=%s", e, str(item)[:100]
                )

        self._log(
            logging.INFO, "search_goods result: items=%s total=%s", len(items), total
        )

        return GoodsSearchResult(
            items=items,
            total=total or len(items),
            page=page,
            size=size,
        )

    # ── 链接转链 ──────────────────────────────────────────

    async def convert_link(
        self,
        original_url: str,
        user_channel_id: str,
    ) -> ConvertLinkResult:
        """淘客万能转链接口（ID=330，联盟版）

        接口地址：http://api.web.ecapi.cn/taoke/doTbHighCommissionPromotionUrl
        请求方式：GET
        响应码：200 表示成功
        说明：
        - material_list 支持物料URL/淘口令，兼容搜索返回的 click_url
        - 账号 PID 非渠道专属推广位，无法使用 relation_id 做渠道归因，
          用户归属由系统自建短链（/s/{key}）承载
        - 响应取 data.material_url_list.material_url_list[0].link_info_dto
        """
        self._log(
            logging.INFO,
            "convert_link: url=%s channel_id=%s",
            original_url,
            user_channel_id,
        )

        # 搜索返回的 click_url 为协议相对地址（//s.click.taobao.com/...），需补全 https:
        material = original_url
        if material.startswith("//"):
            material = "https:" + material

        params = self._build_params(
            {
                "material_list": material,
                "tbname": self._tbname,
                "biz_scene_id": "1",  # 动态ID转链场景
            }
        )

        data = await get(
            self.API_CONVERT,
            params=params,
            channel_name=self.get_channel_name(),
            logger_tag="convert",
        )

        if data.get("code") != 200:
            raise CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message=f"喵有券转链接口错误: {data.get('msg', 'unknown')}",
                channel_name=self.get_channel_name(),
                raw_response=data,
            )

        # 响应格式: data.material_url_list.material_url_list[0]
        inner_data = data.get("data", {})
        material_list: List[Dict[str, Any]] = []
        if isinstance(inner_data, dict):
            material_list = (
                inner_data.get("material_url_list", {}).get("material_url_list", [])
                or []
            )

        if not material_list:
            raise CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message="喵有券转链结果为空（material_url_list 无数据）",
                channel_name=self.get_channel_name(),
                raw_response=data,
            )

        link_info = material_list[0].get("link_info_dto", {}) or {}
        promo_info = material_list[0].get("promotion_info_dto", {}) or {}
        promote_url = str(
            link_info.get("cps_short_url", "")
            or link_info.get("cps_long_url", "")
            or ""
        )
        if not promote_url:
            raise CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message="喵有券转链结果缺少推广链接（cps_short_url/cps_long_url 均为空）",
                channel_name=self.get_channel_name(),
                raw_response=data,
            )
        goods_id = str(link_info.get("material_id", "") or link_info.get("item_id", ""))
        commission_rate = Decimal(str(promo_info.get("commission_rate", "0")))

        convert_result = ConvertLinkResult(
            promote_url=promote_url,
            channel_pid=str(link_info.get("material_id", user_channel_id)),
            estimate_commission=commission_rate,
            goods_id=goods_id,
            raw_data=data,
        )

        self._log(
            logging.INFO,
            "convert_link result: promote_url=%s commission=%s goods_id=%s",
            convert_result.promote_url,
            convert_result.estimate_commission,
            convert_result.goods_id,
        )
        return convert_result

    # ── 订单同步拉取 ──────────────────────────────────────

    async def pull_order(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> OrderPullResult:
        """订单查询接口（ID=83）

        接口地址：http://api.web.ecapi.cn/taoke/tbkOrderDetailsGet
        请求方式：GET
        响应码：200 表示成功
        字段映射：trade_id→origin_order_id, alipay_total_price→order_amount,
                 item_id→goods_id, item_title→goods_title, item_img→goods_img,
                 total_commission_fee→total_commission, tk_status→order_status,
                 tb_paid_time→pay_time, tk_earning_time→settle_time,
                 seller_shop_title→shop_name
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
                "query_type": "1",  # 按订单淘客创建时间查询
                "page_size": "100",
                "page_no": "1",
                "tbname": self._tbname,  # 淘宝授权用户名（必需，否则报 tbname必须填写）
            }
        )

        data = await get(
            self.API_ORDER_LIST,
            params=params,
            channel_name=self.get_channel_name(),
            logger_tag="pull_order",
        )

        if data.get("code") != 200:
            raise CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message=f"喵有券订单拉取接口错误: {data.get('msg', 'unknown')}",
                channel_name=self.get_channel_name(),
                raw_response=data,
            )

        # 响应格式: data.data.list 为订单列表
        inner_data = data.get("data", {})
        raw_orders: List[Dict[str, Any]] = []
        if isinstance(inner_data, dict):
            raw_orders = inner_data.get("list", []) or []
        elif isinstance(inner_data, list):
            raw_orders = inner_data

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
        """解析喵有券原始订单数据为标准 DTO

        字段映射（淘宝客订单查询 API ID=83）：
        trade_id → origin_order_id（子订单号，非 trade_parent_id）
        alipay_total_price → order_amount
        tk_status → order_status（3=结算, 12=付款, 13=失效, 14=收货）
        total_commission_fee → total_commission
        """
        # 解析订单状态为中文描述
        tk_status = str(raw.get("tk_status", ""))
        status_map = {
            "12": "已付款",
            "13": "已失效",
            "14": "已收货",
            "3": "已结算",
        }
        order_status = status_map.get(tk_status, tk_status)

        return OrderDTO(
            origin_order_id=str(raw.get("trade_id", "")),
            pay_time=self._parse_datetime(raw.get("tb_paid_time")),
            confirm_time=self._parse_datetime(raw.get("tk_earning_time")),
            settle_time=self._parse_datetime(raw.get("tk_earning_time")),
            order_status=order_status,
            order_amount=Decimal(str(raw.get("alipay_total_price", "0"))),
            channel_pid=str(raw.get("adzone_id", "")),
            refund_info={"refund_tag": raw.get("refund_tag", 0)},
            goods_id=str(raw.get("item_id", "")),
            goods_title=str(raw.get("item_title", "")),
            goods_img=str(raw.get("item_img", "")),
            total_commission=Decimal(str(raw.get("total_commission_fee", "0"))),
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
        """探测喵有券接口连通性（使用搜索接口测试）"""
        try:
            params = self._build_params(
                {
                    "keyword": "测试",
                    "pageno": "1",
                    "pagesize": "1",
                    "ver_code": "101",
                }
            )
            data = await get(
                self.API_SEARCH,
                params=params,
                channel_name=self.get_channel_name(),
                logger_tag="health",
            )
            self._log(logging.INFO, "health_check result: code=%s", data.get("code"))
            return data.get("code") == 200
        except CpsChannelException as e:
            self._log(logging.WARNING, "health_check failed: %s", e)
            return False