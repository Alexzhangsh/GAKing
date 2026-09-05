# @ai-generated
"""
B08-1 用户佣金资产账户模块：新建资金流水记录表

迁移内容：
1. 新建资金流水记录表 gaking_fund_flow
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gaking_fund_flow",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("flow_type", sa.String(32), nullable=False, comment="流水类型：DEPOSIT/DEDUCT/FREEZE/UNFREEZE/WITHDRAW_APPLY/WITHDRAW_REJECT/WITHDRAW_SUCCESS/REFUND_DEDUCT/MANUAL_ADJUST/SETTLEMENT"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="变动金额(元)"),
        sa.Column("before_balance", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="变动前可用余额(元)"),
        sa.Column("after_balance", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="变动后可用余额(元)"),
        sa.Column("before_frozen", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="变动前冻结余额(元)"),
        sa.Column("after_frozen", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="变动后冻结余额(元)"),
        sa.Column("order_id", sa.BigInteger(), nullable=True, default=None, comment="关联订单ID"),
        sa.Column("withdraw_apply_id", sa.BigInteger(), nullable=True, default=None, comment="关联提现申请ID"),
        sa.Column("biz_id", sa.String(64), nullable=False, comment="业务流水号(唯一)"),
        sa.Column("remark", sa.String(512), server_default="", comment="备注"),
        sa.Column("operator_id", sa.BigInteger(), nullable=False, server_default="0", comment="操作人ID"),
        sa.Column("operator_name", sa.String(64), server_default="", comment="操作人姓名"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default="0", comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
        sa.Index("idx_user_id", "user_id"),
        sa.Index("idx_flow_type", "flow_type"),
        sa.Index("idx_create_time", "create_time"),
        sa.Index("idx_biz_id", "biz_id", unique=True),
        sa.Index("idx_user_type_time", "user_id", "flow_type", "create_time"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="资金流水记录表",
    )


def downgrade():
    op.drop_table("gaking_fund_flow")