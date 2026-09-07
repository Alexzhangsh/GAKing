# @ai-generated
"""
0029 - repair miniapp_user profile columns (S17-1)

生产事故修复（2026-09-07 体验版登录 500）：
0027 迁移在生产库被"版本号跳过"（文件事后修改不重放），导致
miniapp_user 表缺少 0027 声明的 6 列，wx-login 查询全列报
1054 Unknown column 'miniapp_user.phone'。

本迁移幂等补齐：
- phone          手机号
- real_name      真实姓名
- id_card        身份证号
- bank_card      银行卡号
- bank_name      发卡银行
- bank_branch    开户支行

幂等：仅当列不存在时添加；全新库（0000 create_all 已含这些列）直接跳过。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers
revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

TABLE_NAME = "miniapp_user"

NEW_COLUMNS = [
    sa.Column("phone", sa.String(20), nullable=False, server_default="", comment="手机号"),
    sa.Column("real_name", sa.String(64), nullable=False, server_default="", comment="真实姓名"),
    sa.Column("id_card", sa.String(32), nullable=False, server_default="", comment="身份证号"),
    sa.Column("bank_card", sa.String(32), nullable=False, server_default="", comment="银行卡号"),
    sa.Column("bank_name", sa.String(64), nullable=False, server_default="", comment="发卡银行（BIN自动识别）"),
    sa.Column("bank_branch", sa.String(128), nullable=False, server_default="", comment="开户支行（用户手动输入）"),
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
            print(f"[0029] 已补列 {TABLE_NAME}.{col.name}")
        else:
            print(f"[0029] 列已存在，跳过 {TABLE_NAME}.{col.name}")


def downgrade() -> None:
    for col in reversed(NEW_COLUMNS):
        if _column_exists(TABLE_NAME, col.name):
            op.drop_column(TABLE_NAME, col.name)
            print(f"[0029] 已删除列 {TABLE_NAME}.{col.name}")
