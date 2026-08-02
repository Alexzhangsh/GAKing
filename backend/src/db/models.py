# @ai-generated
"""
后台管理相关 ORM 模型
注：系统配置表(gaking_system_config / gaking_cloud_config / gaking_pay_config /
gaking_channel_mapping) 已迁移至 src/models/system/ 目录，
本文件仅保留后台管理域模型。
"""
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey, UniqueConstraint, Index, BigInteger, Numeric
from sqlalchemy.orm import relationship

from .base import Base


class AdminRole(Base):
    __tablename__ = "admin_role"
    __table_args__ = (
        UniqueConstraint("role_name", name="uk_role_name"),
        {"comment": "后台角色表"},
    )

    role_name = Column(String(64), nullable=False, comment="角色名称")
    role_desc = Column(String(512), default="", comment="角色描述")
    permissions = Column(Text, default="", comment="权限列表JSON")
    status = Column(Boolean, default=True, nullable=False, comment="状态：0-禁用 1-启用")


class AdminUser(Base):
    __tablename__ = "admin_user"
    __table_args__ = (
        UniqueConstraint("username", name="uk_username"),
        Index("idx_role_id", "role_id"),
        Index("idx_status", "status"),
        {"comment": "后台管理员表"},
    )

    username = Column(String(64), nullable=False, comment="用户名")
    password = Column(String(256), nullable=False, comment="密码（bcrypt加密）")
    real_name = Column(String(64), default="", comment="真实姓名")
    phone = Column(String(32), default="", comment="手机号")
    email = Column(String(128), default="", comment="邮箱")
    role_id = Column(BigInteger, ForeignKey("admin_role.id"), nullable=False, comment="角色ID")
    status = Column(Boolean, default=True, nullable=False, comment="状态：0-禁用 1-启用")

    role = relationship("AdminRole", lazy="select")


class AuditLogs(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_action", "action"),
        Index("idx_target_type", "target_type"),
        {"comment": "审计日志表"},
    )

    user_id = Column(BigInteger, nullable=False, comment="操作人ID")
    user_name = Column(String(64), default="", comment="操作人姓名")
    action = Column(String(128), nullable=False, comment="操作描述")
    target_type = Column(String(64), default="", comment="目标类型")
    target_id = Column(BigInteger, default=0, comment="目标ID")
    details = Column(Text, default="", comment="脱敏操作内容")
    ip_address = Column(String(64), default="", comment="IP地址")
    user_agent = Column(String(512), default="", comment="User Agent")


class GakingTaskStatus(Base):
    __tablename__ = "gaking_task_status"
    __table_args__ = (
        Index("idx_task_name", "task_name"),
        Index("idx_status", "status"),
        Index("idx_create_time", "create_time"),
        {"comment": "定时任务执行状态表"},
    )

    task_name = Column(String(128), nullable=False, comment="任务名称")
    status = Column(String(32), nullable=False, comment="执行状态：running/success/failed/skipped")
    message = Column(String(512), default="", comment="执行结果消息")
    retry_count = Column(Integer, default=0, nullable=False, comment="重试次数")
    error_stack = Column(Text, default="", comment="异常堆栈信息")
