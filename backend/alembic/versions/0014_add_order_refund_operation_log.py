# @ai-generated
"""add order_refund_operation_log table (B05-6)

B05-6 退款操作日志：
- 新建 order_refund_operation_log 表，记录退款订单逆向冲减佣金的每次操作流水

执行方式：
  alembic upgrade head     # 新建表
  alembic downgrade -1     # 回滚删除表

Revision ID: 0014_add_order_refund_operation_log
Revises: 0013_add_commission_flow_validation_log
Create Date: 2026-08-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_add_order_refund_operation_log"
down_revision: Union[str, None] = "0013_add_commission_flow_validation_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新建 order_refund_operation_log 表"""
    op.create_table(
        "order_refund_operation_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False, comment="关联订单ID"),
        sa.Column("operator_id", sa.BigInteger(), nullable=False, comment="操作人管理员ID"),
        sa.Column("operation_type", sa.String(32), nullable=False, comment="操作类型：DEDUCT-退款冲减"),
        sa.Column("order_status_before", sa.Integer(), nullable=False, comment="变更前订单状态"),
        sa.Column("order_status_after", sa.Integer(), nullable=False, comment="变更后订单状态"),
        sa.Column("deduct_amount", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False, comment="扣减金额(元)"),
        sa.Column("flow_type", sa.String(32), server_default="", nullable=False, comment="原始流水类型：ORDER/SUPPLEMENT"),
        sa.Column("flow_transfer_status", sa.String(32), server_default="", nullable=False, comment="原始流水转账状态：PENDING/SUCCESS"),
        sa.Column("old_available_balance", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False, comment="变更前可用余额(元)"),
        sa.Column("new_available_balance", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False, comment="变更后可用余额(元)"),
        sa.Column("old_total_balance", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False, comment="变更前累计佣金(元)"),
        sa.Column("new_total_balance", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False, comment="变更后累计佣金(元)"),
        sa.Column("deduct_flow_id", sa.BigInteger(), nullable=True, comment="关联扣减流水ID(commission_flow.id)"),
        sa.Column("remark", sa.Text(), nullable=True, comment="备注说明（MySQL 8.0.13+ TEXT 禁止默认值，置 NULL 代替）"),
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
        mysql_comment="退款操作日志表（B05-6）",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # 创建索引
    op.create_index("idx_rol_order_id", "order_refund_operation_log", ["order_id"])
    op.create_index("idx_rol_operator_id", "order_refund_operation_log", ["operator_id"])
    op.create_index("idx_rol_operation_type", "order_refund_operation_log", ["operation_type"])
    op.create_index("idx_rol_create_time", "order_refund_operation_log", ["created_at"])


def downgrade() -> None:
    """回滚删除 order_refund_operation_log 表"""
    op.drop_index("idx_rol_create_time", table_name="order_refund_operation_log")
    op.drop_index("idx_rol_operation_type", table_name="order_refund_operation_log")
    op.drop_index("idx_rol_operator_id", table_name="order_refund_operation_log")
    op.drop_index("idx_rol_order_id", table_name="order_refund_operation_log")
    op.drop_table("order_refund_operation_log")