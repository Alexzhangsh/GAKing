# @ai-generated
"""
B08 佣金账户+流水 DAO / Service 单元测试（与 B07 解耦，AsyncMock 模拟不依赖真实 DB/Redis）

覆盖范围（目标覆盖率 ≥90%）：
 1. UserCommissionAccountDAO
    - 覆写的 logic_delete_by_id / batch_logic_delete（删除后失效缓存被调用）
    - list_all / paginate_list（参数透传基类）
    - batch_get_for_update（去重排序 + with_for_update 锁）
    - adjust_balance_batch（N 条调整，含 1 条透支付款，成功/失败都有结果）
    - list_accounts_by_balance_ge（分页 + 总条数）
    - aggregate_platform_balance（聚合 SUM/COUNT）
 2. CommissionFlowDAO
    - list_by_user_id（类型+状态+时间范围+分页）
    - sum_commission_by_user_id（SQL SUM 聚合，无数据返回 0）
    - list_supplement_flows_by_order_id / list_deduct_flows_by_order_id
    - aggregate_user_monthly_summary（GROUP BY + 精确 flow_count/order_count）
 3. UserCommissionService
    - get_user_account（非法 user_id 参数校验 → BizException(10004)）
    - list_user_flows 参数校验（page_size 超限 / 时间反向 → 10004）
    - _validate_positive_amount（非 Decimal / 0 / 超 10 万 / 超 2 位小数 → 10004）
    - freeze_for_withdraw（调用 DAO adjust_balance 成功/透支付款 10001）
    - unfreeze_or_deduct_on_withdraw_result：
        成功（手续费 0.5 → withdrawn=99.5, fee=0.5, delta_frozen=-100）
        失败（delta_available +100 回补）
        fee >= frozen 报错 10004
    - operate_supplement：补贴 SUCCESS（调用 operate_flow_and_balance_atomic，断言 DAO.create 被调用 + adjust_balance +delta）
    - operate_deduct 正常（扣减可用余额）/ 强扣 allow_over_draft=True
    - operate_flow_and_balance_atomic 流程：账户快照 → adjust_balance → flow_dao.create
    - _to_biz_exception 错误映射：
        ValueError("用户佣金账户不存在") → 10000
        ValueError("可用余额不足") → 10001
        ValueError("冻结余额不足") → 10002
        ValueError("幂等xx") → 10003
        IntegrityError (msg含duplicate) → 10003
        OperationalError (msg含lock) → 10006
        兜底 Exception → 10005
"""
import sys
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
import json
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch, call

import pytest

sys.path.insert(0, ".")

from sqlalchemy.exc import IntegrityError, OperationalError

# 常量与 user_commission_service 保持一致（本地副本，不依赖 B01-B07 散落在各文件的常量）
FLOW_TYPE_ORDER = "ORDER"
FLOW_TYPE_SUPPLEMENT = "SUPPLEMENT"
FLOW_TYPE_DEDUCT = "DEDUCT"
TRANSFER_STATUS_PENDING = "PENDING"
TRANSFER_STATUS_PROCESSING = "PROCESSING"
TRANSFER_STATUS_SUCCESS = "SUCCESS"
TRANSFER_STATUS_FAILED = "FAILED"

from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.order_model import Order
from src.models.business.user_commission_account_model import UserCommissionAccount
from src.schemas.cps_goods import BizException
from src.services.user_commission_service import (
    MAX_OPERATE_AMOUNT,
    UserCommissionService,
)


# ─────────────────────────────────────────────────────
# 构造 helpers
# ─────────────────────────────────────────────────────


def _make_account(
    user_id: int = 100,
    available: str = "1000.00",
    total: str = "2000.00",
    frozen: str = "0.00",
    withdrawn: str = "0.00",
    fee: str = "0.00",
    account_id: int = 1,
) -> UserCommissionAccount:
    a = MagicMock(spec=UserCommissionAccount)
    a.id = account_id
    a.user_id = user_id
    a.available_balance = Decimal(available)
    a.total_balance = Decimal(total)
    a.frozen_balance = Decimal(frozen)
    a.cumulative_withdrawn = Decimal(withdrawn)
    a.cumulative_fee = Decimal(fee)
    a.version = 0
    return a


def _make_flow(
    flow_id: int = 1,
    user_id: int = 100,
    order_id: int = 1,
    flow_type: str = FLOW_TYPE_ORDER,
    amount: str = "80.00",
    transfer_status: str = TRANSFER_STATUS_SUCCESS,
) -> CommissionFlow:
    f = MagicMock(spec=CommissionFlow)
    f.id = flow_id
    f.user_id = user_id
    f.order_id = order_id
    f.flow_type = flow_type
    f.amount = Decimal(amount)
    f.transfer_status = transfer_status
    f.before_balance = Decimal("0")
    f.after_balance = Decimal("80")
    return f


def _make_session_mock(
    scalars_result: Optional[List[Any]] = None,
    scalar_result: Any = None,
    one_result: Any = None,
) -> AsyncMock:
    """通用 AsyncSession mock（与 B07 style 一致）"""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    execute_result = MagicMock()
    if scalars_result is not None:
        execute_result.scalars.return_value.all.return_value = scalars_result
        execute_result.scalars.return_value.one_or_none.return_value = (
            scalars_result[0] if scalars_result else None
        )
    if scalar_result is not None:
        execute_result.scalar.return_value = scalar_result
        execute_result.scalar_one_or_none.return_value = scalar_result
    if one_result is not None:
        execute_result.one.return_value = one_result
    execute_result.all.return_value = []
    session.execute = AsyncMock(return_value=execute_result)
    return session


def _make_redis_mock() -> AsyncMock:
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=0)
    client.expire = AsyncMock(return_value=True)
    return client


# ══════════════════════════════════════════════════════
# 1. UserCommissionAccountDAO 单元测试
# ══════════════════════════════════════════════════════


