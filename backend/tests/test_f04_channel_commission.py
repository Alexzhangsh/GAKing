# @ai-generated
"""
F04-2 渠道佣金策略管理 API 单元测试
覆盖：
1. 序列化：策略/阶梯
2. Schema 校验：比例 0~1 区间、双比例之和=100%、阶梯区间、用户类型
3. 策略 CRUD：list/get/create/update/toggle
4. 分佣预览：命中阶梯/未命中/策略停用/非法参数
5. 审计记录查询
6. 阶梯匹配算法 _match_tier

覆盖率目标：API 路由层 ≥90%
"""
import sys
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from fastapi.responses import JSONResponse


def _unwrap(resp):
    """将 JSONResponse 解包为 dict 供测试断言"""
    if isinstance(resp, JSONResponse):
        return json.loads(resp.body)
    return resp


from src.api.v1.admin.f04_channel_commission import (
    TierItem,
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyToggleRequest,
    CommissionPreviewRequest,
    list_strategies,
    get_strategy,
    create_strategy,
    update_strategy,
    toggle_strategy,
    preview_commission,
    list_strategy_audit_logs,
    _serialize_strategy,
    _serialize_tier,
    _match_tier,
    ACTION_STRATEGY_CREATE,
    ACTION_STRATEGY_UPDATE,
    ACTION_STRATEGY_TOGGLE,
)
from src.models.system.f04_channel_commission import (
    ChannelCommissionStrategy,
    ChannelCommissionTier,
)


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_strategy(
    channel_code: str = "myq",
    strategy_name: str = "2026年Q3阶梯佣金",
    enabled: bool = True,
    tier_dimension: int = 1,
    remark: str = "测试策略",
    strategy_id: int = 1,
):
    """构造 ChannelCommissionStrategy mock 对象"""
    s = MagicMock(spec=ChannelCommissionStrategy)
    s.id = strategy_id
    s.channel_code = channel_code
    s.strategy_name = strategy_name
    s.enabled = enabled
    s.tier_dimension = tier_dimension
    s.remark = remark
    s.is_delete = False
    s.create_time = datetime(2026, 8, 1, 10, 0, 0)
    s.update_time = datetime(2026, 8, 14, 10, 0, 0)
    return s


def _make_tier(
    strategy_id: int = 1,
    user_type: int = 1,
    tier_name: str = "基础档",
    tier_min: float = 0,
    tier_max: float = 0,
    user_commission_rate: float = 0.8,
    platform_retention_rate: float = 0.2,
    sort_order: int = 0,
    tier_id: int = 1,
):
    """构造 ChannelCommissionTier mock 对象"""
    t = MagicMock(spec=ChannelCommissionTier)
    t.id = tier_id
    t.strategy_id = strategy_id
    t.user_type = user_type
    t.tier_name = tier_name
    t.tier_min = tier_min
    t.tier_max = tier_max
    t.user_commission_rate = user_commission_rate
    t.platform_retention_rate = platform_retention_rate
    t.sort_order = sort_order
    t.is_delete = False
    t.create_time = datetime(2026, 8, 1, 10, 0, 0)
    t.update_time = datetime(2026, 8, 14, 10, 0, 0)
    return t


def _make_request():
    """构造 FastAPI Request mock"""
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.url = MagicMock()
    request.url.path = "/api/v1/admin/channel-commission/strategies"
    return request


def _make_session_cm():
    """构造 DatabaseManager.get_session() 上下文管理器 mock"""
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


def _tier_payload(user_type=1, user_rate=0.8, platform_rate=0.2, tier_min=0, tier_max=0):
    """构造 TierItem 请求数据"""
    return {
        "user_type": user_type,
        "tier_name": "基础档",
        "tier_min": tier_min,
        "tier_max": tier_max,
        "user_commission_rate": user_rate,
        "platform_retention_rate": platform_rate,
        "sort_order": 0,
    }


# ══════════════════════════════════════════════════════
# 1. 序列化测试
# ══════════════════════════════════════════════════════


