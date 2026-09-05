# @ai-generated
"""
佣金流水结算前置校验日志表 ORM 模型（B05-5 新建）
表名：commission_flow_validation_log
业务说明：记录佣金流水生成前的每项校验结果，包括订单状态、金额合法性、
重复拦截等校验项，供后台审计和异常追溯
"""
from sqlalchemy import Column, String, BigInteger, Text, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class CommissionFlowValidationLog(Base, SerializableMixin, SoftDeleteMixin):
    """佣金流水结算前置校验日志表"""

    __tablename__ = "commission_flow_validation_log"
    __table_args__ = (
        # order_id 单值索引 —— 按订单查询校验记录
        Index("idx_cfvl_order_id", "order_id"),
        # user_id 单值索引 —— 按用户查询校验记录
        Index("idx_cfvl_user_id", "user_id"),
        # validation_result 单值索引 —— 按校验结果筛选
        Index("idx_cfvl_validation_result", "validation_result"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_cfvl_create_time", "create_time"),
        {
            "comment": "佣金流水结算前置校验日志表",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 关联订单ID
    order_id = Column(BigInteger, nullable=False, comment="关联订单ID")
    # 用户ID
    user_id = Column(BigInteger, nullable=False, comment="用户ID")
    # 校验类型：PRE_SETTLE-结算前置校验 / PRE_DEDUCT-扣减前置校验
    validation_type = Column(String(32), nullable=False, comment="校验类型：PRE_SETTLE-结算前置校验/PRE_DEDUCT-扣减前置校验")
    # 校验结果：PASS-通过 / FAIL-失败
    validation_result = Column(String(32), nullable=False, comment="校验结果：PASS-通过/FAIL-失败")
    # 各项校验明细（JSON格式存储）
    check_items = Column(Text, nullable=False, comment="各项校验明细JSON")
    # 总体错误信息（校验失败时记录）
    error_message = Column(String(1024), default="", comment="总体错误信息")
    # 操作人管理员ID（0=系统自动）
    operator_id = Column(BigInteger, default=0, comment="操作人管理员ID（0=系统自动）")