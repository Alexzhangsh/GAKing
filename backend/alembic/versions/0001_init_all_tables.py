# @ai-generated
"""init all system & business tables

创建 6 张核心业务表：
- gaking_system_config  全局系统配置表
- gaking_cloud_config   OBS/CDN云资源配置表
- gaking_pay_config     微信V3支付配置表
- gaking_channel_mapping CPS渠道配置表
- orders                导购订单主表
- commission_flow       佣金发放流水明细表

执行方式：
  alembic upgrade head     # 建表
  alembic downgrade -1     # 回滚删除表

Revision ID: 0001_init_tables
Revises:
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_init_tables"
down_revision: Union[str, None] = "0000_ensure_runtime_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 6 张核心业务表、所有索引、外键约束"""

    # ============================================================
    # 1. gaking_system_config 全局系统配置表
    # ============================================================
    op.create_table(
        "gaking_system_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("config_key", sa.String(length=64), nullable=False, comment="配置唯一键名"),
        sa.Column("config_value", sa.Text(), nullable=False, comment="配置值，支持文本、数字、JSON"),
        sa.Column("config_name", sa.String(length=128), nullable=False, comment="配置中文名称"),
        sa.Column("remark", sa.String(length=512), nullable=True, comment="配置说明备注"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("config_key", name="uk_config_key"),
        comment="系统全局配置表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ============================================================
    # 2. gaking_cloud_config OBS/CDN云资源配置表
    # ============================================================
    op.create_table(
        "gaking_cloud_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("config_name", sa.String(length=128), nullable=False, comment="配置名称"),
        sa.Column("obs_bucket", sa.String(length=128), nullable=True, comment="华为OBS桶名"),
        sa.Column("obs_endpoint", sa.String(length=256), nullable=True, comment="OBS终端地址"),
        sa.Column("access_key", sa.String(length=256), nullable=True, comment="云存储AK密钥"),
        sa.Column("secret_key", sa.String(length=256), nullable=True, comment="云存储SK密钥"),
        sa.Column("cdn_domain", sa.String(length=256), nullable=True, comment="CDN根域名"),
        sa.Column("status", sa.Boolean(), nullable=False, comment="状态：0-禁用 1-启用"),
        sa.Column("remark", sa.String(length=512), nullable=True, comment="备注说明"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("config_name", name="uk_config_name"),
        comment="云资源CDN配置表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ============================================================
    # 3. gaking_pay_config 微信V3支付配置表
    # ============================================================
    op.create_table(
        "gaking_pay_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("mch_id", sa.String(length=64), nullable=False, comment="微信商户号"),
        sa.Column("serial_no", sa.String(length=128), nullable=True, comment="商户证书序列号"),
        sa.Column("private_key_path", sa.String(length=256), nullable=True, comment="商户私钥文件路径"),
        sa.Column("v3_secret", sa.String(length=128), nullable=True, comment="APIv3密钥，用于回调解密"),
        sa.Column("transfer_scene_id", sa.String(length=64), nullable=True, comment="微信转账场景ID"),
        sa.Column("notify_url", sa.String(length=256), nullable=True, comment="支付回调地址"),
        sa.Column("status", sa.Boolean(), nullable=False, comment="状态：0-禁用 1-启用"),
        sa.Column("remark", sa.String(length=512), nullable=True, comment="备注说明"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="微信V3支付配置表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ============================================================
    # 4. gaking_channel_mapping CPS渠道配置表
    # ============================================================
    op.create_table(
        "gaking_channel_mapping",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("channel_code", sa.String(length=32), nullable=False, comment="渠道标识：myq-喵有券 / orderx-订单侠"),
        sa.Column("channel_name", sa.String(length=64), nullable=True, comment="渠道中文名称"),
        sa.Column("api_token", sa.String(length=256), nullable=True, comment="渠道API Token"),
        sa.Column("api_secret", sa.String(length=256), nullable=True, comment="渠道API密钥，用于签名校验"),
        sa.Column("pid", sa.String(length=64), nullable=True, comment="渠道推广位PID"),
        sa.Column("settle_rate", sa.Numeric(precision=5, scale=4), nullable=False, comment="结算比例(0~1)，如0.80"),
        sa.Column("status", sa.Boolean(), nullable=False, comment="状态：0-禁用 1-启用"),
        sa.Column("remark", sa.String(length=512), nullable=True, comment="备注说明"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_code", name="uk_channel_code"),
        comment="CPS渠道配置表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ============================================================
    # 5. orders 导购订单主表
    # ============================================================
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("out_order_no", sa.String(length=64), nullable=False, comment="渠道订单号"),
        sa.Column("internal_order_no", sa.String(length=64), nullable=False, comment="平台内部订单号"),
        sa.Column("goods_title", sa.String(length=256), nullable=True, comment="商品标题"),
        sa.Column("goods_img", sa.String(length=512), nullable=True, comment="商品主图URL"),
        sa.Column("pay_amount", sa.Numeric(precision=10, scale=2), nullable=False, comment="支付金额(元)"),
        sa.Column("total_commission", sa.Numeric(precision=10, scale=2), nullable=False, comment="总佣金(元)"),
        sa.Column("user_commission", sa.Numeric(precision=10, scale=2), nullable=False, comment="用户佣金(元)"),
        sa.Column("platform_commission", sa.Numeric(precision=10, scale=2), nullable=False, comment="平台佣金(元)"),
        sa.Column("channel_code", sa.String(length=32), nullable=True, comment="渠道标识：myq/orderx"),
        sa.Column("order_status", sa.Integer(), nullable=False, comment="订单状态：10-待付款 30-已付款 40-已结算 50-失效"),
        sa.Column("pay_time", sa.DateTime(), nullable=True, comment="支付时间"),
        sa.Column("settle_time", sa.DateTime(), nullable=True, comment="结算时间"),
        sa.Column("wx_batch_id", sa.String(length=64), nullable=True, comment="微信转账批次ID"),
        sa.Column("transfer_status", sa.String(length=32), nullable=False, comment="转账状态：PENDING/PROCESSING/SUCCESS/FAILED"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="导购订单主表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # orders 索引
    op.create_index("idx_user_id", "orders", ["user_id"])
    op.create_index("idx_out_order_no", "orders", ["out_order_no"], unique=True)
    op.create_index("idx_internal_order_no", "orders", ["internal_order_no"], unique=True)
    op.create_index("idx_create_time", "orders", ["create_time"])
    op.create_index("idx_order_status", "orders", ["order_status"])
    op.create_index("idx_user_status", "orders", ["user_id", "order_status"])

    # ============================================================
    # 6. commission_flow 佣金发放流水明细表
    # ============================================================
    op.create_table(
        "commission_flow",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("order_id", sa.BigInteger(), nullable=True, comment="关联订单ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("flow_type", sa.String(length=32), nullable=False, comment="流水类型：ORDER-订单佣金/SUPPLEMENT-补发/DEDUCT-扣减"),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False, comment="流水金额(元)"),
        sa.Column("before_balance", sa.Numeric(precision=10, scale=2), nullable=False, comment="变更前余额(元)"),
        sa.Column("after_balance", sa.Numeric(precision=10, scale=2), nullable=False, comment="变更后余额(元)"),
        sa.Column("transfer_batch_id", sa.String(length=64), nullable=True, comment="微信转账批次ID"),
        sa.Column("transfer_status", sa.String(length=32), nullable=False, comment="转账状态：PENDING/PROCESSING/SUCCESS/FAILED"),
        sa.Column("remark", sa.String(length=512), nullable=True, comment="备注说明"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="佣金发放流水明细表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # commission_flow 索引
    op.create_index("idx_order_id", "commission_flow", ["order_id"])
    op.create_index("idx_user_id", "commission_flow", ["user_id"])
    op.create_index("idx_create_time", "commission_flow", ["create_time"])
    op.create_index("idx_user_flow_type", "commission_flow", ["user_id", "flow_type"])


def downgrade() -> None:
    """回滚：删除 6 张表（按依赖反序删除，drop_table 自动级联删除索引）"""
    # 先删 commission_flow（有外键依赖 orders）
    op.drop_table("commission_flow")
    # 再删 orders
    op.drop_table("orders")
    # 删 4 张系统配置表
    op.drop_table("gaking_channel_mapping")
    op.drop_table("gaking_pay_config")
    op.drop_table("gaking_cloud_config")
    op.drop_table("gaking_system_config")
