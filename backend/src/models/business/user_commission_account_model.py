# @ai-generated
"""
用户佣金账户表 ORM 模型
表名：user_commission_account
业务说明：平台用户佣金资产聚合账户，记录可用/冻结/累计佣金/累计提现/累计手续费
余额联动规则：
  - 发起提现：available_balance -= apply_amount，frozen_balance += apply_amount
  - 驳回/打款失败：available_balance += apply_amount，frozen_balance -= apply_amount
  - 打款完成：frozen_balance -= apply_amount，cumulative_withdrawn += actual_amount，cumulative_fee += fee
  - 对账入账：available_balance += amount，total_balance += amount
余额变动全部数据库事务包裹，Decimal 精确计算；commit 后失效 Redis 缓存。
id / is_delete / create_time / update_time 由 Base 基类统一提供。
"""
from sqlalchemy import Column, BigInteger, Numeric, Integer, Date, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class UserCommissionAccount(Base, SerializableMixin, SoftDeleteMixin):
    """用户佣金账户表"""

    __tablename__ = "user_commission_account"
    __table_args__ = (
        # user_id 单值索引 —— 按用户查询账户
        Index("idx_user_id", "user_id"),
        {
            "comment": "用户佣金账户表",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 平台用户ID（与 orders.user_id / commission_flow.user_id 一致）
    user_id = Column(BigInteger, nullable=False, comment="平台用户ID")
    # 累计已结算佣金(元)：对账任务入账时累加
    total_balance = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="累计已结算佣金(元)"
    )
    # 可用余额(元)：可提现金额
    available_balance = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="可用余额(元)，可提现"
    )
    # 冻结余额(元)：待审核提现申请锁定的金额（提现锁定金额语义，非风险保证金）
    frozen_balance = Column(
        Numeric(10, 2),
        default=0.00,
        nullable=False,
        comment="冻结余额(元)，待审核提现锁定",
    )
    # 累计成功提现金额(元，实际到账 = actual_amount 累计)
    cumulative_withdrawn = Column(
        Numeric(10, 2),
        default=0.00,
        nullable=False,
        comment="累计成功提现金额(元，实际到账)",
    )
    # 累计手续费(元)
    cumulative_fee = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="累计手续费(元)"
    )
    # 最近一次对账入账日期（幂等防重复入账：同日重跑跳过）
    last_settle_date = Column(
        Date, nullable=True, comment="最近一次对账入账日期（幂等防重复入账）"
    )
    # 乐观锁版本号（余额变更递增）；实际写操作优先用 SELECT...FOR UPDATE 悲观锁
    version = Column(
        Integer, default=0, nullable=False, comment="乐观锁版本号（余额变更递增）"
    )

    # ── 远期需求埋点备注（本期不实现，仅注释不编码）─────────────────────────
    # TODO(远期-V2.1): 20% 佣金保证金冻结 + 订单结算 30 天冷静期自动释放
    #   1. 计划新增字段 margin_balance Numeric(10,2) default 0「风险保证金冻结余额」，
    #      与 frozen_balance（提现审核锁定）语义分离，互不混淆；
    #   2. 佣金结算入账（对账任务 credit_on_reconciliation）时：按 20% 冻结至
    #      margin_balance，仅 80% 计入 available_balance（可提现）；
    #   3. 新增独立定时任务扫描「结算满 30 天」的保证金，自动释放
    #      margin_balance → available_balance，并生成保证金释放流水；
    #   4. 提现可用余额校验改为 available_balance（不含 margin_balance），
    #      保证金冻结期间不可提现，冷静期满释放后方可提现；
    #   5. 本期 frozen_balance 仅用于提现审核锁定，保证金逻辑上线前
    #      margin_balance 字段不创建（避免空字段污染 schema）。
