# @ai-generated
"""add user commission account and withdraw apply tables

新增 2 张用户佣金提现业务表：
- user_commission_account  用户佣金账户表（可用/冻结/累计佣金/累计提现/累计手续费）
- user_withdraw_apply      用户提现申请表（5 态状态机）

执行方式：
  alembic upgrade head     # 建表
  alembic downgrade -1     # 回滚删除表

Revision ID: 0002_add_user_commission_withdraw
Revises: 0001_init_tables
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_add_user_commission_withdraw"
down_revision: Union[str, None] = "0001_init_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 2 张用户佣金提现业务表 + 索引"""

    # ============================================================
    # 1. user_commission_account 用户佣金账户表
    # ============================================================
    op.create_table(
        "user_commission_account",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="平台用户ID"),
        sa.Column("total_balance", sa.Numeric(precision=10, scale=2), nullable=False, comment="累计已结算佣金(元)"),
        sa.Column("available_balance", sa.Numeric(precision=10, scale=2), nullable=False, comment="可用余额(元)，可提现"),
        sa.Column("frozen_balance", sa.Numeric(precision=10, scale=2), nullable=False, comment="冻结余额(元)，待审核提现锁定"),
        sa.Column("cumulative_withdrawn", sa.Numeric(precision=10, scale=2), nullable=False, comment="累计成功提现金额(元，实际到账)"),
        sa.Column("cumulative_fee", sa.Numeric(precision=10, scale=2), nullable=False, comment="累计手续费(元)"),
        sa.Column("last_settle_date", sa.Date(), nullable=True, comment="最近一次对账入账日期（幂等防重复入账）"),
        sa.Column("version", sa.Integer(), nullable=False, comment="乐观锁版本号（余额变更递增）"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uk_user_id"),
        comment="用户佣金账户表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # user_commission_account 索引
    op.create_index("idx_user_id", "user_commission_account", ["user_id"])

    # ============================================================
    # 2. user_withdraw_apply 用户提现申请表
    # ============================================================
    op.create_table(
        "user_withdraw_apply",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("apply_no", sa.String(length=64), nullable=False, comment="提现单号（GAKW前缀+时间+随机，全局唯一）"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="平台用户ID"),
        sa.Column("apply_amount", sa.Numeric(precision=10, scale=2), nullable=False, comment="申请提现金额(元)"),
        sa.Column("fee", sa.Numeric(precision=10, scale=2), nullable=False, comment="手续费(元)"),
        sa.Column("actual_amount", sa.Numeric(precision=10, scale=2), nullable=False, comment="实际到账金额(元)=apply_amount-fee"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="状态：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED"),
        sa.Column("review_user_id", sa.BigInteger(), nullable=True, comment="审核人ID（后台管理员）"),
        sa.Column("review_remark", sa.String(length=512), nullable=True, comment="审核备注"),
        sa.Column("review_time", sa.DateTime(), nullable=True, comment="审核时间"),
        sa.Column("transfer_batch_id", sa.String(length=64), nullable=True, comment="微信转账批次ID"),
        sa.Column("transfer_time", sa.DateTime(), nullable=True, comment="打款完成时间"),
        sa.Column("reject_reason", sa.String(length=512), nullable=True, comment="驳回原因（含打款失败原因）"),
        sa.Column("remark", sa.String(length=512), nullable=True, comment="备注"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("apply_no", name="uk_apply_no"),
        comment="用户提现申请表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # user_withdraw_apply 索引
    op.create_index("idx_user_id", "user_withdraw_apply", ["user_id"])
    op.create_index("idx_status", "user_withdraw_apply", ["status"])
    op.create_index("idx_create_time", "user_withdraw_apply", ["create_time"])
    op.create_index("idx_user_status", "user_withdraw_apply", ["user_id", "status"])


def downgrade() -> None:
    """回滚：删除 2 张表（drop_table 自动级联删除索引）"""
    op.drop_table("user_withdraw_apply")
    op.drop_table("user_commission_account")
