# @ai-generated
"""
订单归属操作日志表 ORM 模型（B05-4-3 新建）
表名：abnormal_order_operation_log
业务说明：记录异常订单每次人工修改归属、备注、操作人员、变更前后参数，供后台审计追溯
"""
from sqlalchemy import Column, String, BigInteger, Text, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class AbnormalOrderOperationLog(Base, SerializableMixin, SoftDeleteMixin):
    """订单归属操作日志表"""

    __tablename__ = "abnormal_order_operation_log"
    __table_args__ = (
        # abnormal_order_id 单值索引 —— 按异常订单查询操作历史
        Index("idx_ao_abnormal_order_id", "abnormal_order_id"),
        # operation_type 单值索引 —— 按操作类型筛选
        Index("idx_ao_operation_type", "operation_type"),
        # operator_id 单值索引 —— 按操作人筛选
        Index("idx_ao_operator_id", "operator_id"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_ao_create_time", "create_time"),
        {
            "comment": "订单归属操作日志表",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 关联异常订单ID（非外键约束，仅逻辑关联，避免跨模块强耦合）
    abnormal_order_id = Column(BigInteger, nullable=False, comment="异常订单ID")
    # 操作人管理员ID
    operator_id = Column(BigInteger, nullable=False, comment="操作人管理员ID")
    # 操作类型：REVIEW-复核 / EDIT-编辑
    operation_type = Column(String(32), nullable=False, comment="操作类型：REVIEW-复核 / EDIT-编辑")
    # 变更前归属用户ID
    old_assigned_user_id = Column(BigInteger, default=0, comment="变更前归属用户ID")
    # 变更后归属用户ID
    new_assigned_user_id = Column(BigInteger, default=0, comment="变更后归属用户ID")
    # 变更前复核备注
    old_review_remark = Column(String(512), default="", comment="变更前复核备注")
    # 变更后复核备注
    new_review_remark = Column(String(512), default="", comment="变更后复核备注")
    # 变更前复核状态
    old_review_status = Column(String(32), default="", comment="变更前复核状态")
    # 变更后复核状态
    new_review_status = Column(String(32), default="", comment="变更后复核状态")
    # 操作补充说明
    remark = Column(Text, default="", comment="操作补充说明")