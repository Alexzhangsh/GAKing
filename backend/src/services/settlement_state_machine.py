# @ai-generated
"""
佣金结算状态机守护（B12 新建）
纯逻辑校验，固化不可回退流转规则：ORDERED → SETTLABLE → SETTLED → PAID
任何状态变更前必须通过本守护校验，非法流转抛 ValueError
"""
import logging

from src.config.b12_constants import (
    SETTLEMENT_TERMINAL_STATES,
    SETTLEMENT_TRANSITIONS,
    SettlementStatus,
)

logger = logging.getLogger("service.settlement_state_machine")


class SettlementStateMachine:
    """结算单状态机守护

    合法流转（严格不可回退）：
        ORDERED → SETTLABLE → SETTLED → PAID

    终态：PAID（不可再操作）
    """

    @staticmethod
    def validate_transition(from_status: str, to_status: str) -> None:
        """校验状态流转合法性，非法抛 ValueError

        Args:
            from_status: 变更前状态
            to_status: 变更后状态
        Raises:
            ValueError: 非法流转 / 未知状态
        """
        # 校验状态值合法
        valid_statuses = {s.value for s in SettlementStatus}
        if from_status not in valid_statuses:
            raise ValueError(f"未知结算单状态: from_status={from_status}")
        if to_status not in valid_statuses:
            raise ValueError(f"未知结算单状态: to_status={to_status}")

        # 相同状态不算流转
        if from_status == to_status:
            raise ValueError(f"状态未变更（不可重复操作）: status={from_status}")

        allowed = SETTLEMENT_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise ValueError(
                f"非法状态流转: {from_status} → {to_status}，"
                f"允许的下一状态: {allowed or '无（终态）'}"
            )

    @staticmethod
    def is_terminal(status: str) -> bool:
        """判断是否终态（PAID 不可再操作）"""
        return status in SETTLEMENT_TERMINAL_STATES

    @staticmethod
    def get_allowed_next(status: str) -> set:
        """获取当前状态允许的下一状态集合"""
        return SETTLEMENT_TRANSITIONS.get(status, set())

    @staticmethod
    def can_freeze(status: str) -> bool:
        """是否可执行冻结操作（ORDERED → SETTLABLE）"""
        return status == SettlementStatus.ORDERED.value

    @staticmethod
    def can_unfreeze(status: str) -> bool:
        """是否可执行解冻操作（SETTLABLE → SETTLED）"""
        return status == SettlementStatus.SETTLABLE.value

    @staticmethod
    def can_mark_paid(status: str) -> bool:
        """是否可标记已打款（SETTLED → PAID）"""
        return status == SettlementStatus.SETTLED.value
