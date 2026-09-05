# @ai-generated
"""
B06-2 渠道导出任务日志表 ORM 模型
表名：gaking_channel_export_task_log
业务说明：记录渠道订单报表导出和佣金账单导出任务的执行日志，
包括任务类型、执行状态、文件路径、参数快照等
"""
from sqlalchemy import Column, String, BigInteger, Integer, Text, DateTime, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ChannelExportTaskLog(Base, SerializableMixin, SoftDeleteMixin):
    """渠道导出任务日志表"""

    __tablename__ = "gaking_channel_export_task_log"
    __table_args__ = (
        Index("idx_task_type", "task_type"),
        Index("idx_operator_id", "operator_id"),
        Index("idx_status", "status"),
        Index("idx_create_time", "create_time"),
        {"comment": "渠道导出任务日志表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 任务类型：order_export-订单报表导出 / commission_bill-佣金账单导出
    task_type = Column(String(32), nullable=False, comment="任务类型：order_export/commission_bill")
    # 渠道标识（筛选条件快照）
    channel_code = Column(String(32), default="", comment="渠道标识")
    # 任务状态：PROCESSING-处理中 / SUCCESS-导出成功 / FAILED-导出失败
    status = Column(String(32), nullable=False, default="PROCESSING", comment="任务状态：PROCESSING/SUCCESS/FAILED")
    # 导出文件路径（服务端相对路径）
    file_path = Column(String(512), default="", comment="导出文件路径")
    # 导出文件名
    file_name = Column(String(256), default="", comment="导出文件名")
    # 文件大小（字节）
    file_size = Column(BigInteger, default=0, comment="文件大小(字节)")
    # 导出行数
    row_count = Column(Integer, default=0, comment="导出行数")
    # 查询参数快照（JSON格式）
    params = Column(Text, default="", comment="查询参数快照(JSON)")
    # 错误信息
    error_message = Column(Text, default="", comment="错误信息")
    # 操作人ID
    operator_id = Column(BigInteger, nullable=False, default=0, comment="操作人ID")
    # 操作人姓名
    operator_name = Column(String(64), default="", comment="操作人姓名")
    # 任务开始时间
    started_at = Column(DateTime, nullable=True, comment="任务开始时间")
    # 任务结束时间
    finished_at = Column(DateTime, nullable=True, comment="任务结束时间")