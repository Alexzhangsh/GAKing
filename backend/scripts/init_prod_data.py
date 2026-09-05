#!/usr/bin/env python3
# @ai-generated
"""
S04 生产数据库基础数据初始化脚本（幂等，可重复执行）

功能：
1. 渠道配置初始化：仅启用喵有券(myq)，禁用订单侠(orderx)/大淘客(dta)
2. 消息模板初始化：预置微信订阅消息模板(template_type=1) + 站内消息模板(template_type=2)
3. 基础角色初始化：创建运营/财务/客服等基础角色，绑定对应权限码
4. 权限码完整性校验：遍历 31 项权限码，确认角色权限绑定无缺失

运行环境：后端 Docker 容器内（已装 SQLAlchemy + aiomysql）
运行方式：
  docker compose exec backend python /app/scripts/init_prod_data.py
  或本地：cd backend && python scripts/init_prod_data.py

安全：本脚本仅写入非敏感基础数据，渠道密钥从 .env 读取，不硬编码。
"""
import asyncio
import json
import logging
import os
import sys

from sqlalchemy import select

# 允许从 backend 根目录直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.env_config import EnvConfig
from src.db.init_db import DatabaseManager
from src.models.system.channel_config import ChannelMapping
from src.models.system.message_template import MessageTemplate
from src.db.models import AdminRole

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("init_prod_data")


# ════════════════════════════════════════════════════════════
# 1. 渠道配置
# ════════════════════════════════════════════════════════════

# 渠道配置：channel_code → (channel_name, status, settle_rate, remark)
# S04 红线：仅启用喵有券(myq)，订单侠/大淘客保持停用
CHANNEL_CONFIGS = {
    "myq": {
        "channel_name": "喵有券",
        "status": True,
        "settle_rate": 0.80,
        "remark": "S04 生产启用：主渠道（高级会员）",
    },
    "orderx": {
        "channel_name": "订单侠",
        "status": False,
        "settle_rate": 0.00,
        "remark": "S04 生产停用：等主体功能开发完成后再付费开通",
    },
    "dta": {
        "channel_name": "大淘客",
        "status": False,
        "settle_rate": 0.00,
        "remark": "S04 生产停用：一期/二期均不对接",
    },
}


# ════════════════════════════════════════════════════════════
# 2. 消息模板
# ════════════════════════════════════════════════════════════

# 微信订阅消息模板（template_type=1），tmpl_id 需替换为微信公众平台审核通过的模板ID
WX_SUBSCRIBE_TEMPLATES = [
    {
        "template_name": "S01-佣金到账通知",
        "tmpl_id": "s01_tmpl_001",
        "title": "佣金已到账",
        "content": "您好，您的订单{{keyword1}}佣金{{keyword2}}已到账",
        "keywords": ["订单号", "佣金金额"],
        "status": 1,
        "remark": "S04 预置：佣金到账微信订阅模板",
    },
    {
        "template_name": "S02-订单状态通知",
        "tmpl_id": "s02_tmpl_001",
        "title": "订单状态更新",
        "content": "您的订单{{keyword1}}状态已更新为{{keyword2}}",
        "keywords": ["订单号", "订单状态"],
        "status": 1,
        "remark": "S04 预置：订单状态微信订阅模板",
    },
    {
        "template_name": "S03-提现到账通知",
        "tmpl_id": "s03_tmpl_001",
        "title": "提现已到账",
        "content": "您的提现申请{{keyword1}}金额{{keyword2}}已到账",
        "keywords": ["提现单号", "提现金额"],
        "status": 1,
        "remark": "S04 预置：提现到账微信订阅模板",
    },
    {
        "template_name": "S04-退款通知",
        "tmpl_id": "s04_tmpl_001",
        "title": "退款处理通知",
        "content": "您的订单{{keyword1}}退款{{keyword2}}已处理",
        "keywords": ["订单号", "退款金额"],
        "status": 1,
        "remark": "S04 预置：退款微信订阅模板",
    },
]

