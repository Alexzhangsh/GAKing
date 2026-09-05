# @ai-generated
"""
B07-1 逆向佣金冲减记录表 ORM 模型
表名：gaking_reverse_commission_record
业务说明：记录退款订单逆向佣金冲减的全生命周期，
包括订单识别、金额冻结、平台回扣、失败重试与手动调整
"""
from sqlalchemy import Column, String, BigInteger, Integer, Numeric, Text, DateTime, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ReverseCommissionRecord(Base, SerializableMixin, SoftDeleteMixin):
    """逆向佣金冲减记录表"""

    __tablename__ = "gaking_reverse_commission_record"
    __table_args__ = (
        # order_id 单值索引 —— 按订单查询冲减记录
        Index("idx_order_id", "order_id"),
        # user_id 单值索引 —— 按用户查询冲减记录
        Index("idx_user_id", "user_id"),
        # status 单值索引 —— 按状态批量查询
        Index("idx_status", "status"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_create_time", "create_time"),
        # 联合索引 —— 状态+创建时间，用于定时任务批量扫描待处理记录
        Index("idx_status_create_time", "status", "create_time"),
        {"comment": "逆向佣金冲减记录表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 关联订单ID
    order_id = Column(BigInteger, nullable=False, comment="关联订单ID")
    # 渠道订单号
    out_order_no = Column(String(64), default="", comment="渠道订单号")
    # 用户ID
    user_id = Column(BigInteger, nullable=False, default=0, comment="用户ID")
    # 渠道标识
    channel_code = Column(String(32), default="", comment="渠道标识")
    # 原始佣金金额（冲减前的用户佣金）
    original_commission = Column(Numeric(10, 2), default=0.00, nullable=False, comment="原始佣金金额(元)")
    # 实际扣减金额
    deducted_amount = Column(Numeric(10, 2), default=0.00, nullable=False, comment="实际扣减金额(元)")
    # 原始流水类型：ORDER/SUPPLEMENT
    flow_type = Column(String(32), default="", comment="原始流水类型：ORDER/SUPPLEMENT")
    # 原始流水转账状态：PENDING/SUCCESS
    flow_transfer_status = Column(String(32), default="", comment="原始流水转账状态：PENDING/SUCCESS")
    # 冲减记录状态：IDENTIFIED/FROZEN/CLAWBACK_DONE/FAILED/ADJUSTED
    status = Column(String(32), nullable=False, default="IDENTIFIED", comment="冲减状态：IDENTIFIED/FROZEN/CLAWBACK_DONE/FAILED/ADJUSTED")
    # 已重试次数
    retry_count = Column(Integer, default=0, comment="已重试次数")
    # 最大重试次数
    max_retry = Column(Integer, default=3, comment="最大重试次数")
    # 错误信息
    error_message = Column(Text, default="", comment="错误信息")
    # 关联扣减流水ID
    deduct_flow_id = Column(BigInteger, nullable=True, default=None, comment="关联扣减流水ID")
    # 操作人ID（手动操作时记录）
    operator_id = Column(BigInteger, nullable=False, default=0, comment="操作人ID")
    # 操作人姓名
    operator_name = Column(String(64), default="", comment="操作人姓名")
    # 备注
    remark = Column(String(512), default="", comment="备注")
    # 冻结时间
    frozen_at = Column(DateTime, nullable=True, comment="冻结时间")
    # 回扣完成时间
    clawback_at = Column(DateTime, nullable=True, comment="回扣完成时间")