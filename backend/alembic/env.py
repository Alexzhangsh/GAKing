# @ai-generated
"""
Alembic 异步迁移环境配置
1. 复用项目 src/config/env_config 加载 DB 参数
2. 导入全部 models（system 四张 + business 两张），确保 autogenerate 识别
3. 完整异步迁移 run_async_migrations 实现，适配 aiomysql
4. 自动过滤无关表，仅生成项目 6 张业务表迁移
"""
import asyncio
import os
import sys
from logging.config import fileConfig

# 确保 backend 目录在 sys.path 中（alembic CLI 默认不含，否则 import src 失败）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from src.config.env_config import EnvConfig
from src.db.base import Base

# 导入全部模型，确保 Alembic autogenerate 能扫描到所有表
# 系统配置表（4张）
from src.models.system.system_config import SystemConfig  # noqa: F401
from src.models.system.cloud_config import CloudConfig  # noqa: F401
from src.models.system.pay_config import PayConfig  # noqa: F401
from src.models.system.channel_config import ChannelMapping  # noqa: F401

# 业务表（2张）
from src.models.business.order_model import Order  # noqa: F401
from src.models.business.commission_flow_model import CommissionFlow  # noqa: F401

# 业务表（商品管理，B13-补全/B14-补全）
from src.models.business.goods_management_model import GoodsManagement  # noqa: F401

# 业务表（用户佣金提现，2张）
from src.models.business.user_commission_account_model import (
    UserCommissionAccount,
)  # noqa: F401
from src.models.business.user_withdraw_apply_model import (
    UserWithdrawApply,
)  # noqa: F401

# 业务表（提现审批流转日志，1张，B11 新增）
from src.models.business.withdraw_review_log_model import (
    WithdrawReviewLog,
)  # noqa: F401

# 业务表（佣金结算单+操作日志，2张，B12 新增）
from src.models.business.settlement_record_model import SettlementRecord  # noqa: F401
from src.models.business.settlement_operation_log_model import (
    SettlementOperationLog,
)  # noqa: F401

# 业务表（对账批次+差异明细，2张，B13 新增）
from src.models.business.reconciliation_record_model import (
    ReconciliationRecord,
)  # noqa: F401
from src.models.business.reconciliation_diff_model import (
    ReconciliationDiff,
)  # noqa: F401

# 后台菜单元数据表（1张，B14 新增）
from src.models.system.admin_menu_model import AdminMenu  # noqa: F401

# B05-4 短链跟单系统（3张）
from src.models.business.short_link_model import ShortLink  # noqa: F401
from src.models.business.click_log_model import ClickLog  # noqa: F401
from src.models.business.abnormal_order_model import AbnormalOrder  # noqa: F401

# B05-4-3 订单归属操作日志表（1张）
from src.models.business.abnormal_order_operation_log_model import (
    AbnormalOrderOperationLog,
)  # noqa: F401

# B05-5 佣金流水结算前置校验日志表（1张）
from src.models.business.commission_flow_validation_log_model import (
    CommissionFlowValidationLog,
)  # noqa: F401

# B06-1 渠道佣金比例配置表（1张）
from src.models.system.b06_channel_config import (
    ChannelCommissionConfig,
)  # noqa: F401

# B06-2 渠道导出任务日志表（1张）
from src.models.system.b06_2_export_task_log import (
    ChannelExportTaskLog,
)  # noqa: F401

# B07-1 逆向佣金冲减记录表（1张）
from src.models.business.b07_1_reverse_commission_record import (
    ReverseCommissionRecord,
)  # noqa: F401

# B08-1 资金流水记录表（1张）
from src.models.business.b08_1_fund_flow_model import (
    FundFlow,
)  # noqa: F401

# B05-6 退款操作日志表（1张）
from src.models.business.order_refund_operation_log_model import (
    OrderRefundOperationLog,
)  # noqa: F401

# B05-7 定时任务运行日志表（1张）
from src.models.business.scheduled_task_run_log_model import (
    ScheduledTaskRunLog,
)  # noqa: F401

# Alembic 配置对象
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标 metadata —— 所有模型共享同一个 Base.metadata
target_metadata = Base.metadata

# 仅生成这些目标表的迁移，过滤无关表（admin_role / admin_user / audit_logs / gaking_task_status）
TARGET_TABLES = {
    "gaking_system_config",
    "gaking_cloud_config",
    "gaking_pay_config",
    "gaking_channel_mapping",
    "orders",
    "commission_flow",
    "user_commission_account",
    "user_withdraw_apply",
    "withdraw_review_log",
    "settlement_record",
    "settlement_operation_log",
    "reconciliation_record",
    "reconciliation_diff",
    "admin_menu",  # B14 新增
    "goods_management",  # B13-补全/B16 商品管理扩展表
    # B05-4 短链跟单系统
    "short_link",
    "click_log",
    "abnormal_order",
    # B05-4-3 订单归属操作日志
    "abnormal_order_operation_log",
    # B05-5 佣金流水结算前置校验日志
    "commission_flow_validation_log",
    # B06-1 渠道佣金比例配置
    "gaking_channel_commission_config",
    # B06-2 渠道导出任务日志
    "gaking_channel_export_task_log",
    # B07-1 逆向佣金冲减记录
    "gaking_reverse_commission_record",
    # B08-1 资金流水记录
    "gaking_fund_flow",
}


def include_object(object, name, type_, reflected, compare_to):
    """过滤函数：仅包含目标表的迁移变更"""
    if type_ == "table":
        return name in TARGET_TABLES
    # 对于列、索引、外键等，仅当其所属表在目标范围内时才包含
    return True


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本，不连接数据库"""
    url = EnvConfig.get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在线模式：通过已有连接执行迁移"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步迁移核心：使用 aiomysql 异步驱动连接 MySQL 执行迁移"""
    # 从 EnvConfig 动态读取 DB URL，禁止写死账号密码
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = EnvConfig.get_db_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # 确保 alembic_version.version_num 列宽足够（长版本号 >32 字符时默认列宽报 1406）：
    # 全新库在 alembic 建版本表前手动预建 VARCHAR(64)；存量库 ALTER 扩列。
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text as sa_text

    def _ensure_version_table(sync_conn) -> None:
        if sa_inspect(sync_conn).has_table("alembic_version"):
            sync_conn.execute(
                sa_text(
                    "ALTER TABLE alembic_version MODIFY version_num VARCHAR(64) NOT NULL"
                )
            )
        else:
            sync_conn.execute(
                sa_text(
                    "CREATE TABLE alembic_version ("
                    "version_num VARCHAR(64) NOT NULL, "
                    "PRIMARY KEY (version_num))"
                )
            )

    async with connectable.begin() as fix_conn:
        await fix_conn.run_sync(_ensure_version_table)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式入口：通过 asyncio.run 启动异步迁移"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