# 站内消息模板（template_type=2）
STATION_MESSAGE_TEMPLATES = [
    {
        "template_name": "N01-佣金到账站内通知",
        "tmpl_id": "",
        "title": "佣金已到账",
        "content": "订单{{keyword1}}佣金{{keyword2}}已到账，可在「我的佣金」查看",
        "keywords": ["订单号", "佣金金额"],
        "status": 1,
        "remark": "S04 预置：佣金到账站内消息模板",
    },
    {
        "template_name": "N02-提现到账站内通知",
        "tmpl_id": "",
        "title": "提现已到账",
        "content": "提现{{keyword1}}金额{{keyword2}}已到账",
        "keywords": ["提现单号", "提现金额"],
        "status": 1,
        "remark": "S04 预置：提现到账站内消息模板",
    },
    {
        "template_name": "N03-订单状态站内通知",
        "tmpl_id": "",
        "title": "订单状态更新",
        "content": "订单{{keyword1}}状态已更新为{{keyword2}}",
        "keywords": ["订单号", "订单状态"],
        "status": 1,
        "remark": "S04 预置：订单状态站内消息模板",
    },
]


# ════════════════════════════════════════════════════════════
# 3. 权限码 + 基础角色
# ════════════════════════════════════════════════════════════

# 全部 31 项权限码（30 项唯一权限码 + 超管通配符 *）
ALL_PERMISSION_CODES = [
    # B14 基线 16 项
    "order:sync", "withdraw:review", "commission:settle", "settlement:review",
    "reconciliation:review", "rbac:manage", "config:manage", "audit:view",
    "menu:manage", "goods:manage", "user:manage", "dashboard:view",
    "order:manage", "withdraw:manage", "message:manage", "channel:test",
    # 各模块新增 14 项
    "fund:account:view", "fund:account:credit", "fund:account:debit",
    "fund:account:freeze", "fund:flow:view", "dashboard:export",
    "channel:export", "channel:reconciliation", "channel:manage",
    "reverse:commission", "order:state_machine", "order:operation_log",
    "channel:stat", "channel:blacklist",
]
SUPER_ADMIN_PERMISSION = "*"

# 基础角色定义：role_name → permissions 列表
BASE_ROLES = [
    {
        "role_name": "运营管理员",
        "role_desc": "日常运营：商品/订单/渠道/消息管理",
        "permissions": [
            "order:sync", "goods:manage", "order:manage", "user:manage",
            "channel:manage", "channel:test", "channel:stat", "channel:export",
            "channel:reconciliation", "message:manage", "dashboard:view",
            "dashboard:export", "order:state_machine", "order:operation_log",
            "channel:blacklist",
        ],
    },
    {
        "role_name": "财务管理员",
        "role_desc": "财务：佣金结算/提现审核/对账/资金账户",
        "permissions": [
            "withdraw:review", "commission:settle", "settlement:review",
            "reconciliation:review", "withdraw:manage", "fund:account:view",
            "fund:account:credit", "fund:account:debit", "fund:account:freeze",
            "fund:flow:view", "reverse:commission", "dashboard:view",
            "dashboard:export",
        ],
    },
    {
        "role_name": "客服管理员",
        "role_desc": "客服：用户/订单/退款查询与处理",
        "permissions": [
            "user:manage", "order:manage", "order:operation_log",
            "order:state_machine", "withdraw:review", "dashboard:view",
        ],
    },
    {
        "role_name": "只读审计员",
        "role_desc": "审计：只读查看审计日志/数据大盘",
        "permissions": [
            "audit:view", "dashboard:view", "dashboard:export",
            "reconciliation:review",
        ],
    },
]


# ════════════════════════════════════════════════════════════
# 初始化逻辑
# ════════════════════════════════════════════════════════════


async def init_channels(session) -> None:
    """幂等初始化渠道配置"""
    for code, cfg in CHANNEL_CONFIGS.items():
        stmt = select(ChannelMapping).where(ChannelMapping.channel_code == code)
        result = await session.execute(stmt)
        ch = result.scalar_one_or_none()
        api_token = ""
        if code == "myq":
            api_token = EnvConfig.MIAO_QUAN_TOKEN
        if ch is None:
            session.add(ChannelMapping(
                channel_code=code,
                channel_name=cfg["channel_name"],
                api_token=api_token,
                api_secret="",
                pid=EnvConfig.MIAO_QUAN_PID if code == "myq" else "",
                settle_rate=cfg["settle_rate"],
                status=cfg["status"],
                remark=cfg["remark"],
            ))
            logger.info("[渠道] 创建 %s(%s) status=%s", code, cfg["channel_name"], cfg["status"])
        else:
            ch.channel_name = cfg["channel_name"]
            ch.status = cfg["status"]
            ch.settle_rate = cfg["settle_rate"]
            ch.remark = cfg["remark"]
            if code == "myq" and api_token:
                ch.api_token = api_token
            logger.info("[渠道] 更新 %s(%s) status=%s", code, cfg["channel_name"], cfg["status"])
    await session.commit()


