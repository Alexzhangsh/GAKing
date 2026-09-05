# @ai-generated
"""
B08-1 用户佣金资产账户模块常量定义
新建文件，不修改 B01-B15 及 B06/B07 任何基线常量

内容：
1. B08-1 新增权限码
2. 资金流水类型枚举
3. 资金流水状态枚举
4. Redis 缓存键
"""
from enum import Enum

from src.config.constants import REDIS_PREFIX


# ════════════════════════════════════════════════════════════
# 1. B08-1 新增权限码
# ════════════════════════════════════════════════════════════
PERM_ACCOUNT_VIEW = "fund:account:view"          # 资金账户查看
PERM_ACCOUNT_CREDIT = "fund:account:credit"      # 资金账户入账
PERM_ACCOUNT_DEBIT = "fund:account:debit"        # 资金账户扣款
PERM_ACCOUNT_FREEZE = "fund:account:freeze"      # 资金账户冻结/解冻
PERM_FUND_FLOW_VIEW = "fund:flow:view"           # 资金流水查看

# B08-1 新增权限码集合
B08_1_PERMISSIONS = [
    PERM_ACCOUNT_VIEW,
    PERM_ACCOUNT_CREDIT,
    PERM_ACCOUNT_DEBIT,
    PERM_ACCOUNT_FREEZE,
    PERM_FUND_FLOW_VIEW,
]


# ════════════════════════════════════════════════════════════
# 2. 资金流水类型枚举
# ════════════════════════════════════════════════════════════
class FundFlowType(str, Enum):
    """资金流水类型"""
    DEPOSIT = "DEPOSIT"                # 入账（佣金结算/补贴入账）
    DEDUCT = "DEDUCT"                  # 扣款（退款冲减/人工扣款）
    FREEZE = "FREEZE"                  # 冻结（风控锁定/人工冻结）
    UNFREEZE = "UNFREEZE"             # 解冻（风控到期/人工解冻）
    WITHDRAW_APPLY = "WITHDRAW_APPLY"  # 提现申请冻结
    WITHDRAW_REJECT = "WITHDRAW_REJECT"  # 提现驳回退回
    WITHDRAW_SUCCESS = "WITHDRAW_SUCCESS"  # 提现成功
    REFUND_DEDUCT = "REFUND_DEDUCT"    # 退款冲减
    MANUAL_ADJUST = "MANUAL_ADJUST"    # 手工调账
    SETTLEMENT = "SETTLEMENT"          # 结算入账


FUND_FLOW_TYPE_LABELS = {
    FundFlowType.DEPOSIT: "入账",
    FundFlowType.DEDUCT: "扣款",
    FundFlowType.FREEZE: "冻结",
    FundFlowType.UNFREEZE: "解冻",
    FundFlowType.WITHDRAW_APPLY: "提现申请冻结",
    FundFlowType.WITHDRAW_REJECT: "提现驳回退回",
    FundFlowType.WITHDRAW_SUCCESS: "提现成功",
    FundFlowType.REFUND_DEDUCT: "退款冲减",
    FundFlowType.MANUAL_ADJUST: "手工调账",
    FundFlowType.SETTLEMENT: "结算入账",
}


# ════════════════════════════════════════════════════════════
# 3. Redis 缓存键
# ════════════════════════════════════════════════════════════
# 资金流水缓存键前缀（按业务ID查询）：gaking:prod:fund_flow:biz:{biz_id}
CACHE_KEY_FUND_FLOW_BIZ = f"{REDIS_PREFIX}fund_flow:biz:"
# 资金流水列表缓存键前缀（按用户查询）：gaking:prod:fund_flow:list:{user_id}
CACHE_KEY_FUND_FLOW_LIST = f"{REDIS_PREFIX}fund_flow:list:"