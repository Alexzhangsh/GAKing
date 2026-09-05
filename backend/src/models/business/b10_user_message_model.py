# @ai-generated
"""
B10 站内消息 ORM 模型
表名：gaking_user_message
业务说明：用户站内消息箱，支持佣金到账/提现审核/订单成交/退款冲减4类业务消息
          已读状态管理，关联业务ID用于前端跳转

id / is_delete / create_time / update_time 由 Base 基类统一提供。
"""
from sqlalchemy import Column, String, BigInteger, SmallInteger, Text, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class UserMessage(Base, SerializableMixin, SoftDeleteMixin):
    """用户站内消息表"""

    __tablename__ = "gaking_user_message"
    __table_args__ = (
        # user_id + is_read 联合索引 —— 用户未读消息查询
        Index("idx_user_read", "user_id", "is_read"),
        # user_id 单值索引 —— 按用户查询消息列表
        Index("idx_um_user_id", "user_id"),
        # message_type 单值索引 —— 按类型筛选
        Index("idx_um_message_type", "message_type"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_um_create_time", "create_time"),
        # user_id + create_time 联合索引 —— 用户消息列表时间排序
        Index("idx_um_user_time", "user_id", "create_time"),
        {"comment": "用户站内消息表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 接收用户ID
    user_id = Column(BigInteger, nullable=False, comment="接收用户ID")
    # 消息业务类型：commission/withdraw/order/refund
    message_type = Column(String(32), nullable=False, comment="消息业务类型：commission/withdraw/order/refund")
    # 消息标题
    title = Column(String(256), nullable=False, comment="消息标题")
    # 消息内容摘要
    content = Column(Text, nullable=False, comment="消息内容")
    # 关联业务ID（用于前端跳转，如订单ID/提现申请ID/佣金流水ID）
    biz_id = Column(String(64), default="", comment="关联业务ID（用于前端跳转）")
    # 已读状态：0=未读 1=已读
    is_read = Column(SmallInteger, nullable=False, default=0, comment="已读状态：0=未读 1=已读")
    # 已读时间
    read_time = Column(String(32), default="", comment="已读时间（YYYY-MM-DD HH:mm:ss）")
    # 推送状态：0=待推送 1=已推送 2=推送失败
    push_status = Column(SmallInteger, nullable=False, default=0, comment="推送状态：0=待推送 1=已推送 2=推送失败")
    # 推送失败原因
    push_error = Column(String(512), default="", comment="推送失败原因")