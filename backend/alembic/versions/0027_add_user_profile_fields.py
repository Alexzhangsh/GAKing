# @ai-generated
"""
0027 - add user profile fields to miniapp_user

为 miniapp_user 表新增提款报税所需个人资料字段：
- phone          手机号
- real_name      真实姓名
- id_card        身份证号
- bank_card      银行卡号
- bank_name      发卡银行（BIN自动识别）
- bank_branch    开户支行（用户手动输入）

幂等：仅当列不存在时添加，避免重复执行报错。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers
revision = "0027"
down_revision = "0026"
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


def _ensure_miniapp_user_table() -> None:
    """全新库兼容：miniapp_user 表由应用启动 create_all 创建，迁移链中无建表迁移；
    全新库升级到本迁移时幂等预建（已存在则跳过）。生产库已应用，不受影响。
    （2026-09-05 发布测试发现：全新库从零 upgrade head 因缺表失败）"""
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table(TABLE_NAME):
        return
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="平台用户ID（全局唯一）"),
        sa.Column("openid", sa.String(64), nullable=False, comment="微信小程序openid"),
        sa.Column("unionid", sa.String(64), nullable=False, server_default="", comment="微信unionid（可为空）"),
        sa.Column("nickname", sa.String(64), nullable=False, server_default="微信用户", comment="用户昵称"),
        sa.Column("avatar", sa.String(512), nullable=False, server_default="", comment="头像URL"),
        sa.Column("session_key", sa.String(128), nullable=False, server_default="", comment="微信会话密钥"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="0", comment="账号状态：0-正常 1-禁用"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default="0", comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.Index("idx_openid", "openid", unique=True),
        sa.Index("idx_user_id", "user_id", unique=True),
        comment="小程序C端用户表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def upgrade() -> None:
    # 全新库兼容：预建 miniapp_user（幂等）
    _ensure_miniapp_user_table()
    for col in NEW_COLUMNS:
        if not _column_exists(TABLE_NAME, col.name):
            op.add_column(TABLE_NAME, col)
            print(f"[0027] 已添加列 {TABLE_NAME}.{col.name}")
        else:
            print(f"[0027] 列已存在，跳过 {TABLE_NAME}.{col.name}")


def downgrade() -> None:
    for col in reversed(NEW_COLUMNS):
        if _column_exists(TABLE_NAME, col.name):
            op.drop_column(TABLE_NAME, col.name)
            print(f"[0027] 已删除列 {TABLE_NAME}.{col.name}")
