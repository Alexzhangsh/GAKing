# @ai-generated
"""
B14 后台权限统一管控与系统配置模块常量定义
新建文件，不修改 B01-B13 任何基线常量

内容：
1. B14 新增权限码（rbac:manage / config:manage / audit:view / menu:manage）
2. 现有 admin 权限码集中导出（仅 import 复用，不改动原文件）
3. AuditAction 审计动作枚举
4. B14_CONFIG_REGISTRY 配置 key 注册表（key → 类型/默认/校验/描述）
5. Redis 键与限流配置
"""
from decimal import Decimal
from enum import Enum
from typing import Any, Dict

from src.config.constants import (
    CACHE_KEY_SYSTEM_CONFIG,
    RATE_LIMIT_PREFIX,
    REDIS_PREFIX,
)

# ════════════════════════════════════════════════════════════
# 1. B14 新增权限码
# ════════════════════════════════════════════════════════════
PERM_RBAC_MANAGE = "rbac:manage"  # RBAC 角色/用户管理
PERM_CONFIG_MANAGE = "config:manage"  # 系统配置管理
PERM_AUDIT_VIEW = "audit:view"  # 审计日志查看
PERM_MENU_MANAGE = "menu:manage"  # 菜单管理

# B14 新增权限码集合
B14_PERMISSIONS = [
    PERM_RBAC_MANAGE,
    PERM_CONFIG_MANAGE,
    PERM_AUDIT_VIEW,
    PERM_MENU_MANAGE,
]

# 全部 admin 权限码字典（含现有 5 个 + B14 新增 4 个），供 RBAC 管理 API 下发前端
ALL_ADMIN_PERMISSIONS = [
    {"code": "order:sync", "name": "订单同步管理", "module": "B07", "group": "订单管理"},
    {"code": "withdraw:review", "name": "提现审核", "module": "B09/B11", "group": "提现管理"},
    {"code": "commission:settle", "name": "佣金结算管理", "module": "B11", "group": "结算管理"},
    {"code": "settlement:review", "name": "结算状态机管理", "module": "B12", "group": "结算管理"},
    {"code": "reconciliation:review", "name": "全链路对账", "module": "B13", "group": "对账管理"},
    {"code": PERM_RBAC_MANAGE, "name": "RBAC 权限管理", "module": "B14", "group": "权限管理"},
    {"code": PERM_CONFIG_MANAGE, "name": "系统配置管理", "module": "B14", "group": "系统配置"},
    {"code": PERM_AUDIT_VIEW, "name": "审计日志查看", "module": "B14", "group": "审计日志"},
    {"code": PERM_MENU_MANAGE, "name": "菜单管理", "module": "B14", "group": "菜单管理"},
    # ↓ B13-补全 + B14-补全 新增权限码（数据扩展，不改逻辑）
    {"code": "goods:manage", "name": "商品后台管理", "module": "B13", "group": "商品管理"},
    {"code": "user:manage", "name": "C端用户管理", "module": "B13", "group": "用户管理"},
    {"code": "dashboard:view", "name": "数据大盘查看", "module": "B14", "group": "数据大盘"},
    # ↓ B13-1 新增权限码
    {"code": "order:manage", "name": "订单后台管理", "module": "B13-1", "group": "订单管理"},
    {"code": "withdraw:manage", "name": "提现后台管理", "module": "B13-1", "group": "提现管理"},
    # ↓ F04 新增权限码（营销消息 + 渠道配置）
    {"code": "message:manage", "name": "营销消息管理", "module": "F04", "group": "营销消息"},
    {"code": "channel:test", "name": "渠道密钥测试", "module": "F04", "group": "渠道配置"},
    # ↓ M07-2 新增权限码（运维监控）
    {"code": "ops:monitor", "name": "运维监控查看", "module": "M07-2", "group": "运维监控"},
    # ↓ X02-1 新增权限码（会员套餐管理）
    {"code": "member:manage", "name": "会员套餐管理", "module": "X02-1", "group": "会员管理"},
    {"code": "member:view", "name": "会员数据查看", "module": "X02-1", "group": "会员管理"},
    {"code": "member:export", "name": "会员数据导出", "module": "X02-1", "group": "会员管理"},
]

