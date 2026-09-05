# @ai-generated
"""add abnormal_order_operation_log table (B05-4-3)

B05-4-3 订单归属操作日志：
- 新建 abnormal_order_operation_log 表，记录异常订单每次人工修改归属、备注、操作人员、变更前后参数

执行方式：
  alembic upgrade head     # 新建表
  alembic downgrade -1     # 回滚删除表

Revision ID: 0012_add_abnormal_order_operation_log
Revises: 0011_add_assigned_user_id_to_abnormal_order
Create Date: 2026-08-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_add_abnormal_order_operation_log"
down_revision: Union[str, None] = "0011_add_assigned_user_id_to_abnormal_order"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新建 abnormal_order_operation_log 表"""
    op.create_table(
        "abnormal_order_operation_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("abnormal_order_id", sa.BigInteger(), nullable=False, comment="异常订单ID"),
        sa.Column("operator_id", sa.BigInteger(), nullable=False, comment="操作人管理员ID"),
        sa.Column("operation_type", sa.String(32), nullable=False, comment="操作类型：REVIEW-复核 / EDIT-编辑"),
        sa.Column("old_assigned_user_id", sa.BigInteger(), server_default="0", nullable=False, comment="变更前归属用户ID"),
        sa.Column("new_assigned_user_id", sa.BigInteger(), server_default="0", nullable=False, comment="变更后归属用户ID"),
        sa.Column("old_review_remark", sa.String(512), server_default="", nullable=False, comment="变更前复核备注"),
        sa.Column("new_review_remark", sa.String(512), server_default="", nullable=False, comment="变更后复核备注"),
        sa.Column("old_review_status", sa.String(32), server_default="", nullable=False, comment="变更前复核状态"),
        sa.Column("new_review_status", sa.String(32), server_default="", nullable=False, comment="变更后复核状态"),
        sa.Column("remark", sa.Text(), nullable=True, comment="操作补充说明（MySQL 8.0.13+ TEXT 禁止默认值，置 NULL 代替）"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_delete", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False, comment="软删除标记"),
        sa.PrimaryKeyConstraint("id"),
        mysql_comment="订单归属操作日志表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # 创建索引
    op.create_index("idx_ao_abnormal_order_id", "abnormal_order_operation_log", ["abnormal_order_id"])
    op.create_index("idx_ao_operation_type", "abnormal_order_operation_log", ["operation_type"])
    op.create_index("idx_ao_operator_id", "abnormal_order_operation_log", ["operator_id"])
    op.create_index("idx_ao_create_time", "abnormal_order_operation_log", ["created_at"])


def downgrade() -> None:
    """回滚删除 abnormal_order_operation_log 表"""
    op.drop_index("idx_ao_create_time", table_name="abnormal_order_operation_log")
    op.drop_index("idx_ao_operator_id", table_name="abnormal_order_operation_log")
    op.drop_index("idx_ao_operation_type", table_name="abnormal_order_operation_log")
    op.drop_index("idx_ao_abnormal_order_id", table_name="abnormal_order_operation_log")
    op.drop_table("abnormal_order_operation_log")