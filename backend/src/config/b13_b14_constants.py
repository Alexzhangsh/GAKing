# @ai-generated
"""
B13-补全 + B14-补全 模块常量定义（新建独立文件，不修改 B01-B15 存量代码）
包含：
1. 新增权限码常量（goods:manage / user:manage / dashboard:view）
2. 商品管理扩展表状态枚举
3. 用户管理扩展表状态枚举
4. Redis Key 前缀（统一 gaking:prod 前缀）
5. 新增权限码注册表（供 RBAC 接口下发前端）
"""
from enum import Enum


# ════════════════════════════════════════════════════════════
# 1. 新增权限码常量
# ════════════════════════════════════════════════════════════
PERM_GOODS_MANAGE = "goods:manage"      # 商品后台管理（上下架/编辑/批量操作）
PERM_USER_MANAGE = "user:manage"        # C端用户后台管理（冻结/解冻/备注）
PERM_DASHBOARD_VIEW = "dashboard:view"  # 数据大盘查看（卡片/多维度统计）
# B13-1 新增权限码
PERM_ORDER_MANAGE = "order:manage"      # 订单后台管理（列表/详情/状态流转/操作日志）
PERM_WITHDRAW_MANAGE = "withdraw:manage"  # 提现后台管理（列表/详情/审核/转账）
# B14-1 新增权限码
PERM_DASHBOARD_EXPORT = "dashboard:export"  # 数据大盘报表导出
# M07-2 新增权限码
PERM_OPS_MONITOR = "ops:monitor"  # 运维监控查看（大盘运维子Tab）


# ════════════════════════════════════════════════════════════
# 2. 新增权限码注册表（合并到 RBAC 权限白名单）
# ════════════════════════════════════════════════════════════
# 供 RBAC 管理 API 下发前端、创建/更新角色时白名单校验
# 与 b14_constants.ALL_ADMIN_PERMISSIONS 合并使用
B13_B14_EXTRA_PERMISSIONS = [
    {"code": PERM_GOODS_MANAGE, "name": "商品后台管理", "module": "B13"},
    {"code": PERM_USER_MANAGE, "name": "C端用户管理", "module": "B13"},
    {"code": PERM_DASHBOARD_VIEW, "name": "数据大盘查看", "module": "B14"},
    # B13-1 新增权限
    {"code": PERM_ORDER_MANAGE, "name": "订单后台管理", "module": "B13-1"},
    {"code": PERM_WITHDRAW_MANAGE, "name": "提现后台管理", "module": "B13-1"},
    # B14-1 新增权限
    {"code": PERM_DASHBOARD_EXPORT, "name": "数据大盘报表导出", "module": "B14-1"},
    # M07-2 新增权限
    {"code": PERM_OPS_MONITOR, "name": "运维监控查看", "module": "M07-2"},
]


# ════════════════════════════════════════════════════════════
# 3. 商品管理扩展表状态枚举
# ════════════════════════════════════════════════════════════
class GoodsShelfStatus(str, Enum):
    """商品上下架状态（goods_management.shelf_status）"""
    ON_SHELF = "on_shelf"    # 上架（C端可展示）
    OFF_SHELF = "off_shelf"  # 下架（C端不展示）


# ════════════════════════════════════════════════════════════
# 4. 用户管理扩展表状态枚举
# ════════════════════════════════════════════════════════════
class UserAdminStatus(str, Enum):
    """C端用户管理状态（user_admin_profile.status）"""
    NORMAL = "normal"  # 正常
    FROZEN = "frozen"  # 冻结（不可提现/不可下单）


# ════════════════════════════════════════════════════════════
# 5. Redis Key 前缀（统一 gaking:prod 前缀，RedisClient.add_prefix 自动补齐）
# ════════════════════════════════════════════════════════════
# 大盘统计缓存（5 分钟 TTL，避免高频聚合查询压垮 DB）
CACHE_KEY_DASHBOARD_CARDS = "dashboard:cards"
CACHE_KEY_DASHBOARD_COMMISSION = "dashboard:commission"
CACHE_KEY_DASHBOARD_ORDER_TREND = "dashboard:order_trend"
CACHE_TTL_DASHBOARD = 300  # 5 分钟


# ════════════════════════════════════════════════════════════
# 6. 审计动作枚举（追加，与 B14 AuditAction 风格一致）
# ════════════════════════════════════════════════════════════
class B13B14AuditAction(str, Enum):
    """B13/B14 补全模块审计动作"""
    GOODS_SHELF_ON = "GOODS_SHELF_ON"        # 商品上架
    GOODS_SHELF_OFF = "GOODS_SHELF_OFF"      # 商品下架
    GOODS_BATCH_OP = "GOODS_BATCH_OP"        # 商品批量操作
    GOODS_SYNC = "GOODS_SYNC"                # 商品同步
    USER_FREEZE = "USER_FREEZE"              # 用户冻结
    USER_UNFREEZE = "USER_UNFREEZE"          # 用户解冻
    USER_REMARK = "USER_REMARK"              # 用户备注修改
    DASHBOARD_QUERY = "DASHBOARD_QUERY"      # 大盘查询