class TestSerialize:
    """序列化测试"""

    def test_serialize_strategy_full(self):
        s = _make_strategy()
        data = _serialize_strategy(s)
        assert data["channel_code"] == "myq"
        assert data["strategy_name"] == "2026年Q3阶梯佣金"
        assert data["enabled"] is True
        assert data["tier_dimension"] == 1
        assert data["tier_dimension_label"] == "按订单金额"
        assert data["create_time"] == "2026-08-01 10:00:00"

    def test_serialize_strategy_count_dimension(self):
        s = _make_strategy(tier_dimension=2)
        data = _serialize_strategy(s)
        assert data["tier_dimension_label"] == "按订单数量"

    def test_serialize_strategy_disabled(self):
        s = _make_strategy(enabled=False)
        data = _serialize_strategy(s)
        assert data["enabled"] is False

    def test_serialize_tier_full(self):
        t = _make_tier()
        data = _serialize_tier(t)
        assert data["user_type"] == 1
        assert data["user_type_label"] == "普通用户"
        assert data["user_commission_rate"] == 0.8
        assert data["platform_retention_rate"] == 0.2
        assert data["tier_max"] == 0.0

    def test_serialize_tier_vip(self):
        t = _make_tier(user_type=2)
        data = _serialize_tier(t)
        assert data["user_type_label"] == "付费会员"


# ══════════════════════════════════════════════════════
# 2. Schema 校验测试
# ══════════════════════════════════════════════════════


class TestSchemaValidation:
    """Schema 校验测试"""

    def test_tier_valid(self):
        t = TierItem(**_tier_payload())
        assert t.user_commission_rate == 0.8
        assert t.platform_retention_rate == 0.2

    def test_tier_rate_out_of_range(self):
        """比例超出 0~1 区间 → 校验失败"""
        with pytest.raises(Exception):
            TierItem(**_tier_payload(user_rate=1.5))

    def test_tier_rate_negative(self):
        """比例负数 → 校验失败"""
        with pytest.raises(Exception):
            TierItem(**_tier_payload(user_rate=-0.1))

    def test_tier_sum_not_one(self):
        """双比例之和 != 1 → 校验失败"""
        with pytest.raises(Exception):
            TierItem(**_tier_payload(user_rate=0.8, platform_rate=0.3))

    def test_tier_invalid_range(self):
        """阶梯下限 >= 上限 → 校验失败"""
        with pytest.raises(Exception):
            TierItem(**_tier_payload(tier_min=100, tier_max=50))

    def test_tier_unlimited_max_zero(self):
        """tier_max=0 表示无上限，合法"""
        t = TierItem(**_tier_payload(tier_min=100, tier_max=0))
        assert t.tier_max == 0

    def test_strategy_duplicate_user_type(self):
        """同一用户类型多条阶梯区间重叠 → 校验失败"""
        with pytest.raises(Exception):
            StrategyCreateRequest(
                channel_code="myq",
                strategy_name="test",
                enabled=True,
                tier_dimension=1,
                remark="",
                tiers=[
                    TierItem(**_tier_payload(user_type=1, tier_min=0, tier_max=100)),
                    TierItem(**_tier_payload(user_type=1, tier_min=50, tier_max=0)),
                ],
            )

    def test_strategy_multi_tier_same_user_type(self):
        """同一用户类型多条阶梯区间不重叠 → 校验通过（阶梯佣金）"""
        req = StrategyCreateRequest(
            channel_code="myq",
            strategy_name="test",
            enabled=True,
            tier_dimension=1,
            remark="",
            tiers=[
                TierItem(**_tier_payload(user_type=1, tier_min=0, tier_max=100)),
                TierItem(**_tier_payload(user_type=1, tier_min=100, tier_max=0)),
                TierItem(**_tier_payload(user_type=2, tier_min=0, tier_max=0)),
            ],
        )
        assert len(req.tiers) == 3

    def test_strategy_unlimited_then_more(self):
        """无上限阶梯后还有后续阶梯 → 校验失败"""
        with pytest.raises(Exception):
            StrategyCreateRequest(
                channel_code="myq",
                strategy_name="test",
                enabled=True,
                tier_dimension=1,
                remark="",
                tiers=[
                    TierItem(**_tier_payload(user_type=1, tier_min=0, tier_max=0)),
                    TierItem(**_tier_payload(user_type=1, tier_min=100, tier_max=0)),
                ],
            )

    def test_strategy_invalid_user_type(self):
        """非法用户类型 → 校验失败"""
        with pytest.raises(Exception):
            StrategyCreateRequest(
                channel_code="myq",
                strategy_name="test",
                enabled=True,
                tier_dimension=1,
                remark="",
                tiers=[TierItem(**_tier_payload(user_type=3))],
            )

    def test_strategy_valid(self):
        """正常策略请求通过校验"""
        req = StrategyCreateRequest(
            channel_code="myq",
            strategy_name="test",
            enabled=True,
            tier_dimension=1,
            remark="",
            tiers=[TierItem(**_tier_payload(user_type=1)), TierItem(**_tier_payload(user_type=2))],
        )
        assert len(req.tiers) == 2


