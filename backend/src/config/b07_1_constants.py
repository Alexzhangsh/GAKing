# @ai-generated
"""
B07-1 退款逆向佣金冲减服务常量定义
新建文件，不修改 B01-B15 及 B06 任何基线常量

内容：
1. B07-1 新增权限码
2. 逆向冲减记录状态枚举
3. 定时任务参数
4. Redis 锁与缓存键
"""
from enum import Enum


# ════════════════════════════════════════════════════════════
# 1. B07-1 新增权限码
# ════════════════════════════════════════════════════════════
PERM_REVERSE_COMMISSION = "reverse:commission"  # 逆向佣金冲减管理

# B07-1 新增权限码集合
B07_1_PERMISSIONS = [
    PERM_REVERSE_COMMISSION,
]


# ════════════════════════════════════════════════════════════
# 2. 逆向冲减记录状态枚举
# ════════════════════════════════════════════════════════════
class ReverseCommissionStatus(str, Enum):
    """逆向冲减记录状态"""
    IDENTIFIED = "IDENTIFIED"            # 已识别（待处理）
    FROZEN = "FROZEN"                    # 已冻结（执行中）
    CLAWBACK_DONE = "CLAWBACK_DONE"      # 回扣完成
    FAILED = "FAILED"                    # 冲减失败（可重试）
    ADJUSTED = "ADJUSTED"                # 已手动调整


REVERSE_STATUS_LABELS = {
    ReverseCommissionStatus.IDENTIFIED: "已识别",
    ReverseCommissionStatus.FROZEN: "已冻结",
    ReverseCommissionStatus.CLAWBACK_DONE: "回扣完成",
    ReverseCommissionStatus.FAILED: "冲减失败",
    ReverseCommissionStatus.ADJUSTED: "已手动调整",
}


# ════════════════════════════════════════════════════════════
# 3. 定时任务参数
# ════════════════════════════════════════════════════════════
# 逆向冲减定时任务开关
TASK_REVERSE_COMMISSION_ENABLE = True
# 逆向冲减定时任务 cron 表达式（每30分钟）
TASK_CRON_REVERSE_COMMISSION = "*/30 * * * *"
# 分布式锁超时时间（秒）
TASK_REVERSE_COMMISSION_LOCK_TIMEOUT = 120
# 单次批量处理最大条数
TASK_REVERSE_COMMISSION_BATCH_SIZE = 50
# 单条记录最大重试次数
MAX_RETRY_COUNT = 3
# 自动冲减操作人标识
SYSTEM_OPERATOR_ID = 0
SYSTEM_OPERATOR_NAME = "系统自动"


# ════════════════════════════════════════════════════════════
# 4. Redis 锁与缓存键
# ════════════════════════════════════════════════════════════
from src.config.constants import REDIS_PREFIX

# 逆向冲减分布式锁
LOCK_KEY_REVERSE_COMMISSION = f"{REDIS_PREFIX}lock:reverse_commission:"
# 逆向冲减扫描游标
CACHE_KEY_REVERSE_SCAN_CURSOR = f"{REDIS_PREFIX}cache:reverse_scan_cursor"