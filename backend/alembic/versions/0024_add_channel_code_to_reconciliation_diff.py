# @ai-generated
"""
0024 - add channel_code to reconciliation_diff

B17 多渠道对账差异处理：reconciliation_diff 表新增 channel_code 列，
用于标识渠道对账差异所属渠道（myq/orderx），支持按渠道筛选差异。

幂等：仅当列不存在时新增，避免重复执行报错。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers
revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("reconciliation_diff")}
    if "channel_code" not in cols:
        op.add_column(
            "reconciliation_diff",
            sa.Column(
                "channel_code",
                sa.String(length=32),
                nullable=True,
                comment="渠道标识：myq/orderx",
            ),
        )
        op.create_index(
            "idx_rd_channel_code", "reconciliation_diff", ["channel_code"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("reconciliation_diff")}
    if "channel_code" in cols:
        op.drop_index("idx_rd_channel_code", table_name="reconciliation_diff")
        op.drop_column("reconciliation_diff", "channel_code")