# 超管通配符（与 RbacUtil.has_permission 对齐）
SUPER_ADMIN_PERMISSION = "*"


# ════════════════════════════════════════════════════════════
# 2. 审计动作枚举
# ════════════════════════════════════════════════════════════
class AuditAction(str, Enum):
    """审计日志动作类型（写入 AuditLogs.action 字段）"""

    # 通用 HTTP 写操作（中间件自动记录）
    HTTP_POST = "HTTP_POST"
    HTTP_PUT = "HTTP_PUT"
    HTTP_PATCH = "HTTP_PATCH"
    HTTP_DELETE = "HTTP_DELETE"

    # 认证相关
    ADMIN_LOGIN = "ADMIN_LOGIN"
    ADMIN_LOGIN_FAILED = "ADMIN_LOGIN_FAILED"
    ADMIN_LOGOUT = "ADMIN_LOGOUT"

    # RBAC 管理
    ROLE_CREATE = "ROLE_CREATE"
    ROLE_UPDATE = "ROLE_UPDATE"
    ROLE_DELETE = "ROLE_DELETE"
    ROLE_PERMISSION_CHANGE = "ROLE_PERMISSION_CHANGE"
    ADMIN_USER_CREATE = "ADMIN_USER_CREATE"
    ADMIN_USER_UPDATE = "ADMIN_USER_UPDATE"
    ADMIN_USER_DELETE = "ADMIN_USER_DELETE"
    PASSWORD_RESET = "PASSWORD_RESET"
    MENU_CREATE = "MENU_CREATE"
    MENU_UPDATE = "MENU_UPDATE"
    MENU_DELETE = "MENU_DELETE"

    # 系统配置
    CONFIG_CREATE = "CONFIG_CREATE"
    CONFIG_UPDATE = "CONFIG_UPDATE"
    CONFIG_DELETE = "CONFIG_DELETE"
    CONFIG_BATCH_UPDATE = "CONFIG_BATCH_UPDATE"
    CONFIG_CACHE_REFRESH = "CONFIG_CACHE_REFRESH"


# 审计目标类型
class AuditTargetType(str, Enum):
    ENDPOINT = "endpoint"
    ROLE = "role"
    ADMIN_USER = "admin_user"
    MENU = "menu"
    CONFIG = "config"
    LOGIN = "login"


# ════════════════════════════════════════════════════════════
# 3. 配置 key 注册表
# ════════════════════════════════════════════════════════════
# 支持 hot reload 的配置 key 白名单，key → {type, default, min, max, desc}
# B14ConfigUtil/SystemConfigB14Service 校验 key 必须在此注册表内
# B12/B13 常量兜底值通过 fallback 字段引用（不修改 B12/B13 代码）


def _reg(
    config_type: str,
    default: Any,
    desc: str,
    min_val: Any = None,
    max_val: Any = None,
) -> Dict[str, Any]:
    """构建注册表条目"""
    return {
        "type": config_type,  # int / bool / str / decimal / json
        "default": default,
        "min": min_val,
        "max": max_val,
        "desc": desc,
    }


