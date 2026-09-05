# @ai-generated
"""
B06-2 渠道订单报表导出与佣金账单对账模块常量定义
新建文件，不修改 B01-B15 及 B06-1 任何基线常量

内容：
1. B06-2 新增权限码（channel:export / channel:reconciliation）
2. 导出任务状态枚举
3. 导出任务类型枚举
4. 导出文件参数限制
5. Redis 键与缓存配置
"""
from enum import Enum, IntEnum

from src.config.b14_constants import ALL_ADMIN_PERMISSIONS as _B14_PERMS
from src.config.b06_constants import B06_PERMISSIONS as _B06_PERMS


# ════════════════════════════════════════════════════════════
# 1. B06-2 新增权限码
# ════════════════════════════════════════════════════════════
PERM_CHANNEL_EXPORT = "channel:export"           # 渠道订单报表导出
PERM_CHANNEL_RECONCILIATION = "channel:reconciliation"  # 佣金账单对账

# B06-2 新增权限码集合
B06_2_PERMISSIONS = [
    PERM_CHANNEL_EXPORT,
    PERM_CHANNEL_RECONCILIATION,
]

# 全部 admin 权限码字典（B14 基线 + B06 + B06-2 新增）
ALL_ADMIN_PERMISSIONS = _B14_PERMS + _B06_PERMS + [
    {"code": PERM_CHANNEL_EXPORT, "name": "渠道订单报表导出", "module": "B06-2"},
    {"code": PERM_CHANNEL_RECONCILIATION, "name": "佣金账单对账", "module": "B06-2"},
]


# ════════════════════════════════════════════════════════════
# 2. 导出任务状态枚举
# ════════════════════════════════════════════════════════════
class ExportTaskStatus(str, Enum):
    """导出任务状态"""
    PROCESSING = "PROCESSING"  # 处理中
    SUCCESS = "SUCCESS"        # 导出成功
    FAILED = "FAILED"          # 导出失败


EXPORT_TASK_STATUS_LABELS = {
    ExportTaskStatus.PROCESSING: "处理中",
    ExportTaskStatus.SUCCESS: "导出成功",
    ExportTaskStatus.FAILED: "导出失败",
}


# ════════════════════════════════════════════════════════════
# 3. 导出任务类型枚举
# ════════════════════════════════════════════════════════════
class ExportTaskType(str, Enum):
    """导出任务类型"""
    ORDER_EXPORT = "order_export"           # 订单报表导出
    COMMISSION_BILL = "commission_bill"     # 佣金账单导出


EXPORT_TASK_TYPE_LABELS = {
    ExportTaskType.ORDER_EXPORT: "订单报表导出",
    ExportTaskType.COMMISSION_BILL: "佣金账单导出",
}


# ════════════════════════════════════════════════════════════
# 4. 导出文件参数限制
# ════════════════════════════════════════════════════════════
# 单次导出最大时间范围（天）
EXPORT_MAX_DATE_RANGE_DAYS = 31
# 单次导出最大行数
EXPORT_MAX_ROWS = 10000
# 单次导出最大文件大小（字节，50MB）
EXPORT_MAX_FILE_SIZE = 50 * 1024 * 1024
# 导出文件存放目录（相对于项目根）
EXPORT_FILE_DIR = "exports"
# 导出文件前缀
EXPORT_FILE_PREFIX = "channel_export"
# 导出文件过期时间（秒，24小时后自动清理）
EXPORT_FILE_TTL = 24 * 3600


# ════════════════════════════════════════════════════════════
# 5. 订单导出 Excel 列定义
# ════════════════════════════════════════════════════════════
ORDER_EXPORT_COLUMNS = [
    ("internal_order_no", "平台订单号"),
    ("out_order_no", "渠道订单号"),
    ("goods_title", "商品标题"),
    ("channel_code", "渠道标识"),
    ("pay_amount", "支付金额(元)"),
    ("total_commission", "总佣金(元)"),
    ("user_commission", "用户佣金(元)"),
    ("platform_commission", "平台佣金(元)"),
    ("order_status", "订单状态"),
    ("pay_time", "支付时间"),
    ("settle_time", "结算时间"),
    ("create_time", "创建时间"),
]

COMMISSION_BILL_COLUMNS = [
    ("internal_order_no", "平台订单号"),
    ("out_order_no", "渠道订单号"),
    ("user_id", "用户ID"),
    ("channel_code", "渠道标识"),
    ("flow_type", "流水类型"),
    ("amount", "流水金额(元)"),
    ("before_balance", "变更前余额(元)"),
    ("after_balance", "变更后余额(元)"),
    ("transfer_status", "转账状态"),
    ("create_time", "创建时间"),
]


# ════════════════════════════════════════════════════════════
# 6. Redis 键与缓存配置
# ════════════════════════════════════════════════════════════
from src.config.constants import REDIS_PREFIX

# 导出任务锁：gaking:prod:lock:export:{user_id}
LOCK_KEY_EXPORT = f"{REDIS_PREFIX}lock:export:"


# ════════════════════════════════════════════════════════════
# 7. 订单状态映射（Excel 导出用中文）
# ════════════════════════════════════════════════════════════
ORDER_STATUS_LABELS = {
    10: "待付款",
    20: "冻结中",
    30: "可结算",
    40: "已结算",
    50: "已失效",
    60: "已退款",
}

FLOW_TYPE_LABELS = {
    "ORDER": "订单佣金",
    "SUPPLEMENT": "补发",
    "DEDUCT": "扣减",
}

TRANSFER_STATUS_LABELS = {
    "PENDING": "待转账",
    "PROCESSING": "转账中",
    "SUCCESS": "已转账",
    "FAILED": "转账失败",
}