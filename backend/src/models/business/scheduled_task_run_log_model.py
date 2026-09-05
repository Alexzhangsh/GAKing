# @ai-generated
"""
定时任务运行日志 ORM 模型（B05-7 新建）
表名：scheduled_task_run_log
业务说明：记录定时批量订单结算任务的每次运行情况，包括运行状态、处理统计、错误信息等
"""
from sqlalchemy import Column, String, BigInteger, Integer, Text, DateTime, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ScheduledTaskRunLog(Base, SerializableMixin, SoftDeleteMixin):
    """定时任务运行日志表"""

    __tablename__ = "scheduled_task_run_log"
    __table_args__ = (
        # task_name 单值索引 —— 按任务名称查询运行历史
        Index("idx_strl_task_name", "task_name"),
        # status 单值索引 —— 按运行状态筛选
        Index("idx_strl_status", "status"),
        # started_at 单值索引 —— 按时间范围查询
        Index("idx_strl_started_at", "started_at"),
        # 联合索引 —— 任务名+状态高频联查
        Index("idx_strl_task_status", "task_name", "status"),
        {
            "comment": "定时任务运行日志表（B05-7）",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 任务名称
    task_name = Column(String(128), nullable=False, comment="任务名称")
    # 运行批次ID（格式：{task_name}_{YYYYMMDDHHMMSS}）
    run_id = Column(String(64), nullable=False, unique=True, comment="运行批次ID")
    # 运行状态：running/success/failed/partial
    status = Column(String(32), nullable=False, comment="运行状态：running/success/failed/partial")
    # 开始时间
    started_at = Column(DateTime, nullable=False, comment="开始时间")
    # 结束时间
    finished_at = Column(DateTime, nullable=True, comment="结束时间")
    # 耗时（秒）
    duration_seconds = Column(Integer, default=0, nullable=False, comment="耗时(秒)")
    # 总处理订单数
    total_orders = Column(Integer, default=0, nullable=False, comment="总处理订单数")
    # 成功数
    success_count = Column(Integer, default=0, nullable=False, comment="成功数")
    # 失败数
    failed_count = Column(Integer, default=0, nullable=False, comment="失败数")
    # 跳过数
    skipped_count = Column(Integer, default=0, nullable=False, comment="跳过数")
    # 错误信息（失败时记录）
    error_message = Column(Text, default="", comment="错误信息")
    # 详细结果JSON（记录每个订单的处理结果摘要）
    detail_json = Column(Text, default="", comment="详细结果JSON")