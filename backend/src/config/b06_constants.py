# @ai-generated
"""
B06 渠道管理模块常量定义
新建文件，不修改 B01-B15 任何基线常量

内容：
1. B06 新增权限码（channel:manage）
2. 渠道佣金比例配置相关枚举
3. 审计动作枚举扩展
4. Redis 键与缓存配置
"""
from enum import Enum, IntEnum

from src.config.b14_constants import ALL_ADMIN_PERMISSIONS as _B14_PERMS

# ════════════════════════════════════════════════════════════
# 1. B06 新增权限码
# ════════════════════════════════════════════════════════════
PERM_CHANNEL_MANAGE = "channel:manage"  # 渠道管理（含佣金配置）

# B06 新增权限码集合
B06_PERMISSIONS = [
    PERM_CHANNEL_MANAGE,
]

# 全部 admin 权限码字典（B14 基线 + B06 新增），供 RBAC 管理 API 下发前端
ALL_ADMIN_PERMISSIONS = _B14_PERMS + [
    {"code": PERM_CHANNEL_MANAGE, "name": "渠道管理", "module": "B06"},
]


# ════════════════════════════════════════════════════════════
# 2. 渠道佣金比例配置相关枚举
# ════════════════════════════════════════════════════════════
class UserType(int, Enum):
    """用户类型枚举"""

    NORMAL = 1  # 普通用户
    VIP = 2  # 付费会员


# 用户类型中文映射
USER_TYPE_LABELS = {
    UserType.NORMAL: "普通用户",
    UserType.VIP: "付费会员",
}


# ════════════════════════════════════════════════════════════
# 3. 审计动作枚举扩展
# ════════════════════════════════════════════════════════════
class AuditAction(str, Enum):
    """审计日志动作类型（B06 扩展）"""

    CHANNEL_CREATE = "CHANNEL_CREATE"
    CHANNEL_UPDATE = "CHANNEL_UPDATE"
    CHANNEL_DELETE = "CHANNEL_DELETE"
    CHANNEL_TOGGLE_STATUS = "CHANNEL_TOGGLE_STATUS"
    CHANNEL_COMMISSION_CONFIG = "CHANNEL_COMMISSION_CONFIG"


class AuditTargetType(str, Enum):
    """审计目标类型（B06 扩展）"""

    CHANNEL = "channel"


# ════════════════════════════════════════════════════════════
# 4. Redis 键与缓存配置
# ════════════════════════════════════════════════════════════
from src.config.constants import REDIS_PREFIX

# 渠道佣金配置缓存：gaking:prod:channel:commission_config:{channel_code}
CACHE_KEY_CHANNEL_COMMISSION = f"{REDIS_PREFIX}channel:commission_config:"
# 渠道佣金配置缓存 TTL：10 分钟
CACHE_TTL_CHANNEL_COMMISSION = 10 * 60

# 渠道数据看板缓存：gaking:prod:channel:dashboard:{channel_code}:{date}
CACHE_KEY_CHANNEL_DASHBOARD = f"{REDIS_PREFIX}channel:dashboard:"
CACHE_TTL_CHANNEL_DASHBOARD = 5 * 60