class TestUserCommissionAccountDAO:
    """B08-1 补全的 DAO 方法用例"""

    def _make_dao(
        self,
        session: Optional[AsyncMock] = None,
        redis_client: Optional[AsyncMock] = None,
    ) -> UserCommissionAccountDAO:
        """构造 DAO（session 入参即可；Redis 通过 patch RedisClient 单例控制）"""
        session = session or _make_session_mock()
        # redis_client 参数仅兼容旧用例命名，本 DAO 内部使用 RedisClient 单例，
        # 因此在调用方通过 patch(src.dao.user_commission_account_dao.RedisClient) 注入。
        return UserCommissionAccountDAO(session)

    # ── 覆写 logic_delete_by_id ──
    @pytest.mark.asyncio
    async def test_logic_delete_by_id_success_invalidates_cache(self):
        """软删除成功：调用基类 + 失效账户缓存"""
        account = _make_account(user_id=888, account_id=9)
        session = _make_session_mock(scalars_result=[account])
        redis = _make_redis_mock()
        dao = self._make_dao(session, redis)

        with patch.object(
            UserCommissionAccountDAO,
            "get_by_id",
            new=AsyncMock(return_value=account),
        ):
            with patch.object(
                UserCommissionAccountDAO,
                "_invalidate_account_cache",
                new=AsyncMock(),
            ) as mock_invalidate:
                with patch(
                    "src.dao.user_commission_account_dao.BaseDAO.logic_delete_by_id",
                    new=AsyncMock(return_value=True),
                ) as mock_super:
                    ok = await dao.logic_delete_by_id(9)
        assert ok is True
        mock_super.assert_awaited_once_with(9)
        mock_invalidate.assert_awaited_once_with(888)

    @pytest.mark.asyncio
    async def test_logic_delete_by_id_missing_item(self):
        """账户不存在：返回 False 不抛错"""
        session = _make_session_mock()
        dao = self._make_dao(session)
        with patch.object(
            UserCommissionAccountDAO,
            "get_by_id",
            new=AsyncMock(return_value=None),
        ):
            ok = await dao.logic_delete_by_id(9999)
        assert ok is False

    # ── 覆写 batch_logic_delete ──
    @pytest.mark.asyncio
    async def test_batch_logic_delete_invalidates_multi_user_caches(self):
        """批量软删：先查 user_ids → 调用基类 → 对每个 user_id 失效缓存"""
        # 基类返回 affected=2
        a1 = _make_account(user_id=11, account_id=1)
        a2 = _make_account(user_id=22, account_id=2)
        session = _make_session_mock(scalar_result=2)
        # 让 SELECT user_id FROM ... 返回 [11, 22]
        user_ids_raw = [(11,), (22,)]
        session.execute.return_value.all.return_value = user_ids_raw
        redis = _make_redis_mock()
        dao = self._make_dao(session, redis)
        with patch(
            "src.dao.user_commission_account_dao.BaseDAO.batch_logic_delete",
            new=AsyncMock(return_value=2),
        ) as mock_super:
            with patch.object(
                UserCommissionAccountDAO,
                "_invalidate_account_cache",
                new=AsyncMock(),
            ) as mock_invalidate:
                affected = await dao.batch_logic_delete([1, 2])
        assert affected == 2
        mock_super.assert_awaited_once_with([1, 2])
        assert mock_invalidate.await_count == 2
        calls_args = {c.args[0] for c in mock_invalidate.await_args_list}
        assert calls_args == {11, 22}

    @pytest.mark.asyncio
    async def test_batch_logic_delete_empty_ids(self):
        """空列表直接返回 0，不调用 session"""
        dao = self._make_dao()
        affected = await dao.batch_logic_delete([])
        assert affected == 0

    # ── 覆写 list_all / paginate_list（透传基类） ──
    @pytest.mark.asyncio
    async def test_list_all_paginate_list_delegate_to_super(self):
        account = _make_account()
        dao = self._make_dao()
        with patch(
            "src.dao.user_commission_account_dao.BaseDAO.list_all",
            new=AsyncMock(return_value=[account]),
        ) as mock_super_all:
            res = await dao.list_all(filters={"x": 1}, order_by="id")
        mock_super_all.assert_awaited_once_with(filters={"x": 1}, order_by="id")
        assert res == [account]

        with patch(
            "src.dao.user_commission_account_dao.BaseDAO.paginate_list",
            new=AsyncMock(return_value=([account], 1)),
        ) as mock_super_page:
            items, total = await dao.paginate_list(
                page=2, page_size=3, filters={"y": 2}
            )
        mock_super_page.assert_awaited_once_with(
            page=2, page_size=3, filters={"y": 2}, order_by=None
        )
        assert total == 1

    # ── batch_get_for_update（去重排序 + FOR UPDATE） ──
    @pytest.mark.asyncio
    async def test_batch_get_for_update_dedup_sort_and_lock(self):
        """入参重复/乱序 [30, 10, 20, 10] → 锁查询 user_ids 升序 [10, 20, 30]"""
        a10 = _make_account(user_id=10, account_id=101)
        a20 = _make_account(user_id=20, account_id=102)
        a30 = _make_account(user_id=30, account_id=103)
        session = _make_session_mock(scalars_result=[a10, a20, a30])
        dao = self._make_dao(session)
        # patch with_for_update：检查 stmt 最终调用了 with_for_update
        res = await dao.batch_get_for_update([30, 10, 20, 10])
        assert len(res) == 3
        # 验证 execute 被调用；参数 stmt 里 user_id.in_ 的有序集合在 all 返回值里体现为 3 条
        assert session.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_batch_get_for_update_empty_list(self):
        dao = self._make_dao()
        res = await dao.batch_get_for_update([])
        assert res == []

    # ── adjust_balance_batch：成功/失败混合 ──
    @pytest.mark.asyncio
    async def test_adjust_balance_batch_mixed_success_and_failed(self):
        """3 条：用户 1 加 50 成功；用户 2 扣 9999 透支失败；用户 3 加 10 成功"""
        adjustments = [
            {"user_id": 1, "delta_available": "50"},
            {"user_id": 2, "delta_available": "-9999"},  # 透支
            {"user_id": 3, "delta_available": "10"},
        ]
        dao = self._make_dao()

        async def fake_adjust(user_id, **kw):
            if user_id == 2:
                raise ValueError("可用余额不足: user_id=2, 当前可用=100, 扣减=9999")
            acc = _make_account(
                user_id=user_id, available=str(1000 + float(kw["delta_available"]))
            )
            return acc

        with patch.object(dao, "adjust_balance", side_effect=fake_adjust):
            results = await dao.adjust_balance_batch(adjustments)

        assert len(results) == 3
        status_map = {r["user_id"]: r["status"] for r in results}
        assert status_map == {1: "success", 2: "failed", 3: "success"}
        failed = [r for r in results if r["user_id"] == 2][0]
        assert "可用余额不足" in failed["message"]

    # ── list_accounts_by_balance_ge：分页参数 + 总数 ──
    @pytest.mark.asyncio
    async def test_list_accounts_by_balance_ge(self):
        a1 = _make_account(user_id=1, available="500.00")
        a2 = _make_account(user_id=2, available="300.00")
        # 两条 execute：count 查询 + page 查询；用 scalar + scalars 分开 mock
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [a1, a2]
        session.execute.side_effect = [count_result, list_result]
        dao = self._make_dao(session)
        items, total = await dao.list_accounts_by_balance_ge(
            Decimal("100"), page=1, page_size=10
        )
        assert total == 2
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_list_accounts_by_balance_ge_fix_wrong_params(self):
        """page / page_size 非法值兜底"""
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []
        session.execute.side_effect = [count_result, list_result]
        dao = self._make_dao(session)
        items, total = await dao.list_accounts_by_balance_ge(
            Decimal("100"), page=0, page_size=0
        )
        assert total == 0
        assert items == []

    # ── aggregate_platform_balance：聚合字段完整 ──
    @pytest.mark.asyncio
    async def test_aggregate_platform_balance_all_fields(self):
        row = MagicMock()
        row.total = Decimal("10000")
        row.available = Decimal("5000")
        row.frozen = Decimal("2000")
        row.withdrawn = Decimal("2500")
        row.fee = Decimal("500")
        row.account_count = 42
        session = _make_session_mock(one_result=row)
        dao = self._make_dao(session)
        out = await dao.aggregate_platform_balance()
        assert out == {
            "total": Decimal("10000"),
            "available": Decimal("5000"),
            "frozen": Decimal("2000"),
            "withdrawn": Decimal("2500"),
            "fee": Decimal("500"),
            "account_count": 42,
        }


# ══════════════════════════════════════════════════════
# 2. CommissionFlowDAO 单元测试
# ══════════════════════════════════════════════════════