B14_CONFIG_REGISTRY: Dict[str, Dict[str, Any]] = {
    # ── 结算延迟天数（B12 settlement_delay_days，兜底 SETTLEMENT_DELAY_DAYS_DEFAULT）──
    "settlement_delay_days": _reg(
        "int", 30, "佣金结算延迟天数（SETTLABLE→SETTLED 等待渠道返佣天数）", 1, 365
    ),
    # ── 对账执行时间 cron（B13）──
    "reconciliation_cron": _reg(
        "str", "0 2 * * *", "全链路对账定时任务 cron 表达式（Asia/Shanghai 时区）"
    ),
    # ── 熔断阈值（B04 CircuitBreaker 连续失败次数）──
    "circuit_breaker_threshold": _reg(
        "int", 5, "熔断器连续失败触发阈值（次）", 1, 100
    ),
    # ── 金额容差（B13 对账 RECONCILIATION_TOLERANCE）──
    "amount_tolerance": _reg(
        "decimal", Decimal("0.01"), "对账金额容差（元，差异小于此值视为平账）"
    ),
    # ── 后台 admin 限流阈值（次/分钟）──
    "admin_rate_limit_per_minute": _reg(
        "int", 60, "后台 admin 接口限流阈值（单 IP 每分钟最大请求数）", 1, 10000
    ),
    # ── 定时任务开关（B12 task8/task9、B05 订单同步、B13 对账）──
    "task_settlement_freeze_enable": _reg(
        "bool", True, "B12 结算冻结定时任务（task8）开关"
    ),
    "task_settlement_unfreeze_enable": _reg(
        "bool", True, "B12 结算解冻定时任务（task9）开关"
    ),
    "task_order_sync_enable": _reg("bool", True, "B05 订单同步定时任务开关"),
    "task_reconciliation_enable": _reg("bool", True, "B13 全链路对账定时任务开关"),
    # ── JWT 过期时间（秒，仅 admin）──
    "admin_jwt_expires_in": _reg(
        "int", 3600, "后台 admin JWT 过期时间（秒）", 300, 86400
    ),
}


# 允许批量更新的 key 前缀（仅 task_*_enable 类型）
BATCH_UPDATE_KEY_PREFIX = "task_"


# ════════════════════════════════════════════════════════════
# 4. Redis 键
# ════════════════════════════════════════════════════════════
# 系统配置缓存（复用 constants.py 既有定义，永久有效）
CACHE_KEY_B14_CONFIG = CACHE_KEY_SYSTEM_CONFIG  # gaking:prod:config:system

# admin JWT 黑名单（密码重置后强制下线）：gaking:prod:auth:blacklist:{user_id}
CACHE_KEY_ADMIN_JWT_BLACKLIST = f"{REDIS_PREFIX}auth:blacklist:"

# admin 登录失败次数缓存（防爆破）：gaking:prod:auth:login_fail:{username}
CACHE_KEY_ADMIN_LOGIN_FAIL = f"{REDIS_PREFIX}auth:login_fail:"

# admin 限流 key 前缀（gaking:prod:rate:admin:{ip}，RateLimitUtil 内部已拼 RATE_LIMIT_PREFIX）
RATE_LIMIT_ADMIN_KEY_PREFIX = "admin:"

# 登录失败锁定阈值
ADMIN_LOGIN_FAIL_MAX = 5
ADMIN_LOGIN_FAIL_TTL = 900  # 15 分钟

# 默认超管账号（迁移 seed 使用）
DEFAULT_SUPER_ADMIN_USERNAME = "admin"
DEFAULT_SUPER_ADMIN_PASSWORD = "admin@12345"  # 首次登录强制修改
DEFAULT_SUPER_ADMIN_ROLE_NAME = "超级管理员"
DEFAULT_SUPER_ADMIN_REAL_NAME = "系统超管"


# ════════════════════════════════════════════════════════════
# 5. 限流中间件跳过路径
# ════════════════════════════════════════════════════════════
RATE_LIMIT_SKIP_PATHS = frozenset(
    {
        "/healthz",
        "/readyz",
        "/metrics",
        "/api/v1/admin/auth/login",  # 登录接口单独防爆破，不走通用限流
    }
)

# admin 路由前缀（限流/审计中间件拦截判定）
ADMIN_PATH_PREFIX = "/api/v1/admin/"

# 审计中间件拦截的 HTTP 方法（写操作）
AUDIT_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


# ════════════════════════════════════════════════════════════
# 6. 敏感字段脱敏规则（AuditLogger.sanitize_details 使用）
# ════════════════════════════════════════════════════════════
SENSITIVE_FIELD_PATTERNS = (
    "password",
    "pwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "private_key",
    "credentials",
)
