# @ai-generated
"""
X02-1 会员套餐管理模块专属常量
独立文件，不修改 B01-B15 任何基线常量
"""
from decimal import Decimal


# ── 权限码 ────────────────────────────────────────────────────
PERM_MEMBER_MANAGE = "member:manage"  # 会员套餐管理（套餐 CRUD + 上下架）
PERM_MEMBER_VIEW = "member:view"  # 会员数据查看（会员记录查询）
PERM_MEMBER_EXPORT = "member:export"  # 会员数据导出

X02_1_PERMISSIONS = [
    PERM_MEMBER_MANAGE,
    PERM_MEMBER_VIEW,
    PERM_MEMBER_EXPORT,
]

# ── 套餐上下架状态 ────────────────────────────────────────────
PACKAGE_STATUS_ON = 1  # 上架
PACKAGE_STATUS_OFF = 0  # 下架
PACKAGE_STATUS_LABELS = {
    PACKAGE_STATUS_ON: "上架",
    PACKAGE_STATUS_OFF: "下架",
}

# ── 会员记录状态 ──────────────────────────────────────────────
MEMBER_STATUS_ACTIVE = "active"  # 生效中
MEMBER_STATUS_EXPIRED = "expired"  # 已到期
MEMBER_STATUS_REVOKED = "revoked"  # 已撤销
MEMBER_STATUS_LABELS = {
    MEMBER_STATUS_ACTIVE: "生效中",
    MEMBER_STATUS_EXPIRED: "已到期",
    MEMBER_STATUS_REVOKED: "已撤销",
}

# ── 会员状态定时刷新任务 ──────────────────────────────────────
# 每 30 分钟执行一次（与既有 B12-1 巡检频率一致）
TASK_CRON_MEMBER_STATUS_REFRESH = "*/30 * * * *"
TASK_MEMBER_STATUS_REFRESH_ENABLE = True  # 任务开关
TASK_MEMBER_STATUS_REFRESH_LOCK_TIMEOUT = 300  # 分布式锁超时（秒）
LOCK_KEY_MEMBER_STATUS_REFRESH = "member_status_refresh:"

# ── 导出限制 ──────────────────────────────────────────────────
MEMBER_EXPORT_MAX_ROWS = 1000  # 单次导出最大行数
