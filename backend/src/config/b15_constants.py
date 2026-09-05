# @ai-generated
"""
B15 RBAC 全局鉴权中间件常量定义
新建文件，不修改 B01-B14 任何基线常量

内容：
1. URL→权限码映射表（PATH_PERMISSION_MAP）
2. 公开路径白名单（PUBLIC_PATHS）
3. JWT 仅需路径列表（JWT_ONLY_PATHS）
4. 中间件跳过路径前缀（SKIP_PATH_PREFIXES）
5. B15 新增权限码
"""
from typing import Dict, FrozenSet, Set

# ════════════════════════════════════════════════════════════
# 1. URL 路径→权限码映射表
# ════════════════════════════════════════════════════════════
# 全局 RBAC 中间件根据此映射自动检测请求路径是否需要鉴权/权限校验
# 匹配规则：最长前缀匹配（例如 /api/v1/admin/rbac/roles/123 匹配 /api/v1/admin/rbac/roles）
# 特殊标记：
#   "PUBLIC"  - 公开路径，无需任何鉴权
#   "JWT"     - 仅需有效 JWT（已登录），不校验特定权限码
#   权限码     - 需要用户拥有该权限码（或 * 超管通配符）
PATH_PERMISSION_MAP: Dict[str, str] = {
    # ── 认证模块 ──
    "/api/v1/admin/auth/login": "PUBLIC",
    "/api/v1/admin/auth/logout": "JWT",
    "/api/v1/admin/auth/me": "JWT",
    "/api/v1/admin/auth/password": "JWT",

    # ── 菜单管理（menu:manage）──
    "/api/v1/admin/rbac/menus/tree": "menu:manage",
    "/api/v1/admin/rbac/menus": "menu:manage",

    # ── 角色管理（rbac:manage）──
    "/api/v1/admin/rbac/roles": "rbac:manage",
    "/api/v1/admin/rbac/permissions": "rbac:manage",

    # ── 管理员账号管理（rbac:manage）──
    "/api/v1/admin/rbac/users": "rbac:manage",

    # ── 系统配置（config:manage）──
    "/api/v1/admin/config/registry": "config:manage",
    "/api/v1/admin/config/batch": "config:manage",
    "/api/v1/admin/config/cache/refresh": "config:manage",
    "/api/v1/admin/config/validate": "config:manage",
    "/api/v1/admin/config": "config:manage",

    # ── 审计日志（audit:view）──
    "/api/v1/admin/audit/stats": "audit:view",
    "/api/v1/admin/audit/logs": "audit:view",

    # ── B13-补全：数据大盘（dashboard:view/dashboard:export）──
    "/api/v1/admin/dashboard/cards": "dashboard:view",
    "/api/v1/admin/dashboard/commission-stats": "dashboard:view",
    "/api/v1/admin/dashboard/order-trend": "dashboard:view",
    "/api/v1/admin/dashboard/withdraw-trend": "dashboard:view",
    "/api/v1/admin/dashboard/export": "dashboard:export",

    # ── B13-补全：商品管理（goods:manage）──
    "/api/v1/admin/goods": "goods:manage",

    # ── B13-补全：C端用户管理（user:manage）──
    "/api/v1/admin/users-manage": "user:manage",

    # ── B13-1：订单管理（order:manage）──
    "/api/v1/admin/b13/orders": "order:manage",

    # ── B13-1：提现管理（withdraw:manage）──
    "/api/v1/admin/b13/withdraws": "withdraw:manage",

    # ── B05：订单同步管理（order:sync）──
    "/api/v1/admin/order-sync": "order:sync",

    # ── B09/B11：提现审核（withdraw:review）──
    "/api/v1/admin/withdraw": "withdraw:review",

    # ── B07：佣金结算（commission:settle）──
    "/api/v1/admin/commission-settlement": "commission:settle",
    "/api/v1/admin/commission-flow-validation": "commission:settle",
    "/api/v1/admin/refund-deduction": "commission:settle",

    # ── B12：结算状态机（settlement:review）──
    "/api/v1/admin/settlement": "settlement:review",

    # ── B13：全链路对账（reconciliation:review）──
    "/api/v1/admin/reconciliation": "reconciliation:review",

    # ── B06-1：渠道管理（channel:manage）──
    "/api/v1/admin/b06-channel": "channel:manage",

    # ── B06-2：渠道报表（channel:export / channel:reconciliation）──
    "/api/v1/admin/b06-2": "channel:export",

    # ── B07-1：逆向佣金冲减（reverse:commission）──
    "/api/v1/admin/b07/reverse-commission": "reverse:commission",

    # ── B08-1：用户资产账户（fund:account:view）──
    "/api/v1/admin/b08": "fund:account:view",

    # ── B10：消息管理（message:manage）──
    "/api/v1/admin/message": "message:manage",

    # ── F04-2：渠道佣金策略（config:manage）──
    "/api/v1/admin/channel-commission": "config:manage",

    # ── B11-1：渠道黑名单（channel:blacklist）──
    "/api/v1/admin/b11/channel": "channel:blacklist",

    # ── B12-1：订单状态机（order:state_machine）──
    "/api/v1/admin/b12/order-state": "order:state_machine",

    # ── B05-4：短链管理（无特殊权限要求，JWT即可）──
    "/api/v1/admin/short-links": "JWT",
    "/api/v1/admin/abnormal-orders": "JWT",

    # ── B05-7：定时任务运行日志（无特殊权限要求，JWT即可）──
    "/api/v1/admin/scheduled-task-run-logs": "JWT",

    # ── X02-1：会员套餐管理（member:manage）──
    "/api/v1/admin/member-package": "member:manage",

    # ── X02-1：会员记录（member:view / member:export）──
    "/api/v1/admin/member-record/export": "member:export",
    "/api/v1/admin/member-record": "member:view",
}

