# @ai-generated
"""
0028 - add price & bonus fields to goods_management

为 goods_management 表新增商品价格与会员奖金字段：
- original_price       商品原价(元)
- bonus_price_normal   普通会员奖金(元)
- bonus_rate_normal    普通会员奖金比例(%)
- bonus_price_vip      VIP会员奖金(元)
- bonus_rate_vip       VIP会员奖金比例(%)

幂等：仅当列不存在时添加，避免重复执行报错。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers
revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

TABLE_NAME = "goods_management"

NEW_COLUMNS = [
    sa.Column("original_price", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="商品原价(元)"),
    sa.Column("bonus_price_normal", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="普通会员奖金(元)"),
    sa.Column("bonus_rate_normal", sa.Numeric(5, 2), nullable=False, server_default="0.00", comment="普通会员奖金比例(%)"),
    sa.Column("bonus_price_vip", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="VIP会员奖金(元)"),
    sa.Column("bonus_rate_vip", sa.Numeric(5, 2), nullable=False, server_default="0.00", comment="VIP会员奖金比例(%)"),
]


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    if table_name not in insp.get_table_names():
        return False
    cols = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    for col in NEW_COLUMNS:
        if not _column_exists(TABLE_NAME, col.name):
            op.add_column(TABLE_NAME, col)
            print(f"[0028] 已添加列 {TABLE_NAME}.{col.name}")
        else:
            print(f"[0028] 列已存在，跳过 {TABLE_NAME}.{col.name}")


def downgrade() -> None:
    for col in reversed(NEW_COLUMNS):
        if _column_exists(TABLE_NAME, col.name):
            op.drop_column(TABLE_NAME, col.name)
            print(f"[0028] 已删除列 {TABLE_NAME}.{col.name}")
