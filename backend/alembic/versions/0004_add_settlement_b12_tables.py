# @ai-generated
"""add settlement record and operation log tables (B12)

新增 2 张佣金结算状态机业务表（B12）：
- settlement_record          佣金结算单表（4 态状态机：ORDERED→SETTLABLE→SETTLED→PAID）
- settlement_operation_log   佣金结算操作日志表（记录每次状态变更，供后台审计追溯）

执行方式：
  alembic upgrade head     # 建表
  alembic downgrade -1     # 回滚删除表

Revision ID: 0004_add_settlement_b12_tables
Revises: 0003_add_withdraw_fee_config
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_add_settlement_b12_tables"
down_revision: Union[str, None] = "0003_add_withdraw_fee_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 2 张 B12 佣金结算状态机业务表 + 索引"""

    # ============================================================
    # 1. settlement_record 佣金结算单表
    # ============================================================
    op.create_table(
        "settlement_record",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "settlement_no",
            sa.String(length=64),
            nullable=False,
            comment="平台结算单号",
        ),
        sa.Column("order_id", sa.BigInteger(), nullable=False, comment="关联订单ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column(
            "channel_code", sa.String(length=32), nullable=False, comment="渠道标识"
        ),
        sa.Column(
            "total_commission",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="总佣金(元)",
        ),
        sa.Column(
            "user_commission",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="用户佣金(元)",
        ),
        sa.Column(
            "platform_commission",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="平台佣金(元)",
        ),
        sa.Column(
            "settlement_status",
            sa.String(length=32),
            nullable=False,
            comment="结算单状态：ORDERED/SETTLABLE/SETTLED/PAID",
        ),
        sa.Column("flow_id", sa.BigInteger(), nullable=True, comment="关联佣金流水ID"),
        sa.Column("confirm_time", sa.DateTime(), nullable=True, comment="确认收货时间"),
        sa.Column(
            "settle_time", sa.DateTime(), nullable=True, comment="渠道结算到账时间"
        ),
        sa.Column("paid_time", sa.DateTime(), nullable=True, comment="提现打款时间"),
        sa.Column(
            "delay_days", sa.Integer(), nullable=False, comment="延迟结算天数快照"
        ),
        sa.Column("remark", sa.String(length=512), nullable=True, comment="备注说明"),
        sa.Column(
            "is_delete",
            sa.Boolean(),
            nullable=False,
            comment="软删除：0-未删除 1-已删除",
        ),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="佣金结算单表（B12）",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # settlement_record 索引
    op.create_index(
        "idx_settlement_no", "settlement_record", ["settlement_no"], unique=True
    )
    op.create_index("idx_sr_order_id", "settlement_record", ["order_id"])
    op.create_index("idx_sr_user_id", "settlement_record", ["user_id"])
    op.create_index("idx_sr_status", "settlement_record", ["settlement_status"])
    op.create_index("idx_sr_create_time", "settlement_record", ["create_time"])

    # ============================================================
    # 2. settlement_operation_log 佣金结算操作日志表
    # ============================================================
    op.create_table(
        "settlement_operation_log",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "settlement_id", sa.BigInteger(), nullable=False, comment="关联结算单ID"
        ),
        sa.Column("order_id", sa.BigInteger(), nullable=False, comment="关联订单ID"),
        sa.Column(
            "from_status", sa.String(length=32), nullable=False, comment="变更前状态"
        ),
        sa.Column(
            "to_status", sa.String(length=32), nullable=False, comment="变更后状态"
        ),
        sa.Column(
            "action",
            sa.String(length=32),
            nullable=False,
            comment="操作类型：CREATE_SETTLEMENT/FREEZE/UNFREEZE/MARK_PAID",
        ),
        sa.Column("operator_id", sa.BigInteger(), nullable=True, comment="操作人ID"),
        sa.Column(
            "amount",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="涉及金额(元)",
        ),
        sa.Column("flow_id", sa.BigInteger(), nullable=True, comment="关联佣金流水ID"),
        sa.Column("remark", sa.Text(), nullable=True, comment="操作备注"),
        sa.Column(
            "is_delete",
            sa.Boolean(),
            nullable=False,
            comment="软删除：0-未删除 1-已删除",
        ),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="佣金结算操作日志表（B12）",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # settlement_operation_log 索引
    op.create_index(
        "idx_sol_settlement_id", "settlement_operation_log", ["settlement_id"]
    )
    op.create_index("idx_sol_order_id", "settlement_operation_log", ["order_id"])
    op.create_index("idx_sol_action", "settlement_operation_log", ["action"])
    op.create_index("idx_sol_create_time", "settlement_operation_log", ["create_time"])


def downgrade() -> None:
    """回滚：删除 2 张 B12 业务表"""
    op.drop_table("settlement_operation_log")
    op.drop_table("settlement_record")
