# @ai-generated
"""add withdraw fee config columns to gaking_pay_config

Revision ID: 0003_add_withdraw_fee_config
Revises: 0002_add_user_commission_withdraw
Create Date: 2026-08-01

为 gaking_pay_config 表新增 2 个提现手续费动态配置列：
  - withdraw_rate      Numeric(5,4)  提现费率(0~1)，如 0.001 = 0.1%；空值兜底 constants.WITHDRAW_FEE_RATE
  - withdraw_min_fee   Numeric(10,2) 单笔最低手续费(元)，如 1.00；空值兜底 constants.WITHDRAW_FEE_MIN
均为 nullable，未配置时由 PayConfigUtil 兜底使用 constants 常量，保证降级可用。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_add_withdraw_fee_config"
down_revision = "0002_add_user_commission_withdraw"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """gaking_pay_config 新增 withdraw_rate / withdraw_min_fee 两列"""
    op.add_column(
        "gaking_pay_config",
        sa.Column(
            "withdraw_rate",
            sa.Numeric(precision=5, scale=4),
            nullable=True,
            comment="提现费率(0~1)，如0.001=0.1%；空值兜底常量",
        ),
    )
    op.add_column(
        "gaking_pay_config",
        sa.Column(
            "withdraw_min_fee",
            sa.Numeric(precision=10, scale=2),
            nullable=True,
            comment="单笔最低手续费(元)，如1.00；空值兜底常量",
        ),
    )


def downgrade() -> None:
    """回滚：移除 withdraw_rate / withdraw_min_fee 两列"""
    op.drop_column("gaking_pay_config", "withdraw_min_fee")
    op.drop_column("gaking_pay_config", "withdraw_rate")
