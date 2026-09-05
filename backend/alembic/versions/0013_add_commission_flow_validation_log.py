# @ai-generated
"""add commission_flow_validation_log table (B05-5)

B05-5 佣金流水结算前置校验：
- 新建 commission_flow_validation_log 表，记录佣金流水生成前的每项校验结果

执行方式：
  alembic upgrade head     # 新建表
  alembic downgrade -1     # 回滚删除表

Revision ID: 0013_add_commission_flow_validation_log
Revises: 0012_add_abnormal_order_operation_log
Create Date: 2026-08-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_add_commission_flow_validation_log"
down_revision: Union[str, None] = "0012_add_abnormal_order_operation_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新建 commission_flow_validation_log 表"""
    op.create_table(
        "commission_flow_validation_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False, comment="关联订单ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("validation_type", sa.String(32), nullable=False, comment="校验类型：PRE_SETTLE-结算前置校验/PRE_DEDUCT-扣减前置校验"),
        sa.Column("validation_result", sa.String(32), nullable=False, comment="校验结果：PASS-通过/FAIL-失败"),
        sa.Column("check_items", sa.Text(), nullable=False, comment="各项校验明细JSON"),
        sa.Column("error_message", sa.String(1024), server_default="", nullable=False, comment="总体错误信息"),
        sa.Column("operator_id", sa.BigInteger(), server_default="0", nullable=False, comment="操作人管理员ID（0=系统自动）"),
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
        mysql_comment="佣金流水结算前置校验日志表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # 创建索引
    op.create_index("idx_cfvl_order_id", "commission_flow_validation_log", ["order_id"])
    op.create_index("idx_cfvl_user_id", "commission_flow_validation_log", ["user_id"])
    op.create_index("idx_cfvl_validation_result", "commission_flow_validation_log", ["validation_result"])
    op.create_index("idx_cfvl_create_time", "commission_flow_validation_log", ["created_at"])


def downgrade() -> None:
    """回滚删除 commission_flow_validation_log 表"""
    op.drop_index("idx_cfvl_create_time", table_name="commission_flow_validation_log")
    op.drop_index("idx_cfvl_validation_result", table_name="commission_flow_validation_log")
    op.drop_index("idx_cfvl_user_id", table_name="commission_flow_validation_log")
    op.drop_index("idx_cfvl_order_id", table_name="commission_flow_validation_log")
    op.drop_table("commission_flow_validation_log")