async def init_message_templates(session) -> None:
    """幂等初始化消息模板（按 template_name 唯一）"""
    all_templates = WX_SUBSCRIBE_TEMPLATES + STATION_MESSAGE_TEMPLATES
    for tpl in all_templates:
        stmt = select(MessageTemplate).where(MessageTemplate.template_name == tpl["template_name"])
        result = await session.execute(stmt)
        t = result.scalar_one_or_none()
        if t is None:
            session.add(MessageTemplate(
                template_name=tpl["template_name"],
                template_type=tpl.get("template_type", 1),
                tmpl_id=tpl["tmpl_id"],
                title=tpl["title"],
                content=tpl["content"],
                keywords=tpl["keywords"],
                status=tpl["status"],
                remark=tpl["remark"],
            ))
            logger.info("[模板] 创建 %s", tpl["template_name"])
        else:
            t.title = tpl["title"]
            t.content = tpl["content"]
            t.keywords = tpl["keywords"]
            t.status = tpl["status"]
            t.remark = tpl["remark"]
            logger.info("[模板] 更新 %s", tpl["template_name"])
    await session.commit()


async def init_base_roles(session) -> None:
    """幂等初始化基础角色（不含超管，超管由 init_super_admin.py 处理）"""
    for role in BASE_ROLES:
        stmt = select(AdminRole).where(AdminRole.role_name == role["role_name"])
        result = await session.execute(stmt)
        r = result.scalar_one_or_none()
        perms_json = json.dumps(role["permissions"], ensure_ascii=False)
        if r is None:
            session.add(AdminRole(
                role_name=role["role_name"],
                role_desc=role["role_desc"],
                permissions=perms_json,
                status=1,
                is_delete=False,
            ))
            logger.info("[角色] 创建 %s（%d 项权限）", role["role_name"], len(role["permissions"]))
        else:
            r.role_desc = role["role_desc"]
            r.permissions = perms_json
            r.status = 1
            r.is_delete = False
            logger.info("[角色] 更新 %s（%d 项权限）", role["role_name"], len(role["permissions"]))
    await session.commit()


async def verify_permissions(session) -> None:
    """校验 31 项权限码完整性 + 角色权限绑定"""
    logger.info("=" * 60)
    logger.info("权限码完整性校验（共 %d 项唯一权限码 + 超管通配符）", len(ALL_PERMISSION_CODES))
    logger.info("=" * 60)

    # 校验权限码唯一性
    unique_codes = set(ALL_PERMISSION_CODES)
    if len(unique_codes) != len(ALL_PERMISSION_CODES):
        logger.warning("[校验] 权限码清单存在重复项！")
    else:
        logger.info("[校验] 权限码清单无重复，共 %d 项", len(unique_codes))

    # 校验角色权限绑定：每个权限码至少被一个非超管角色绑定
    stmt = select(AdminRole).where(AdminRole.is_delete == False)  # noqa: E712
    result = await session.execute(stmt)
    roles = result.scalars().all()

    bound_perms = set()
    for role in roles:
        try:
            perms = json.loads(role.permissions or "[]")
        except (json.JSONDecodeError, TypeError):
            perms = []
        bound_perms.update(perms)

    missing = []
    for code in unique_codes:
        if code not in bound_perms:
            missing.append(code)

    if missing:
        logger.warning("[校验] 以下 %d 项权限码未被任何角色绑定: %s", len(missing), missing)
    else:
        logger.info("[校验] 全部 %d 项权限码均已被角色绑定", len(unique_codes))

    # 输出角色清单
    logger.info("角色清单（%d 个）:", len(roles))
    for role in roles:
        try:
            perms = json.loads(role.permissions or "[]")
        except (json.JSONDecodeError, TypeError):
            perms = []
        logger.info("  - %s: %d 项权限", role.role_name, len(perms))


async def main() -> None:
    EnvConfig.load()
    DatabaseManager.initialize()
    async with DatabaseManager.get_session() as session:
        await init_channels(session)
        await init_message_templates(session)
        await init_base_roles(session)
        await verify_permissions(session)
    await DatabaseManager.dispose()
    logger.info("[DONE] S04 生产数据库基础数据初始化完成")


if __name__ == "__main__":
    asyncio.run(main())