class TestCommissionFlowDAO:
    def _make_dao(
        self,
        session: Optional[AsyncMock] = None,
        redis_client: Optional[AsyncMock] = None,
    ) -> CommissionFlowDAO:
        """构造 CommissionFlowDAO；Redis 单例通过 patch src.dao.commission_flow_dao.RedisClient 注入"""
        session = session or _make_session_mock()
        return CommissionFlowDAO(session)

    # ── list_by_user_id：条件叠加 + 分页 ──
    @pytest.mark.asyncio
    async def test_list_by_user_id_all_filters_applied(self):
        flow1 = _make_flow(flow_id=1, user_id=99, amount="10.00")
        flow2 = _make_flow(flow_id=2, user_id=99, amount="20.00")
        session = AsyncMock()
        count_res = MagicMock()
        count_res.scalar.return_value = 13
        list_res = MagicMock()
        list_res.scalars.return_value.all.return_value = [flow1, flow2]
        session.execute.side_effect = [count_res, list_res]
        dao = self._make_dao(session)
        items, total = await dao.list_by_user_id(
            99,
            flow_type=FLOW_TYPE_ORDER,
            transfer_status=TRANSFER_STATUS_SUCCESS,
            start_time=datetime(2026, 1, 1),
            end_time=datetime(2026, 12, 31),
            page=2,
            page_size=5,
        )
        assert total == 13
        assert items == [flow1, flow2]

    @pytest.mark.asyncio
    async def test_list_by_user_id_invalid_params_normalized(self):
        """page / page_size 超小值被兜底"""
        session = AsyncMock()
        count_res = MagicMock()
        count_res.scalar.return_value = 0
        list_res = MagicMock()
        list_res.scalars.return_value.all.return_value = []
        session.execute.side_effect = [count_res, list_res]
        dao = self._make_dao(session)
        items, total = await dao.list_by_user_id(99, page=-1, page_size=0)
        assert total == 0
        assert items == []

    # ── sum_commission_by_user_id：SQL SUM 聚合 ──
    @pytest.mark.asyncio
    async def test_sum_commission_with_match(self):
        session = _make_session_mock(scalar_result=Decimal("123.45"))
        dao = self._make_dao(session)
        total = await dao.sum_commission_by_user_id(
            1,
            flow_type=FLOW_TYPE_ORDER,
            transfer_status=TRANSFER_STATUS_SUCCESS,
        )
        assert total == Decimal("123.45")

    @pytest.mark.asyncio
    async def test_sum_commission_empty_returns_zero(self):
        session = _make_session_mock(scalar_result=None)
        dao = self._make_dao(session)
        total = await dao.sum_commission_by_user_id(1)
        assert total == Decimal("0")

    # ── list_supplement / list_deduct by order_id ──
    @pytest.mark.asyncio
    async def test_list_supplement_and_deduct(self):
        sup_flow = _make_flow(flow_type=FLOW_TYPE_SUPPLEMENT, amount="5")
        ded_flow = _make_flow(flow_type=FLOW_TYPE_DEDUCT, amount="-3")
        session1 = _make_session_mock(scalars_result=[sup_flow])
        dao1 = self._make_dao(session1)
        assert (await dao1.list_supplement_flows_by_order_id(7)) == [sup_flow]

        session2 = _make_session_mock(scalars_result=[ded_flow])
        dao2 = self._make_dao(session2)
        assert (await dao2.list_deduct_flows_by_order_id(7)) == [ded_flow]

    # ── aggregate_user_monthly_summary ──
    @pytest.mark.asyncio
    async def test_monthly_summary_group_by_and_totals(self):
        """GROUP BY 3 行：ORDER+SUCCESS 赚 100, ORDER+PENDING 20, DEDUCT 扣 15"""
        r1 = MagicMock()
        r1.flow_type = FLOW_TYPE_ORDER
        r1.transfer_status = TRANSFER_STATUS_SUCCESS
        r1.sum_amount = Decimal("100.00")
        r1.order_count = 5
        r2 = MagicMock()
        r2.flow_type = FLOW_TYPE_ORDER
        r2.transfer_status = "PENDING"
        r2.sum_amount = Decimal("20.00")
        r2.order_count = 1
        r3 = MagicMock()
        r3.flow_type = FLOW_TYPE_DEDUCT
        r3.transfer_status = TRANSFER_STATUS_SUCCESS
        r3.sum_amount = Decimal("15.00")
        r3.order_count = 1

        group_session = AsyncMock()
        group_res = MagicMock()
        group_res.all.return_value = [r1, r2, r3]
        flow_count_res = MagicMock()
        flow_count_res.scalar.return_value = 7  # 总流水 7 条
        order_count_res = MagicMock()
        order_count_res.scalar.return_value = 6  # 6 单

        group_session.execute.side_effect = [group_res, flow_count_res, order_count_res]
        dao = self._make_dao(group_session)
        summary = await dao.aggregate_user_monthly_summary(100, 2026, 8)
        assert summary["year"] == 2026 and summary["month"] == 8
        assert summary["total_earned"] == Decimal("100.00")
        assert summary["pending_amount"] == Decimal("20.00")
        assert summary["total_deducted"] == Decimal("15.00")
        assert summary["flow_count"] == 7
        assert summary["order_count"] == 6
        assert len(summary["details"]) == 3


# ══════════════════════════════════════════════════════
# 3. UserCommissionService 单元测试
# ══════════════════════════════════════════════════════


