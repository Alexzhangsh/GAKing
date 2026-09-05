# @ai-generated
"""
F04 营销消息模块 ORM 模型
表名：gaking_message_template / gaking_push_record / gaking_subscribe_binding
业务说明：消息模板管理（微信订阅消息+站内消息）、推送记录、订阅消息绑定
"""
from sqlalchemy import Column, String, Text, SmallInteger, JSON, DateTime, Boolean, UniqueConstraint

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class MessageTemplate(Base, SerializableMixin, SoftDeleteMixin):
    """消息模板表（微信订阅消息 + 站内消息）"""

    __tablename__ = "gaking_message_template"
    __table_args__ = (
        {"comment": "消息模板表（微信订阅消息 + 站内消息）", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 模板名称
    template_name = Column(String(128), nullable=False, comment="模板名称")
    # 模板类型：1=微信订阅消息 2=站内消息
    template_type = Column(SmallInteger, nullable=False, default=1, comment="模板类型：1=微信订阅消息 2=站内消息")
    # 微信订阅消息模板ID（type=1时必填）
    tmpl_id = Column(String(128), default="", comment="微信订阅消息模板ID（type=1时必填）")
    # 消息标题
    title = Column(String(256), default="", comment="消息标题")
    # 消息内容（支持占位符 {{keyword1}}）
    content = Column(Text, nullable=False, comment="消息内容（支持占位符 {{keyword1}}）")
    # 关键词列表（微信订阅消息用）
    keywords = Column(JSON, nullable=True, comment="关键词列表（微信订阅消息用）")
    # 状态：1=启用 0=停用
    status = Column(SmallInteger, nullable=False, default=1, comment="状态：1=启用 0=停用")
    # 备注
    remark = Column(String(512), default="", comment="备注")


class PushRecord(Base, SerializableMixin):
    """推送记录表"""

    __tablename__ = "gaking_push_record"
    __table_args__ = (
        {"comment": "推送记录表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 关联消息模板ID
    template_id = Column(String(128), nullable=False, default="0", comment="关联消息模板ID")
    # 推送目标用户ID
    user_id = Column(String(128), nullable=False, default="0", comment="推送目标用户ID")
    # 推送状态：1=成功 2=失败 3=待发送
    push_status = Column(SmallInteger, nullable=False, default=3, comment="推送状态：1=成功 2=失败 3=待发送")
    # 实际推送时间
    push_time = Column(DateTime, nullable=True, comment="实际推送时间")
    # 失败原因
    error_msg = Column(String(512), default="", comment="失败原因")


class SubscribeBinding(Base, SerializableMixin):
    """订阅消息绑定表（用户授权记录）"""

    __tablename__ = "gaking_subscribe_binding"
    __table_args__ = (
        UniqueConstraint("user_id", "template_id", name="uq_user_template"),
        {"comment": "订阅消息绑定表（用户授权记录）", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # C端用户ID
    user_id = Column(String(128), nullable=False, default="0", comment="C端用户ID")
    # 关联消息模板ID
    template_id = Column(String(128), nullable=False, default="0", comment="关联消息模板ID")
    # 订阅状态：1=已订阅 0=已取消
    subscribe_status = Column(SmallInteger, nullable=False, default=1, comment="订阅状态：1=已订阅 0=已取消")
    # 订阅时间
    subscribe_time = Column(DateTime, nullable=True, comment="订阅时间")
    # 过期时间（微信订阅消息1次性模板有效期7天）
    expire_time = Column(DateTime, nullable=True, comment="过期时间（微信订阅消息1次性模板有效期7天）")
