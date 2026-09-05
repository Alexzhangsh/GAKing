# @ai-generated
"""
商品管理扩展表 ORM 模型
表名：goods_management
业务说明：CPS 商品本地管理扩展表，存储平台对 CPS 商品的管理标记（上下架/排序/备注）
         商品基础数据来自 CPS 渠道（喵有券/订单侠）实时拉取缓存，本表仅存"管理标记"
         通过 goods_id + source_channel 与 CPS 渠道商品关联
id / is_delete / create_time / update_time 由 Base 基类统一提供。
"""
from datetime import datetime

from sqlalchemy import Column, String, BigInteger, Integer, Index, Numeric, DateTime

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class GoodsManagement(Base, SerializableMixin, SoftDeleteMixin):
    """商品管理扩展表"""

    __tablename__ = "goods_management"
    __table_args__ = (
        # goods_id + source_channel 联合唯一索引 —— 同渠道同商品仅一条记录
        Index("idx_goods_channel", "goods_id", "source_channel", unique=True),
        # shelf_status 单值索引 —— 按上下架状态筛选
        Index("idx_shelf_status", "shelf_status"),
        # category 单值索引 —— 按类目筛选
        Index("idx_category", "category"),
        # sync_status 单值索引 —— 按同步状态筛选
        Index("idx_sync_status", "sync_status"),
        {
            "comment": "商品管理扩展表（CPS 商品本地管理标记）",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # CPS 渠道商品唯一ID（与 GoodsDTO.goods_id 一致）
    goods_id = Column(String(128), nullable=False, comment="CPS 渠道商品唯一ID")
    # 来源渠道：myq=喵有券 / dta=大淘客 / orderx=订单侠
    source_channel = Column(String(16), nullable=False, comment="来源渠道码")
    # 商品标题（冗余存储，便于后台列表展示，避免每次回查 CPS 渠道）
    goods_title = Column(String(512), default="", nullable=False, comment="商品标题")
    # 商品主图链接（冗余存储）
    goods_img = Column(String(1024), default="", nullable=False, comment="商品主图链接")
    # 销售价（元，冗余存储）
    sale_price = Column(Numeric(10, 2), default=0.00, nullable=False, comment="销售价(元)")
    # 商品原价（元，冗余存储，用于展示划线价）
    original_price = Column(Numeric(10, 2), default=0.00, nullable=False, comment="商品原价(元)")
    # 佣金比例（百分比，冗余存储）
    commission_rate = Column(
        Numeric(5, 2), default=0.00, nullable=False, comment="佣金比例(%)"
    )
    # 普通会员奖金（元）
    bonus_price_normal = Column(Numeric(10, 2), default=0.00, nullable=False, comment="普通会员奖金(元)")
    # 普通会员奖金比例（%）
    bonus_rate_normal = Column(Numeric(5, 2), default=0.00, nullable=False, comment="普通会员奖金比例(%)")
    # VIP会员奖金（元）
    bonus_price_vip = Column(Numeric(10, 2), default=0.00, nullable=False, comment="VIP会员奖金(元)")
    # VIP会员奖金比例（%）
    bonus_rate_vip = Column(Numeric(5, 2), default=0.00, nullable=False, comment="VIP会员奖金比例(%)")
    # 商品类目
    category = Column(String(64), default="", nullable=False, comment="商品类目")
    # 店铺名称
    shop_name = Column(String(128), default="", nullable=False, comment="店铺名称")
    # 上下架状态：on_shelf=上架 / off_shelf=下架
    shelf_status = Column(
        String(16), default="on_shelf", nullable=False, comment="上下架状态"
    )
    # 排序权重（数字越小越靠前，0 表示默认）
    sort_order = Column(Integer, default=0, nullable=False, comment="排序权重")
    # 管理员备注
    admin_remark = Column(String(512), default="", nullable=False, comment="管理员备注")
    # 最后操作管理员ID
    last_admin_id = Column(
        BigInteger, default=0, nullable=False, comment="最后操作管理员ID"
    )

    # ── B16 预热任务新增字段 ─────────────────────────────────
    # 最后同步时间（定时预热/刷新时更新）
    last_sync_time = Column(DateTime, nullable=True, comment="最后同步时间")
    # 热度值（被用户访问次数，0=普通商品，>0=热门商品）
    popularity = Column(Integer, default=0, nullable=False, comment="热度值(被访问次数)")
    # 最后浏览时间（用于冷品清理判定）
    last_visit_time = Column(DateTime, nullable=True, comment="最后浏览时间")
    # 同步状态：normal=正常 expired=过期（30天无浏览）
    sync_status = Column(
        String(16), default="normal", nullable=False, comment="同步状态: normal=正常 expired=过期"
    )