# ══════════════════════════════════════════════════════
# 3. 阶梯匹配算法测试
# ══════════════════════════════════════════════════════


class TestMatchTier:
    """阶梯匹配算法测试"""

    def _tiers(self):
        return [
            {"tier_min": 0, "tier_max": 100, "user_type": 1},
            {"tier_min": 100, "tier_max": 0, "user_type": 1},  # 无上限
        ]

    def test_match_lower_tier(self):
        matched = _match_tier(self._tiers(), 1, 50, 0)
        assert matched["tier_max"] == 100

    def test_match_upper_tier(self):
        matched = _match_tier(self._tiers(), 1, 200, 0)
        assert matched["tier_max"] == 0

    def test_match_boundary(self):
        """边界值 100 命中第二档（100 <= value < 0 无上限）"""
        matched = _match_tier(self._tiers(), 1, 100, 0)
        assert matched["tier_max"] == 0

    def test_match_by_count_dimension(self):
        """按订单数量维度匹配"""
        tiers = [
            {"tier_min": 0, "tier_max": 5, "user_type": 1},
            {"tier_min": 5, "tier_max": 0, "user_type": 1},
        ]
        matched = _match_tier(tiers, 2, 0, 3)
        assert matched["tier_max"] == 5

    def test_no_match(self):
        """无命中（区间空洞）"""
        tiers = [{"tier_min": 100, "tier_max": 200, "user_type": 1}]
        matched = _match_tier(tiers, 1, 50, 0)
        assert matched is None


# ══════════════════════════════════════════════════════
# 4. 策略列表测试
# ══════════════════════════════════════════════════════