# 需要最长前缀匹配的路径前缀（供中间件路由匹配使用）
# 这些前缀的路径需要按 PATH_PERMISSION_MAP 中注册的完整路径做前缀匹配
PATH_PREFIXES: FrozenSet[str] = frozenset(
    {
        "/api/v1/admin/auth",
        "/api/v1/admin/rbac",
        "/api/v1/admin/config",
        "/api/v1/admin/audit",
        "/api/v1/admin/dashboard",
        "/api/v1/admin/goods",
        "/api/v1/admin/users-manage",
        "/api/v1/admin/b13/orders",
        "/api/v1/admin/b13/withdraws",
        "/api/v1/admin/order-sync",
        "/api/v1/admin/withdraw",
        "/api/v1/admin/commission-settlement",
        "/api/v1/admin/commission-flow-validation",
        "/api/v1/admin/refund-deduction",
        "/api/v1/admin/settlement",
        "/api/v1/admin/reconciliation",
        "/api/v1/admin/b06-channel",
        "/api/v1/admin/b06-2",
        "/api/v1/admin/b07/reverse-commission",
        "/api/v1/admin/b08",
        "/api/v1/admin/message",
        "/api/v1/admin/channel-commission",
        "/api/v1/admin/b11/channel",
        "/api/v1/admin/b12/order-state",
        "/api/v1/admin/short-links",
        "/api/v1/admin/abnormal-orders",
        "/api/v1/admin/scheduled-task-run-logs",
        "/api/v1/admin/member-package",
        "/api/v1/admin/member-record",
    }
)


# ════════════════════════════════════════════════════════════
# 2. 公开路径白名单（无需任何鉴权）
# ════════════════════════════════════════════════════════════
# 这些路径完全跳过 RBAC 中间件
PUBLIC_PATHS: FrozenSet[str] = frozenset(
    {
        "/healthz",
        "/readyz",
        "/metrics",
        "/api/v1/admin/auth/login",
    }
)


# ════════════════════════════════════════════════════════════
# 3. JWT 仅需路径列表（已登录即可，无需特定权限码）
# ════════════════════════════════════════════════════════════
# 这些路径只要求 JWT 有效且不在黑名单中
JWT_ONLY_PATHS: FrozenSet[str] = frozenset(
    {
        "/api/v1/admin/auth/logout",
        "/api/v1/admin/auth/me",
        "/api/v1/admin/auth/password",
        "/api/v1/admin/short-links",
        "/api/v1/admin/abnormal-orders",
        "/api/v1/admin/scheduled-task-run-logs",
    }
)


# ════════════════════════════════════════════════════════════
# 4. 中间件跳过路径前缀
# ════════════════════════════════════════════════════════════
# 不以 /api/v1/admin/ 开头的路径跳过 RBAC 中间件
ADMIN_PATH_PREFIX = "/api/v1/admin/"


# ════════════════════════════════════════════════════════════
# 5. B15 新增权限码（需同步更新后台功能清单总览.md 权限码汇总）
# ════════════════════════════════════════════════════════════
# B15 不新增独立权限码，复用 B14 已有的权限码体系
# 但新增的全局鉴权中间件覆盖了所有存量后台模块的权限码映射

# 从 B14 导入已有权限码（供中间件内部使用）
from src.config.b14_constants import (  # noqa: E402, F401
    PERM_RBAC_MANAGE,
    PERM_CONFIG_MANAGE,
    PERM_AUDIT_VIEW,
    PERM_MENU_MANAGE,
    SUPER_ADMIN_PERMISSION,
)

# ════════════════════════════════════════════════════════════
# 6. F04 新增权限码（营销消息 + 渠道配置）
# ════════════════════════════════════════════════════════════
PERM_MESSAGE_MANAGE = "message:manage"  # 营销消息管理（模板/推送记录/订阅绑定）
PERM_CHANNEL_TEST = "channel:test"  # 渠道密钥测试