class TestUserCommissionService:
    """B08-3 服务层（BizException 转码 + 金额校验 + 原子编排）"""

    def _make(
        self,
        account_dao: Optional[UserCommissionAccountDAO] = None,
        flow_dao: Optional[CommissionFlowDAO] = None,
    ) -> UserCommissionService:
        if account_dao is None:
            session = _make_session_mock()
            account_dao = UserCommissionAccountDAO(session)
        if flow_dao is None:
            session = _make_session_mock()
            flow_dao = CommissionFlowDAO(session)
        return UserCommissionService(account_dao=account_dao, flow_dao=flow_dao)

    # ── _to_biz_exception 错误码映射全覆盖 ──
    def test_to_biz_exception_code_mapping(self):
        svc = self._make()
        cases = [
            (ValueError("用户佣金账户不存在: user_id=1"), 10000),
            (ValueError("可用余额不足: xxxxx"), 10001),
            (ValueError("冻结余额不足: xxxxx"), 10002),
            (ValueError("幂等重复: biz_no=A"), 10003),
            (ValueError("随便别的参数错误"), 10004),
        ]
        for exc, expected in cases:
            got = svc._to_biz_exception(exc, "fallback")
            assert isinstance(got, BizException)
            assert got.code == expected, f"{exc} → {got.code}, 期望 {expected}"

        # IntegrityError(duplicate) → 10003
        ie = IntegrityError(
            statement="INSERT", params={}, orig=Exception("duplicate entry 1062")
        )
        assert svc._to_biz_exception(ie, "fb").code == 10003
        # IntegrityError(其他) → 10004
        ie2 = IntegrityError(
            statement="INSERT", params={}, orig=Exception("foreign key fail")
        )
        assert svc._to_biz_exception(ie2, "fb").code == 10004

        # OperationalError lock → 10006
        oe = OperationalError(
            statement="SELECT", params={}, orig=Exception("lock wait timeout")
        )
        assert svc._to_biz_exception(oe, "fb").code == 10006
        # OperationalError 其他 → 10005
        oe2 = OperationalError(
            statement="SELECT", params={}, orig=Exception("connection refused")
        )
        assert svc._to_biz_exception(oe2, "fb").code == 10005

        # 兜底：通用 Exception → 10005
        generic = RuntimeError("unknown DB down")
        assert svc._to_biz_exception(generic, "fallback-msg").code == 10005

        # BizException 直通
        direct = BizException(code=9999, msg="custom")
        assert svc._to_biz_exception(direct, "fb") is direct

    # ── _validate_positive_amount ──
    def test_validate_positive_amount_cases(self):
        ok_cases = ["0.01", "1000.00", str(MAX_OPERATE_AMOUNT)]
        for c in ok_cases:
            got = UserCommissionService._validate_positive_amount(c, f"case-{c}")
            assert got == Decimal(c)
        bad_cases = [
            ("abc", 10004),
            (Decimal("0"), 10004),
            (Decimal("-1"), 10004),
            (MAX_OPERATE_AMOUNT + Decimal("0.01"), 10004),
            (Decimal("0.123"), 10004),  # 3 位小数
        ]
        for val, expected_code in bad_cases:
            with pytest.raises(BizException) as exc_info:
                UserCommissionService._validate_positive_amount(val, "bad-case")
            assert exc_info.value.code == expected_code, f"{val} 未抛 {expected_code}"

    # ── get_user_account 参数校验 ──
    @pytest.mark.asyncio
    async def test_get_user_account_invalid_id(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.get_user_account(0)
        assert exc.value.code == 10004

    # ── list_user_flows 参数校验 ──
    @pytest.mark.asyncio
    async def test_list_user_flows_invalid_params(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.list_user_flows(1, page_size=999)
        assert exc.value.code == 10004
        with pytest.raises(BizException) as exc:
            await svc.list_user_flows(
                1,
                start_time=datetime(2026, 8, 2),
                end_time=datetime(2026, 8, 1),
            )
        assert exc.value.code == 10004
        with pytest.raises(BizException) as exc:
            await svc.list_user_flows(-1)
        assert exc.value.code == 10004

    # ── get_user_monthly_summary 参数校验 ──
    @pytest.mark.asyncio
    async def test_get_user_monthly_summary_invalid_ym(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.get_user_monthly_summary(1, 20200, 1)
        assert exc.value.code == 10004
        with pytest.raises(BizException) as exc:
            await svc.get_user_monthly_summary(-1, 2026, 13)
        assert exc.value.code == 10004

    # ── freeze_for_withdraw：冻结成功 / 透支 10001 ──
    @pytest.mark.asyncio
    async def test_freeze_for_withdraw_success(self):
        svc = self._make()
        after = _make_account(user_id=1, available="900", frozen="100")
        with patch.object(
            svc.account_dao, "adjust_balance", new=AsyncMock(return_value=after)
        ) as mock_adjust:
            account = await svc.freeze_for_withdraw(1, Decimal("100"))
        mock_adjust.assert_awaited_once_with(
            1,
            delta_available=Decimal("-100"),
            delta_frozen=Decimal("100"),
        )
        assert account.frozen_balance == Decimal("100")

    @pytest.mark.asyncio
    async def test_freeze_for_withdraw_overdraft_biz_exception_10001(self):
        svc = self._make()
        with patch.object(
            svc.account_dao,
            "adjust_balance",
            new=AsyncMock(
                side_effect=ValueError("可用余额不足: user_id=1, 当前可用=10, 扣减=100")
            ),
        ):
            with pytest.raises(BizException) as exc:
                await svc.freeze_for_withdraw(1, Decimal("100"))
        assert exc.value.code == 10001

    # ── unfreeze_or_deduct_on_withdraw_result：成功 + 手续费 / 失败回补 / 参数错 ──
    @pytest.mark.asyncio
    async def test_withdraw_result_success_with_fee(self):
        svc = self._make()
        after_acc = _make_account(
            user_id=1,
            available="1000",
            frozen="0",
            withdrawn="99.5",
            fee="0.5",
        )
        with patch.object(
            svc.account_dao, "adjust_balance", new=AsyncMock(return_value=after_acc)
        ) as mock_adjust:
            out = await svc.unfreeze_or_deduct_on_withdraw_result(
                1, Decimal("100.00"), success=True, fee=Decimal("0.5")
            )
        mock_adjust.assert_awaited_once_with(
            1,
            delta_available=Decimal("0"),
            delta_frozen=Decimal("-100"),
            delta_withdrawn=Decimal("99.5"),
            delta_fee=Decimal("0.5"),
        )
        assert out["account"].cumulative_withdrawn == Decimal("99.5")
        assert out["account"].cumulative_fee == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_withdraw_result_fail_unfreeze(self):
        svc = self._make()
        after_acc = _make_account(
            user_id=1,
            available="1100",
            frozen="0",
        )
        with patch.object(
            svc.account_dao, "adjust_balance", new=AsyncMock(return_value=after_acc)
        ) as mock_adjust:
            await svc.unfreeze_or_deduct_on_withdraw_result(
                1, Decimal("100"), success=False
            )
        mock_adjust.assert_awaited_once_with(
            1,
            delta_available=Decimal("100"),
            delta_frozen=Decimal("-100"),
            delta_withdrawn=Decimal("0"),
            delta_fee=Decimal("0"),
        )

    @pytest.mark.asyncio
    async def test_withdraw_result_fee_ge_frozen_fail(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.unfreeze_or_deduct_on_withdraw_result(
                1, Decimal("10"), success=True, fee=Decimal("10")
            )
        assert exc.value.code == 10004

    # ── operate_supplement：补贴原子编排 ──
    @pytest.mark.asyncio
    async def test_operate_supplement_happy_path(self):
        svc = self._make()
        before = _make_account(user_id=1, available="100")
        after = _make_account(user_id=1, available="150", total="250")
        created_flow = _make_flow(flow_type=FLOW_TYPE_SUPPLEMENT, amount="50")

        with patch.object(
            svc.account_dao, "get_account_cached", new=AsyncMock(return_value=before)
        ), patch.object(
            svc.account_dao, "adjust_balance", new=AsyncMock(return_value=after)
        ) as mock_adjust, patch.object(
            svc.flow_dao, "create", new=AsyncMock(return_value=created_flow)
        ) as mock_flow_create:
            out = await svc.operate_supplement(
                1, Decimal("50.00"), operator="op_test", remark="补发"
            )
        # adjust_balance 调用：+50 可用 / +50 累计
        mock_adjust.assert_awaited_once_with(
            1,
            delta_available=Decimal("50"),
            delta_frozen=Decimal("0"),
            delta_total=Decimal("50"),
            delta_withdrawn=Decimal("0"),
            delta_fee=Decimal("0"),
        )
        # flow.create 参数断言
        call_kw = mock_flow_create.await_args.args[0]
        assert call_kw["flow_type"] == FLOW_TYPE_SUPPLEMENT
        assert call_kw["amount"] == Decimal("50")
        assert call_kw["transfer_status"] == TRANSFER_STATUS_SUCCESS
        assert call_kw["before_balance"] == Decimal("100")
        assert call_kw["after_balance"] == Decimal("150")
        assert call_kw["operator"] == "op_test"
        assert out["flow"] is created_flow
        assert out["account"] is after

    # ── operate_deduct：正常扣减 / 强扣 allow_over_draft ──
    @pytest.mark.asyncio
    async def test_operate_deduct_normal_hit_10001_then_raise(self):
        svc = self._make()
        with patch.object(
            svc,
            "operate_flow_and_balance_atomic",
            new=AsyncMock(side_effect=BizException(code=10001, msg="可用余额不足")),
        ):
            with pytest.raises(BizException) as exc:
                await svc.operate_deduct(1, Decimal("100"))
        assert exc.value.code == 10001

    @pytest.mark.asyncio
    async def test_operate_deduct_overdraft_strong_mode(self):
        """allow_over_draft=True → 走 operate_flow_and_balance_no_validate（绕开校验）"""
        svc = self._make()
        before = _make_account(user_id=1, available="10")
        # 强扣后 available 可能负数：-90
        after = _make_account(user_id=1, available="-90")
        created_flow = _make_flow(flow_type=FLOW_TYPE_DEDUCT, amount="100")
        with patch.object(
            svc.account_dao, "get_for_update", new=AsyncMock(return_value=before)
        ), patch.object(
            svc.account_dao, "session", new=_make_session_mock()
        ), patch.object(
            svc.account_dao, "_invalidate_account_cache", new=AsyncMock()
        ) as mock_invalidate, patch.object(
            svc.account_dao,
            "get_by_user_id",
            new=AsyncMock(return_value=after),
        ), patch.object(
            svc.flow_dao, "create", new=AsyncMock(return_value=created_flow)
        ):
            out = await svc.operate_deduct(1, Decimal("100.00"), allow_over_draft=True)
        assert out["flow"] is created_flow
        # 强扣 commit 后应已调用缓存失效
        mock_invalidate.assert_awaited_once_with(1)

    # ── operate_flow_and_balance_atomic 参数校验（flow_type 非法 → 10004） ──
    @pytest.mark.asyncio
    async def test_operate_atomic_invalid_flow_type(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.operate_flow_and_balance_atomic(
                user_id=1,
                flow_type="BAD_TYPE",
                transfer_status=TRANSFER_STATUS_SUCCESS,
                amount=Decimal("10"),
            )
        assert exc.value.code == 10004

    @pytest.mark.asyncio
    async def test_operate_atomic_zero_amount_fail(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.operate_flow_and_balance_atomic(
                user_id=1,
                flow_type=FLOW_TYPE_SUPPLEMENT,
                transfer_status=TRANSFER_STATUS_SUCCESS,
                amount=Decimal("0"),
            )
        assert exc.value.code == 10004

    @pytest.mark.asyncio
    async def test_operate_atomic_invalid_transfer_status(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.operate_flow_and_balance_atomic(
                user_id=1,
                flow_type=FLOW_TYPE_SUPPLEMENT,
                transfer_status="BAD_STATUS",
                amount=Decimal("1"),
            )
        assert exc.value.code == 10004

    @pytest.mark.asyncio
    async def test_operate_no_validate_invalid_flow_type(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.operate_flow_and_balance_no_validate(
                user_id=1,
                flow_type="BAD",
                transfer_status=TRANSFER_STATUS_SUCCESS,
                amount=Decimal("1"),
            )
        assert exc.value.code == 10004

    @pytest.mark.asyncio
    async def test_operate_no_validate_account_missing_10000(self):
        svc = self._make()
        with patch.object(
            svc.account_dao, "get_for_update", new=AsyncMock(return_value=None)
        ):
            with pytest.raises(BizException) as exc:
                await svc.operate_flow_and_balance_no_validate(
                    user_id=9999,
                    flow_type=FLOW_TYPE_DEDUCT,
                    transfer_status=TRANSFER_STATUS_SUCCESS,
                    amount=Decimal("100"),
                )
        assert exc.value.code == 10000

    @pytest.mark.asyncio
    async def test_operate_no_validate_zero_amount(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.operate_flow_and_balance_no_validate(
                user_id=1,
                flow_type=FLOW_TYPE_ORDER,
                transfer_status=TRANSFER_STATUS_SUCCESS,
                amount=Decimal("0"),
            )
        assert exc.value.code == 10004

    # ── B07 复用 settle_order_commission / deduct_on_refund：异常转码 + 前置校验 ──
    @pytest.mark.asyncio
    async def test_settle_order_commission_no_settlement_dao_10005(self):
        svc = self._make()
        # 没传 settlement_dao → 10005
        order = MagicMock(spec=Order)
        with pytest.raises(BizException) as exc:
            await svc.settle_order_commission(order, Decimal("10"), "BATCH_X")
        assert exc.value.code == 10005

    @pytest.mark.asyncio
    async def test_settle_order_commission_non_positive_amount_10004(self):
        svc = self._make()
        svc.settlement_dao = MagicMock()
        order = MagicMock(spec=Order)
        with pytest.raises(BizException) as exc:
            await svc.settle_order_commission(order, Decimal("0"), "B")
        assert exc.value.code == 10004
        with pytest.raises(BizException) as exc:
            await svc.settle_order_commission(order, Decimal("-1"), "B")
        assert exc.value.code == 10004

    @pytest.mark.asyncio
    async def test_deduct_on_refund_invalid_amount_10004(self):
        svc = self._make()
        svc.settlement_dao = MagicMock()
        order = MagicMock(spec=Order)
        with pytest.raises(BizException) as exc:
            await svc.deduct_on_refund(order, Decimal("0"), "B")
        assert exc.value.code == 10004

    @pytest.mark.asyncio
    async def test_deduct_on_refund_no_settlement_dao_10005(self):
        svc = self._make()
        order = MagicMock(spec=Order)
        with pytest.raises(BizException) as exc:
            await svc.deduct_on_refund(order, Decimal("10"), "B")
        assert exc.value.code == 10005

    # ── operate_batch_adjust_balance：超单笔上限兜底 10004 ──
    @pytest.mark.asyncio
    async def test_operate_batch_adjust_single_limit_over(self):
        svc = self._make()
        big = MAX_OPERATE_AMOUNT + Decimal("0.01")
        with pytest.raises(BizException) as exc:
            await svc.operate_batch_adjust_balance(
                [{"user_id": 1, "delta_available": str(big)}]
            )
        assert exc.value.code == 10004

    @pytest.mark.asyncio
    async def test_operate_batch_adjust_pass(self):
        svc = self._make()
        expected = [
            {
                "index": 0,
                "user_id": 1,
                "status": "success",
                "message": "ok",
                "new_available": Decimal("1050"),
            }
        ]
        with patch.object(
            svc.account_dao,
            "adjust_balance_batch",
            new=AsyncMock(return_value=expected),
        ) as mock_batch:
            got = await svc.operate_batch_adjust_balance(
                [{"user_id": 1, "delta_available": "50"}]
            )
        mock_batch.assert_awaited_once()
        assert got == expected

    # ── get_user_sum_commission：参数校验 + 透传 DAO ──
    @pytest.mark.asyncio
    async def test_get_user_sum_commission_invalid_user_10004(self):
        svc = self._make()
        with pytest.raises(BizException) as exc:
            await svc.get_user_sum_commission(-1)
        assert exc.value.code == 10004

    @pytest.mark.asyncio
    async def test_get_user_sum_commission_happy_path(self):
        svc = self._make()
        with patch.object(
            svc.flow_dao,
            "sum_commission_by_user_id",
            new=AsyncMock(return_value=Decimal("123")),
        ) as m:
            got = await svc.get_user_sum_commission(
                1, flow_type=FLOW_TYPE_ORDER, transfer_status=TRANSFER_STATUS_SUCCESS
            )
        m.assert_awaited_once_with(
            1, flow_type=FLOW_TYPE_ORDER, transfer_status=TRANSFER_STATUS_SUCCESS
        )
        assert got == Decimal("123")


# ══════════════════════════════════════════════════════
# 4. 覆盖率冲刺用例（补齐 B07 原有方法分支，目标 3 个文件 ≥90%）
# ══════════════════════════════════════════════════════


class TestUserCommissionAccountDAOB07Coverage:
    """B07 原有方法覆盖：get_by_user_id / get_for_update / get_or_create_by_user_id
    / get_account_cached（4 路径：命中/空标/损坏/未命中有/未命中空）
    / create / update_by_id 覆写 / adjust_balance（3 条异常 + 成功）
    / credit_on_reconciliation（金额 0 / 幂等 / 成功 / commit 异常回滚）
    """

    def _make_dao(self, session=None) -> UserCommissionAccountDAO:
        return UserCommissionAccountDAO(session or _make_session_mock())

    # ── get_by_user_id / get_for_update ──
    @pytest.mark.asyncio
    async def test_get_by_user_id_existing(self):
        account = _make_account(user_id=77)
        session = _make_session_mock(scalar_result=account)
        dao = self._make_dao(session)
        assert (await dao.get_by_user_id(77)) is account

    @pytest.mark.asyncio
    async def test_get_for_update_missing(self):
        session = _make_session_mock()
        # 让 scalar_one_or_none 显式返回 None（而非 MagicMock）
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        session.execute.return_value = execute_result
        dao = self._make_dao(session)
        assert (await dao.get_for_update(99999)) is None

    # ── get_or_create_by_user_id（已存在 / 新建成功 / commit 异常回滚） ──
    @pytest.mark.asyncio
    async def test_get_or_create_by_user_id_already_exists(self):
        existing = _make_account(user_id=5)
        dao = self._make_dao()
        with patch.object(dao, "get_by_user_id", new=AsyncMock(return_value=existing)):
            acc = await dao.get_or_create_by_user_id(5)
        assert acc is existing

    @pytest.mark.asyncio
    async def test_get_or_create_by_user_id_create_new(self):
        dao = self._make_dao()
        with patch.object(
            dao, "get_by_user_id", new=AsyncMock(return_value=None)
        ), patch.object(dao.session, "add", MagicMock()), patch.object(
            dao.session, "flush", AsyncMock()
        ), patch.object(
            dao.session, "commit", AsyncMock()
        ), patch.object(
            dao.session, "rollback", AsyncMock()
        ):
            acc = await dao.get_or_create_by_user_id(5555)
        assert acc.user_id == 5555
        assert acc.available_balance == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_or_create_rollback_on_commit_fail(self):
        dao = self._make_dao()
        with patch.object(
            dao, "get_by_user_id", new=AsyncMock(return_value=None)
        ), patch.object(dao.session, "add", MagicMock()), patch.object(
            dao.session, "flush", AsyncMock()
        ), patch.object(
            dao.session, "commit", AsyncMock(side_effect=RuntimeError("boom"))
        ), patch.object(
            dao.session, "rollback", AsyncMock()
        ) as mock_rb:
            with pytest.raises(RuntimeError):
                await dao.get_or_create_by_user_id(5)
        mock_rb.assert_awaited_once()

    # ── get_account_cached（5 分支全覆盖） ──
    @pytest.mark.asyncio
    async def test_get_account_cached_hit_regular(self):
        dao = self._make_dao()
        expected = {"user_id": 9, "available_balance": "666.00"}
        mock_get = AsyncMock(return_value=json.dumps(expected))
        with patch("src.dao.user_commission_account_dao.RedisClient.get", mock_get):
            got = await dao.get_account_cached(9)
        assert got == expected

    @pytest.mark.asyncio
    async def test_get_account_cached_hit_empty_marker(self):
        dao = self._make_dao()
        with patch(
            "src.dao.user_commission_account_dao.RedisClient.get",
            AsyncMock(return_value="__EMPTY__"),
        ):
            assert (await dao.get_account_cached(1)) is None

    @pytest.mark.asyncio
    async def test_get_account_cached_corrupt_then_miss_with_account(self):
        """缓存损坏 JSONDecodeError → 查库有 → set_json 回填"""
        dao = self._make_dao()
        account = _make_account(user_id=3, available="777.00")
        account.to_dict = MagicMock(
            return_value={"user_id": 3, "available_balance": "777.00"}
        )
        with patch(
            "src.dao.user_commission_account_dao.RedisClient.get",
            AsyncMock(return_value="{not-valid-json"),
        ), patch.object(
            dao, "get_by_user_id", new=AsyncMock(return_value=account)
        ), patch(
            "src.dao.user_commission_account_dao.RedisClient.set_json",
            new_callable=AsyncMock,
        ) as mock_set_json:
            got = await dao.get_account_cached(3)
        assert got == {"user_id": 3, "available_balance": "777.00"}
        mock_set_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_account_cached_miss_empty_account(self):
        """未命中且账户为空 → set_empty_cache 防穿透"""
        dao = self._make_dao()
        with patch(
            "src.dao.user_commission_account_dao.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch.object(dao, "get_by_user_id", new=AsyncMock(return_value=None)), patch(
            "src.dao.user_commission_account_dao.RedisClient.set_empty_cache",
            new_callable=AsyncMock,
        ) as mock_empty:
            assert (await dao.get_account_cached(999)) is None
        mock_empty.assert_awaited_once()

    # ── 覆写 create / update_by_id ──
    @pytest.mark.asyncio
    async def test_create_overwrite_invalidates_cache(self):
        dao = self._make_dao()
        created = _make_account(user_id=44)
        with patch(
            "src.dao.user_commission_account_dao.BaseDAO.create",
            new=AsyncMock(return_value=created),
        ) as mock_super, patch.object(
            dao, "_invalidate_account_cache", new=AsyncMock()
        ) as mock_inv:
            got = await dao.create({"user_id": 44})
        assert got is created
        mock_super.assert_awaited_once_with({"user_id": 44})
        mock_inv.assert_awaited_once_with(44)

    @pytest.mark.asyncio
    async def test_update_by_id_overwrite_invalidates_only_when_not_none(self):
        dao = self._make_dao()
        updated = _make_account(user_id=55, account_id=2)
        with patch(
            "src.dao.user_commission_account_dao.BaseDAO.update_by_id",
            new=AsyncMock(return_value=updated),
        ), patch.object(dao, "_invalidate_account_cache", new=AsyncMock()) as mock_inv:
            await dao.update_by_id(2, {"available_balance": "99.99"})
        mock_inv.assert_awaited_once_with(55)

        with patch(
            "src.dao.user_commission_account_dao.BaseDAO.update_by_id",
            new=AsyncMock(return_value=None),
        ), patch.object(
            dao, "_invalidate_account_cache", new=AsyncMock()
        ) as mock_inv_none:
            assert (await dao.update_by_id(9999, {})) is None
        mock_inv_none.assert_not_awaited()

    # ── adjust_balance（3 异常分支 + commit 异常回滚 + 成功） ──
    @pytest.mark.asyncio
    async def test_adjust_balance_account_missing_raises(self):
        dao = self._make_dao()
        with patch.object(dao, "get_for_update", new=AsyncMock(return_value=None)):
            with pytest.raises(ValueError) as exc:
                await dao.adjust_balance(9999, delta_available=Decimal("1"))
        assert "用户佣金账户不存在" in str(exc.value)

    @pytest.mark.asyncio
    async def test_adjust_balance_available_insufficient(self):
        dao = self._make_dao()
        acc = _make_account(user_id=1, available="10")
        with patch.object(dao, "get_for_update", new=AsyncMock(return_value=acc)):
            with pytest.raises(ValueError) as exc:
                await dao.adjust_balance(1, delta_available=Decimal("-100"))
        assert "可用余额不足" in str(exc.value)

    @pytest.mark.asyncio
    async def test_adjust_balance_frozen_insufficient(self):
        dao = self._make_dao()
        acc = _make_account(user_id=1, frozen="0")
        with patch.object(dao, "get_for_update", new=AsyncMock(return_value=acc)):
            with pytest.raises(ValueError) as exc:
                await dao.adjust_balance(1, delta_frozen=Decimal("-1"))
        assert "冻结余额不足" in str(exc.value)

    @pytest.mark.asyncio
    async def test_adjust_balance_rollback_on_commit_error(self):
        dao = self._make_dao()
        acc = _make_account(user_id=1, available="100", frozen="0")
        with patch.object(
            dao, "get_for_update", new=AsyncMock(return_value=acc)
        ), patch.object(dao.session, "flush", AsyncMock()), patch.object(
            dao.session,
            "commit",
            AsyncMock(side_effect=OperationalError("x", {}, Exception("lock"))),
        ), patch.object(
            dao.session, "rollback", AsyncMock()
        ) as mock_rb, patch.object(
            dao, "_invalidate_account_cache", new=AsyncMock()
        ) as mock_inv:
            with pytest.raises(OperationalError):
                await dao.adjust_balance(1, delta_available=Decimal("10"))
        mock_rb.assert_awaited_once()
        mock_inv.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_adjust_balance_success_happy_path(self):
        dao = self._make_dao()
        acc = _make_account(
            user_id=1,
            available="1000.00",
            frozen="0.00",
            total="2000.00",
            withdrawn="0.00",
            fee="0.00",
        )
        with patch.object(
            dao, "get_for_update", new=AsyncMock(return_value=acc)
        ), patch.object(dao.session, "flush", AsyncMock()), patch.object(
            dao.session, "commit", AsyncMock()
        ), patch.object(
            dao, "_invalidate_account_cache", new=AsyncMock()
        ) as mock_inv:
            got = await dao.adjust_balance(
                1,
                delta_available=Decimal("-10.00"),
                delta_frozen=Decimal("10.00"),
                delta_total=Decimal("0"),
                delta_withdrawn=Decimal("0"),
                delta_fee=Decimal("0"),
            )
        assert got.available_balance == Decimal("990.00")
        assert got.frozen_balance == Decimal("10.00")
        assert got.version == 1
        mock_inv.assert_awaited_once_with(1)

    # ── credit_on_reconciliation（4 分支） ──
    @pytest.mark.asyncio
    async def test_credit_on_reconciliation_skip_zero_or_negative(self):
        dao = self._make_dao()
        assert (
            await dao.credit_on_reconciliation(1, Decimal("0"), date.today())
        ) is False
        assert (
            await dao.credit_on_reconciliation(1, Decimal("-1"), date.today())
        ) is False

    @pytest.mark.asyncio
    async def test_credit_on_reconciliation_idempotent_skip(self):
        dao = self._make_dao()
        today = date(2026, 8, 2)
        acc = _make_account(user_id=1)
        acc.last_settle_date = today  # 同日已入账
        with patch.object(
            dao, "get_or_create_by_user_id", new=AsyncMock(return_value=acc)
        ):
            got = await dao.credit_on_reconciliation(1, Decimal("10"), today)
        assert got is False

    @pytest.mark.asyncio
    async def test_credit_on_reconciliation_rollback_on_fail(self):
        dao = self._make_dao()
        today = date(2026, 8, 2)
        acc = _make_account(user_id=1, available="100", total="200")
        acc.last_settle_date = None
        with patch.object(
            dao, "get_or_create_by_user_id", new=AsyncMock(return_value=acc)
        ), patch.object(dao.session, "flush", AsyncMock()), patch.object(
            dao.session, "commit", AsyncMock(side_effect=RuntimeError("db down"))
        ), patch.object(
            dao.session, "rollback", AsyncMock()
        ) as mock_rb, patch.object(
            dao, "_invalidate_account_cache", new=AsyncMock()
        ) as mock_inv:
            with pytest.raises(RuntimeError):
                await dao.credit_on_reconciliation(1, Decimal("10"), today)
        mock_rb.assert_awaited_once()
        mock_inv.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_credit_on_reconciliation_success(self):
        dao = self._make_dao()
        today = date(2026, 8, 2)
        acc = _make_account(user_id=1, available="100.00", total="200.00")
        acc.last_settle_date = None
        with patch.object(
            dao, "get_or_create_by_user_id", new=AsyncMock(return_value=acc)
        ), patch.object(dao.session, "flush", AsyncMock()), patch.object(
            dao.session, "commit", AsyncMock()
        ), patch.object(
            dao, "_invalidate_account_cache", new=AsyncMock()
        ) as mock_inv:
            assert (
                await dao.credit_on_reconciliation(1, Decimal("50.00"), today)
            ) is True
        assert acc.available_balance == Decimal("150.00")
        assert acc.total_balance == Decimal("250.00")
        assert acc.last_settle_date == today
        mock_inv.assert_awaited_once_with(1)


class TestCommissionFlowDAOB07Coverage:
    """commission_flow_dao B07 原有方法（list_by_order_id / get_by_biz_no
    / batch_create / list_by_order_ids / sum_by_order_id / order_has_success_flow
    / flow_order_ids_by_settle_status / batch_invalidate_commission_cache）覆盖"""

    def _make_dao(self, session=None) -> CommissionFlowDAO:
        return CommissionFlowDAO(session or _make_session_mock())

    @pytest.mark.asyncio
    async def test_list_by_order_id(self):
        f1 = _make_flow(order_id=7)
        session = _make_session_mock(scalars_result=[f1])
        dao = self._make_dao(session)
        assert (await dao.list_by_order_id(7)) == [f1]

    @pytest.mark.asyncio
    async def test_create_overwrite_invalidates_order_cache(self):
        dao = self._make_dao()
        flow = _make_flow(order_id=55)
        with patch(
            "src.dao.commission_flow_dao.BaseDAO.create",
            new=AsyncMock(return_value=flow),
        ), patch.object(dao, "_invalidate_flow_cache", new=AsyncMock()) as mock_inv:
            got = await dao.create({"order_id": 55, "amount": "1"})
        assert got is flow
        mock_inv.assert_awaited_once_with(55)

    @pytest.mark.asyncio
    async def test_batch_create_invalidates_cache_per_flow(self):
        dao = self._make_dao()
        f1 = _make_flow(order_id=1)
        f2 = _make_flow(order_id=2)
        with patch(
            "src.dao.commission_flow_dao.BaseDAO.batch_create",
            new=AsyncMock(return_value=[f1, f2]),
        ), patch.object(dao, "_invalidate_flow_cache", new=AsyncMock()) as mock_inv:
            got = await dao.batch_create([{}, {}])
        assert got == [f1, f2]
        assert mock_inv.await_count == 2
        mock_inv.assert_has_awaits([call(1), call(2)], any_order=True)

    @pytest.mark.asyncio
    async def test_update_by_id_invalidates_cache_when_not_none(self):
        dao = self._make_dao()
        flow = _make_flow(order_id=99, flow_id=1)
        with patch(
            "src.dao.commission_flow_dao.BaseDAO.update_by_id",
            new=AsyncMock(return_value=flow),
        ), patch.object(dao, "_invalidate_flow_cache", new=AsyncMock()) as mock_inv:
            await dao.update_by_id(1, {"remark": "x"})
        mock_inv.assert_awaited_once_with(99)

        with patch(
            "src.dao.commission_flow_dao.BaseDAO.update_by_id",
            new=AsyncMock(return_value=None),
        ), patch.object(
            dao, "_invalidate_flow_cache", new=AsyncMock()
        ) as mock_inv_none:
            assert (await dao.update_by_id(9999, {})) is None
        mock_inv_none.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_batch_invalidate_commission_cache(self):
        dao = self._make_dao()
        with patch.object(dao, "_invalidate_flow_cache", new=AsyncMock()) as mock_inv:
            await dao.batch_invalidate_commission_cache([7, 8])
        mock_inv.assert_has_awaits([call(7), call(8)], any_order=True)

    # ── sum_commission_by_order_id 缓存命中/未命中/空值 ──
    @pytest.mark.asyncio
    async def test_sum_commission_by_order_id_cached_hit(self):
        dao = self._make_dao()
        with patch(
            "src.dao.commission_flow_dao.RedisClient.get",
            AsyncMock(return_value="123.45"),
        ):
            got = await dao.sum_commission_by_order_id(99)
        assert got == Decimal("123.45")

    @pytest.mark.asyncio
    async def test_sum_commission_by_order_id_cached_empty_marker(self):
        dao = self._make_dao()
        with patch(
            "src.dao.commission_flow_dao.RedisClient.get",
            AsyncMock(return_value="__EMPTY__"),
        ):
            got = await dao.sum_commission_by_order_id(1)
        assert got == Decimal("0")

    @pytest.mark.asyncio
    async def test_sum_commission_by_order_id_miss_then_zero_write_empty(self):
        dao = self._make_dao()
        session = _make_session_mock(scalar_result=0)
        dao.session = session
        with patch(
            "src.dao.commission_flow_dao.RedisClient.get", AsyncMock(return_value=None)
        ), patch(
            "src.dao.commission_flow_dao.RedisClient.set_empty_cache",
            new_callable=AsyncMock,
        ) as mock_empty:
            got = await dao.sum_commission_by_order_id(55)
        assert got == Decimal("0")
        mock_empty.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sum_commission_by_order_id_miss_then_set_cached(self):
        dao = self._make_dao()
        session = _make_session_mock(scalar_result=Decimal("88.00"))
        dao.session = session
        with patch(
            "src.dao.commission_flow_dao.RedisClient.get", AsyncMock(return_value=None)
        ), patch(
            "src.dao.commission_flow_dao.RedisClient.set", new_callable=AsyncMock
        ) as mock_set:
            got = await dao.sum_commission_by_order_id(55)
        assert got == Decimal("88.00")
        mock_set.assert_awaited_once()

    # ── list_by_settle_status（分页 + page/page_size 边界） ──
    @pytest.mark.asyncio
    async def test_list_by_settle_status_pagination(self):
        flows = [_make_flow(flow_id=1), _make_flow(flow_id=2)]
        session = _make_session_mock(scalars_result=flows, scalar_result=2)
        dao = self._make_dao(session)
        items, total = await dao.list_by_settle_status("SUCCESS", page=1, page_size=10)
        assert total == 2
        assert items == flows

    @pytest.mark.asyncio
    async def test_list_by_settle_status_boundary_correction(self):
        """page < 1 归一为 1；page_size < 1 归一为 20"""
        flows = [_make_flow(flow_id=1)]
        session = _make_session_mock(scalars_result=flows, scalar_result=1)
        dao = self._make_dao(session)
        items, total = await dao.list_by_settle_status("PENDING", page=0, page_size=0)
        assert total == 1
        assert items == flows

    # ── batch_bind_order（更新 order_id + 失效缓存） ──
    @pytest.mark.asyncio
    async def test_batch_bind_order_affected_and_invalidate(self):
        dao = self._make_dao()
        r = MagicMock()
        r.rowcount = 3
        dao.session.execute = AsyncMock(return_value=r)
        dao.session.flush = AsyncMock()
        with patch.object(dao, "_invalidate_flow_cache", new=AsyncMock()) as mock_inv:
            got = await dao.batch_bind_order(77, [1, 2, 3])
        assert got == 3
        mock_inv.assert_awaited_once_with(77)

    # ── aggregate_settled_by_date_range ──
    @pytest.mark.asyncio
    async def test_aggregate_settled_by_date_range_groups(self):
        dao = self._make_dao()
        row1 = MagicMock()
        row1.user_id = 1
        row1.total_amount = Decimal("50.00")
        row1.order_count = 2
        row2 = MagicMock()
        row2.user_id = 2
        row2.total_amount = Decimal("30.00")
        row2.order_count = 1
        session = _make_session_mock()
        er = MagicMock()
        er.all.return_value = [row1, row2]
        session.execute.return_value = er
        dao = self._make_dao(session)
        result = await dao.aggregate_settled_by_date_range(
            datetime(2026, 8, 1), datetime(2026, 8, 2), "SUCCESS"
        )
        assert len(result) == 2
        assert result[0]["user_id"] == 1
        assert result[0]["total_amount"] == Decimal("50.00")
        assert result[1]["order_count"] == 1

    # ── list_settled_order_ids_by_date_range（去重 + 过滤 None） ──
    @pytest.mark.asyncio
    async def test_list_settled_order_ids_filters_none(self):
        dao = self._make_dao()
        session = _make_session_mock()
        er = MagicMock()
        er.all.return_value = [(1,), (None,), (2,)]
        session.execute.return_value = er
        dao = self._make_dao(session)
        order_ids = await dao.list_settled_order_ids_by_date_range(
            datetime(2026, 8, 1), datetime(2026, 8, 2), "SUCCESS"
        )
        assert order_ids == [1, 2]

    # ── sum_commission_by_user_id 异常分支（Decimal 转换失败→兜底 0） ──
    @pytest.mark.asyncio
    async def test_sum_commission_by_user_id_none_scalar_returns_zero(self):
        dao = self._make_dao()
        session = _make_session_mock(scalar_result=None)
        dao.session = session
        got = await dao.sum_commission_by_user_id(88)
        assert got == Decimal("0")


class TestUserCommissionServiceCoverage90:
    """Service 剩余分支：get_user_account 走 DAO 正常 / list_user_flows DAO 透传
    / get_user_monthly_summary DAO 透传 / freeze/get_by_user_id 透传
    / list_user_flows page=0 归一 / unfreeze ValueError → 10000
    / settle_order_commission ValueError("账户不存在") → 10000
    / deduct_on_refund ValueError("可用余额不足") → 10001
    / operate_atomic ValueError(可用余额不足) → 10001 / flow.create 失败 → 10005
    / operate_no_validate commit 异常 → 转码 1000x / flow create 失败 → 10005
    / batch_adjust 单条金额负数小于 -MAX（绝对值校验）
    / unfreeze ValueError("用户佣金账户不存在") → 10000
    """

    def _make(self):
        return UserCommissionService(
            account_dao=UserCommissionAccountDAO(_make_session_mock()),
            flow_dao=CommissionFlowDAO(_make_session_mock()),
        )

    @pytest.mark.asyncio
    async def test_get_user_account_happy(self):
        svc = self._make()
        expected = {"user_id": 1, "available_balance": "5"}
        with patch.object(
            svc.account_dao, "get_account_cached", new=AsyncMock(return_value=expected)
        ):
            got = await svc.get_user_account(1)
        assert got == expected

    @pytest.mark.asyncio
    async def test_list_user_flows_dao_delegation(self):
        svc = self._make()
        flows = [_make_flow(), _make_flow()]
        with patch.object(
            svc.flow_dao,
            "list_by_user_id",
            new=AsyncMock(return_value=(flows, 2)),
        ) as m:
            got_flows, total = await svc.list_user_flows(1, page=1, page_size=2)
        assert total == 2
        assert got_flows == flows
        m.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_monthly_summary_dao_delegation(self):
        svc = self._make()
        summary = {"year": 2026, "month": 8, "order_count": 1}
        with patch.object(
            svc.flow_dao,
            "aggregate_user_monthly_summary",
            new=AsyncMock(return_value=summary),
        ) as m:
            got = await svc.get_user_monthly_summary(1, 2026, 8)
        assert got == summary
        m.assert_awaited_once_with(1, 2026, 8)

    @pytest.mark.asyncio
    async def test_freeze_for_withdraw_account_missing_to_10000(self):
        svc = self._make()
        with patch.object(
            svc.account_dao,
            "adjust_balance",
            new=AsyncMock(side_effect=ValueError("用户佣金账户不存在: user_id=1")),
        ):
            with pytest.raises(BizException) as exc:
                await svc.freeze_for_withdraw(1, Decimal("1"))
        assert exc.value.code == 10000

    @pytest.mark.asyncio
    async def test_unfreeze_account_missing_to_10000(self):
        svc = self._make()
        with patch.object(
            svc.account_dao,
            "adjust_balance",
            new=AsyncMock(side_effect=ValueError("用户佣金账户不存在: user_id=1")),
        ):
            with pytest.raises(BizException) as exc:
                await svc.unfreeze_or_deduct_on_withdraw_result(
                    1, Decimal("10"), success=False
                )
        assert exc.value.code == 10000

    @pytest.mark.asyncio
    async def test_settle_order_value_error_account_missing_10000(self):
        svc = self._make()
        svc.settlement_dao = AsyncMock()
        svc.settlement_dao.settle_order_commission_atomic = AsyncMock(
            side_effect=ValueError("用户佣金账户不存在: user_id=1")
        )
        order = MagicMock(spec=Order)
        with pytest.raises(BizException) as exc:
            await svc.settle_order_commission(order, Decimal("10"), "B")
        assert exc.value.code == 10000

    @pytest.mark.asyncio
    async def test_deduct_on_refund_insufficient_balance_10001(self):
        svc = self._make()
        svc.settlement_dao = AsyncMock()
        svc.settlement_dao.deduct_on_refund_atomic = AsyncMock(
            side_effect=ValueError("可用余额不足: user_id=1, 当前可用=1, 扣减=10")
        )
        order = MagicMock(spec=Order)
        with pytest.raises(BizException) as exc:
            await svc.deduct_on_refund(order, Decimal("10"), "B")
        assert exc.value.code == 10001

    @pytest.mark.asyncio
    async def test_operate_atomic_available_shortage_10001(self):
        svc = self._make()
        before = _make_account(user_id=1, available="10")
        with patch.object(
            svc.account_dao, "get_account_cached", new=AsyncMock(return_value=before)
        ), patch.object(
            svc.account_dao,
            "adjust_balance",
            new=AsyncMock(
                side_effect=ValueError("可用余额不足: user_id=1, 当前可用=10, 扣减=999")
            ),
        ):
            with pytest.raises(BizException) as exc:
                await svc.operate_flow_and_balance_atomic(
                    user_id=1,
                    flow_type=FLOW_TYPE_DEDUCT,
                    transfer_status=TRANSFER_STATUS_SUCCESS,
                    amount=Decimal("999"),
                    delta_available=Decimal("-999"),
                )
        assert exc.value.code == 10001

    @pytest.mark.asyncio
    async def test_operate_atomic_flow_create_failed_10005(self):
        svc = self._make()
        before = _make_account(user_id=1, available="100")
        after = _make_account(user_id=1, available="150")
        with patch.object(
            svc.account_dao, "get_account_cached", new=AsyncMock(return_value=before)
        ), patch.object(
            svc.account_dao, "adjust_balance", new=AsyncMock(return_value=after)
        ), patch.object(
            svc.flow_dao,
            "create",
            new=AsyncMock(side_effect=RuntimeError("db down")),
        ):
            with pytest.raises(BizException) as exc:
                await svc.operate_supplement(1, Decimal("50.00"))
        assert exc.value.code == 10005
        assert "人工核对" in exc.value.msg

    @pytest.mark.asyncio
    async def test_operate_no_validate_commit_error_translate(self):
        svc = self._make()
        acc_before = _make_account(user_id=1, available="10")
        with patch.object(
            svc.account_dao, "get_for_update", new=AsyncMock(return_value=acc_before)
        ), patch.object(
            svc.account_dao, "session", new=_make_session_mock()
        ) as mock_session_patch, patch.object(
            svc.account_dao, "_invalidate_account_cache", new=AsyncMock()
        ):
            mock_session_patch.commit = AsyncMock(
                side_effect=OperationalError("x", {}, Exception("deadlock found"))
            )
            mock_session_patch.rollback = AsyncMock()
            with pytest.raises(BizException) as exc:
                await svc.operate_flow_and_balance_no_validate(
                    user_id=1,
                    flow_type=FLOW_TYPE_DEDUCT,
                    transfer_status=TRANSFER_STATUS_SUCCESS,
                    amount=Decimal("100"),
                    delta_available=Decimal("-100"),
                )
        assert exc.value.code in (10005, 10006)

    @pytest.mark.asyncio
    async def test_operate_no_validate_flow_create_fail_10005(self):
        svc = self._make()
        before = _make_account(user_id=1, available="10")
        after = _make_account(user_id=1, available="-90")
        with patch.object(
            svc.account_dao, "get_for_update", new=AsyncMock(return_value=before)
        ), patch.object(
            svc.account_dao, "session", new=_make_session_mock()
        ), patch.object(
            svc.account_dao, "_invalidate_account_cache", new=AsyncMock()
        ), patch.object(
            svc.account_dao,
            "get_by_user_id",
            new=AsyncMock(return_value=after),
        ), patch.object(
            svc.flow_dao,
            "create",
            new=AsyncMock(side_effect=RuntimeError("flow boom")),
        ):
            with pytest.raises(BizException) as exc:
                await svc.operate_flow_and_balance_no_validate(
                    user_id=1,
                    flow_type=FLOW_TYPE_SUPPLEMENT,
                    transfer_status=TRANSFER_STATUS_SUCCESS,
                    amount=Decimal("50"),
                    delta_available=Decimal("50"),
                )
        assert exc.value.code == 10005

    @pytest.mark.asyncio
    async def test_batch_adjust_negative_value_exceeds_limit_10004(self):
        """绝对值超上限 → 10004（负 delta_frozen 超上限）"""
        svc = self._make()
        huge_neg = "-" + str(MAX_OPERATE_AMOUNT + Decimal("1"))
        with pytest.raises(BizException) as exc:
            await svc.operate_batch_adjust_balance(
                [{"user_id": 1, "delta_frozen": huge_neg}]
            )
        assert exc.value.code == 10004