class TestStrategyList:
    """策略列表查询测试"""

    @pytest.mark.asyncio
    async def test_list_success(self):
        request = _make_request()
        items = [_make_strategy(), _make_strategy(channel_code="orderx", strategy_id=2)]

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.paginate_strategies = AsyncMock(return_value=(items, 2))
            mock_dao_cls.return_value = mock_dao

            result = _unwrap(await list_strategies(request, page=1, page_size=20, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["total"] == 2
        assert len(result["data"]["items"]) == 2
        assert result["data"]["items"][0]["channel_code"] == "myq"

    @pytest.mark.asyncio
    async def test_list_with_filters(self):
        """渠道+状态筛选透传"""
        request = _make_request()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.paginate_strategies = AsyncMock(return_value=([], 0))
            mock_dao_cls.return_value = mock_dao

            result = _unwrap(await list_strategies(
                request, page=1, page_size=20,
                channel_code="myq", enabled=True, admin_user_id=1,
            ))

        assert result["data"]["total"] == 0
        # 验证筛选参数透传
        call_kwargs = mock_dao.paginate_strategies.call_args.kwargs
        assert call_kwargs["channel_code"] == "myq"
        assert call_kwargs["enabled"] is True

    @pytest.mark.asyncio
    async def test_list_empty(self):
        request = _make_request()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.paginate_strategies = AsyncMock(return_value=([], 0))
            mock_dao_cls.return_value = mock_dao

            result = _unwrap(await list_strategies(request, page=1, page_size=20, admin_user_id=1))

        assert result["data"]["total"] == 0
        assert len(result["data"]["items"]) == 0

    @pytest.mark.asyncio
    async def test_list_db_error(self):
        request = _make_request()

        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db:
            mock_db.get_session.side_effect = Exception("DB connection failed")

            result = _unwrap(await list_strategies(request, page=1, page_size=20, admin_user_id=1))

        assert result["code"] != 200


# ══════════════════════════════════════════════════════
# 5. 策略详情测试
# ══════════════════════════════════════════════════════


class TestStrategyGet:
    """策略详情查询测试"""

    @pytest.mark.asyncio
    async def test_get_found(self):
        request = _make_request()
        s = _make_strategy()
        tiers = [_make_tier(), _make_tier(user_type=2, tier_id=2)]

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionTierDAO") as mock_t_dao_cls:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=s)
            mock_s_dao_cls.return_value = mock_s_dao
            mock_t_dao = MagicMock()
            mock_t_dao.list_by_strategy = AsyncMock(return_value=tiers)
            mock_t_dao_cls.return_value = mock_t_dao

            result = _unwrap(await get_strategy(request, "myq", admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["channel_code"] == "myq"
        assert len(result["data"]["tiers"]) == 2

    @pytest.mark.asyncio
    async def test_get_not_found(self):
        request = _make_request()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=None)
            mock_s_dao_cls.return_value = mock_s_dao

            result = _unwrap(await get_strategy(request, "myq", admin_user_id=1))

        assert result["code"] != 200


# ══════════════════════════════════════════════════════
# 6. 新增策略测试
# ══════════════════════════════════════════════════════


class TestStrategyCreate:
    """新增策略测试"""

    def _body(self):
        return StrategyCreateRequest(
            channel_code="myq",
            strategy_name="2026年Q3阶梯佣金",
            enabled=True,
            tier_dimension=1,
            remark="测试",
            tiers=[
                TierItem(**_tier_payload(user_type=1)),
                TierItem(**_tier_payload(user_type=2)),
            ],
        )

    @pytest.mark.asyncio
    async def test_create_success(self):
        request = _make_request()
        body = self._body()
        s = _make_strategy()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionTierDAO") as mock_t_dao_cls, \
             patch("src.api.v1.admin.f04_channel_commission.AuditLogger") as mock_audit:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=None)
            mock_s_dao.create = AsyncMock(return_value=s)
            mock_s_dao_cls.return_value = mock_s_dao
            mock_t_dao = MagicMock()
            mock_t_dao.batch_create = AsyncMock(return_value=[])
            mock_t_dao_cls.return_value = mock_t_dao
            mock_audit.log = AsyncMock()

            result = _unwrap(await create_strategy(request, body, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["channel_code"] == "myq"
        # 审计日志写入
        mock_audit.log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_duplicate(self):
        """渠道已存在策略 → 报错"""
        request = _make_request()
        body = self._body()
        s = _make_strategy()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=s)
            mock_s_dao_cls.return_value = mock_s_dao

            result = _unwrap(await create_strategy(request, body, admin_user_id=1))

        assert result["code"] != 200

    @pytest.mark.asyncio
    async def test_create_invalid_channel(self):
        """非法渠道标识 → 报错"""
        request = _make_request()
        body = self._body()
        body.channel_code = "invalid_channel"

        result = _unwrap(await create_strategy(request, body, admin_user_id=1))

        assert result["code"] != 200

    @pytest.mark.asyncio
    async def test_create_db_error(self):
        request = _make_request()
        body = self._body()

        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db:
            mock_db.get_session.side_effect = Exception("DB error")

            result = _unwrap(await create_strategy(request, body, admin_user_id=1))

        assert result["code"] != 200


# ══════════════════════════════════════════════════════
# 7. 更新策略测试
# ══════════════════════════════════════════════════════


class TestStrategyUpdate:
    """更新策略测试"""

    def _body(self):
        return StrategyUpdateRequest(
            strategy_name="新策略名",
            enabled=False,
            tiers=[
                TierItem(**_tier_payload(user_type=1, user_rate=0.7, platform_rate=0.3)),
            ],
        )

    @pytest.mark.asyncio
    async def test_update_success(self):
        request = _make_request()
        body = self._body()
        s = _make_strategy()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionTierDAO") as mock_t_dao_cls, \
             patch("src.api.v1.admin.f04_channel_commission.AuditLogger") as mock_audit:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=s)
            mock_s_dao_cls.return_value = mock_s_dao
            mock_t_dao = MagicMock()
            mock_t_dao.delete_by_strategy = AsyncMock(return_value=1)
            mock_t_dao.batch_create = AsyncMock(return_value=[])
            mock_t_dao.list_by_strategy = AsyncMock(return_value=[_make_tier()])
            mock_t_dao_cls.return_value = mock_t_dao
            mock_audit.log = AsyncMock()

            result = _unwrap(await update_strategy(request, "myq", body, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["channel_code"] == "myq"
        # 阶梯整体替换
        mock_t_dao.delete_by_strategy.assert_awaited_once_with(s.id)
        mock_audit.log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        request = _make_request()
        body = self._body()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=None)
            mock_s_dao_cls.return_value = mock_s_dao

            result = _unwrap(await update_strategy(request, "myq", body, admin_user_id=1))

        assert result["code"] != 200


# ══════════════════════════════════════════════════════
# 8. 启停策略测试
# ══════════════════════════════════════════════════════


class TestStrategyToggle:
    """启停策略测试"""

    @pytest.mark.asyncio
    async def test_toggle_enable(self):
        request = _make_request()
        body = StrategyToggleRequest(enabled=True)
        s = _make_strategy(enabled=False)

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls, \
             patch("src.api.v1.admin.f04_channel_commission.AuditLogger") as mock_audit:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=s)
            mock_s_dao_cls.return_value = mock_s_dao
            mock_audit.log = AsyncMock()

            result = _unwrap(await toggle_strategy(request, "myq", body, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["enabled"] is True
        assert s.enabled is True
        mock_audit.log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_toggle_disable(self):
        request = _make_request()
        body = StrategyToggleRequest(enabled=False)
        s = _make_strategy(enabled=True)

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls, \
             patch("src.api.v1.admin.f04_channel_commission.AuditLogger") as mock_audit:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=s)
            mock_s_dao_cls.return_value = mock_s_dao
            mock_audit.log = AsyncMock()

            result = _unwrap(await toggle_strategy(request, "myq", body, admin_user_id=1))

        assert result["data"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_toggle_not_found(self):
        request = _make_request()
        body = StrategyToggleRequest(enabled=True)

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=None)
            mock_s_dao_cls.return_value = mock_s_dao

            result = _unwrap(await toggle_strategy(request, "myq", body, admin_user_id=1))

        assert result["code"] != 200


# ══════════════════════════════════════════════════════
# 9. 分佣预览测试
# ══════════════════════════════════════════════════════


class TestPreview:
    """分佣预览测试"""

    @pytest.mark.asyncio
    async def test_preview_success(self):
        request = _make_request()
        body = CommissionPreviewRequest(channel_code="myq", user_type=1, amount=100, order_count=0)
        s = _make_strategy(enabled=True)
        tiers = [_make_tier(user_type=1, tier_min=0, tier_max=0, user_commission_rate=0.8)]

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionTierDAO") as mock_t_dao_cls:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=s)
            mock_s_dao_cls.return_value = mock_s_dao
            mock_t_dao = MagicMock()
            mock_t_dao.list_by_strategy = AsyncMock(return_value=tiers)
            mock_t_dao_cls.return_value = mock_t_dao

            result = _unwrap(await preview_commission(request, body, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["enabled"] is True
        assert result["data"]["matched_tier"] is not None
        assert result["data"]["result"]["total_commission"] == 100.0
        assert result["data"]["result"]["user_commission"] == 80.0
        assert result["data"]["result"]["platform_commission"] == 20.0

    @pytest.mark.asyncio
    async def test_preview_strategy_disabled(self):
        """策略停用 → 提示按默认比例"""
        request = _make_request()
        body = CommissionPreviewRequest(channel_code="myq", user_type=1, amount=100, order_count=0)
        s = _make_strategy(enabled=False)

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=s)
            mock_s_dao_cls.return_value = mock_s_dao

            result = _unwrap(await preview_commission(request, body, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["enabled"] is False
        assert result["data"]["matched_tier"] is None

    @pytest.mark.asyncio
    async def test_preview_no_match(self):
        """未命中阶梯 → 提示"""
        request = _make_request()
        body = CommissionPreviewRequest(channel_code="myq", user_type=1, amount=50, order_count=0)
        s = _make_strategy(enabled=True)
        tiers = [_make_tier(user_type=1, tier_min=100, tier_max=0)]

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionTierDAO") as mock_t_dao_cls:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=s)
            mock_s_dao_cls.return_value = mock_s_dao
            mock_t_dao = MagicMock()
            mock_t_dao.list_by_strategy = AsyncMock(return_value=tiers)
            mock_t_dao_cls.return_value = mock_t_dao

            result = _unwrap(await preview_commission(request, body, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["matched_tier"] is None
        assert "未命中" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_preview_invalid_user_type(self):
        request = _make_request()
        body = CommissionPreviewRequest(channel_code="myq", user_type=3, amount=100, order_count=0)

        result = _unwrap(await preview_commission(request, body, admin_user_id=1))

        assert result["code"] != 200

    @pytest.mark.asyncio
    async def test_preview_strategy_not_found(self):
        request = _make_request()
        body = CommissionPreviewRequest(channel_code="myq", user_type=1, amount=100, order_count=0)

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.ChannelCommissionStrategyDAO") as mock_s_dao_cls:
            mock_db.get_session.return_value = cm
            mock_s_dao = MagicMock()
            mock_s_dao.get_by_channel_code = AsyncMock(return_value=None)
            mock_s_dao_cls.return_value = mock_s_dao

            result = _unwrap(await preview_commission(request, body, admin_user_id=1))

        assert result["code"] != 200


# ══════════════════════════════════════════════════════
# 10. 审计记录查询测试
# ══════════════════════════════════════════════════════


class TestAuditLogs:
    """审计记录查询测试"""

    def _make_log(self, log_id=1, action=ACTION_STRATEGY_CREATE, channel="myq"):
        log = MagicMock()
        log.id = log_id
        log.user_id = 1
        log.user_name = "admin"
        log.action = action
        log.target_type = "channel_commission_strategy"
        log.target_id = 1
        log.details = json.dumps({"channel_code": channel, "enabled": True})
        log.ip_address = "127.0.0.1"
        log.create_time = datetime(2026, 8, 14, 12, 0, 0)
        return log

    @pytest.mark.asyncio
    async def test_audit_logs_success(self):
        request = _make_request()
        logs = [self._make_log(), self._make_log(log_id=2, action=ACTION_STRATEGY_UPDATE)]

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.AuditLogDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.paginate_by_actions = AsyncMock(return_value=(logs, 2))
            mock_dao_cls.return_value = mock_dao

            result = _unwrap(await list_strategy_audit_logs(
                request, page=1, page_size=20, channel_code=None, admin_user_id=1,
            ))

        assert result["code"] == 200
        assert result["data"]["total"] == 2
        assert len(result["data"]["items"]) == 2
        assert result["data"]["items"][0]["action"] == ACTION_STRATEGY_CREATE

    @pytest.mark.asyncio
    async def test_audit_logs_channel_filter(self):
        """按渠道筛选审计记录"""
        request = _make_request()
        logs = [
            self._make_log(log_id=1, channel="myq"),
            self._make_log(log_id=2, channel="orderx"),
        ]

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.AuditLogDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.paginate_by_actions = AsyncMock(return_value=(logs, 2))
            mock_dao_cls.return_value = mock_dao

            result = _unwrap(await list_strategy_audit_logs(
                request, page=1, page_size=20, channel_code="myq", admin_user_id=1,
            ))

        assert result["data"]["total"] == 1
        assert result["data"]["items"][0]["details"]["channel_code"] == "myq"

    @pytest.mark.asyncio
    async def test_audit_logs_empty(self):
        request = _make_request()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.f04_channel_commission.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.f04_channel_commission.AuditLogDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.paginate_by_actions = AsyncMock(return_value=([], 0))
            mock_dao_cls.return_value = mock_dao

            result = _unwrap(await list_strategy_audit_logs(
                request, page=1, page_size=20, channel_code=None, admin_user_id=1,
            ))

        assert result["data"]["total"] == 0
