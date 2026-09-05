# @ai-generated
"""
0015 - add scheduled_task_run_log table (B05-7)

Revision ID: 0015
Revises: 0014_add_order_refund_operation_log
Create Date: 2026-08-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014_add_order_refund_operation_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_task_run_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_name", sa.String(128), nullable=False, comment="任务名称"),
        sa.Column("run_id", sa.String(64), nullable=False, comment="运行批次ID"),
        sa.Column("status", sa.String(32), nullable=False, comment="运行状态：running/success/failed/partial"),
        sa.Column("started_at", sa.DateTime(), nullable=False, comment="开始时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="结束时间"),
        sa.Column("duration_seconds", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="耗时(秒)"),
        sa.Column("total_orders", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="总处理订单数"),
        sa.Column("success_count", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="成功数"),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="失败数"),
        sa.Column("skipped_count", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="跳过数"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息（MySQL 8.0.13+ TEXT 禁止默认值，置 NULL 代替）"),
        sa.Column("detail_json", sa.Text(), nullable=True, comment="详细结果JSON（MySQL 8.0.13+ TEXT 禁止默认值，置 NULL 代替）"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False, comment="更新时间"),
        sa.Column("is_delete", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False, comment="软删除标记"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
        mysql_comment="定时任务运行日志表（B05-7）",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_strl_task_name", "scheduled_task_run_log", ["task_name"])
    op.create_index("idx_strl_status", "scheduled_task_run_log", ["status"])
    op.create_index("idx_strl_started_at", "scheduled_task_run_log", ["started_at"])
    op.create_index("idx_strl_task_status", "scheduled_task_run_log", ["task_name", "status"])


def downgrade() -> None:
    op.drop_index("idx_strl_task_status", table_name="scheduled_task_run_log")
    op.drop_index("idx_strl_started_at", table_name="scheduled_task_run_log")
    op.drop_index("idx_strl_status", table_name="scheduled_task_run_log")
    op.drop_index("idx_strl_task_name", table_name="scheduled_task_run_log")
    op.drop_table("scheduled_task_run_log")