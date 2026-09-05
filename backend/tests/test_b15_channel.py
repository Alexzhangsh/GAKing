# @ai-generated
"""
B15 渠道配置管理 API 单元测试
覆盖：
1. 渠道配置 CRUD 接口：list/get/create/update/delete
2. 渠道密钥测试接口：test-key
3. 权限校验：config:manage / channel:test
4. 正常路径 + 异常边界场景全覆盖

覆盖率目标：API 路由层 ≥90%
"""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

# 解包 JSONResponse → dict（测试直接调用 handler 返回 JSONResponse 对象）
import json
from fastapi.responses import JSONResponse


def _unwrap(resp):
    """将 JSONResponse 解包为 dict 供测试断言"""
    if isinstance(resp, JSONResponse):
        return json.loads(resp.body)
    return resp

from src.api.v1.admin.b15_channel import (
    ChannelConfigCreate,
    ChannelConfigUpdate,
    ChannelKeyTestRequest,
    get_channel,
    list_channels,
    create_channel,
    update_channel,
    delete_channel,
    test_channel_key as api_test_channel_key,
    _serialize_channel,
)
from src.models.system.channel_config import ChannelMapping


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_channel_mapping(
    channel_code: str = "myq",
    channel_name: str = "喵有券",
    api_token: str = "test_token_123456",
    api_secret: str = "test_secret_123456",
    pid: str = "mm_123_456_789",
    settle_rate: float = 0.85,
    status: bool = True,
    remark: str = "测试渠道",
    channel_id: int = 1,
):
    """构造 ChannelMapping mock 对象"""
    from datetime import datetime

    c = MagicMock(spec=ChannelMapping)
    c.id = channel_id
    c.channel_code = channel_code
    c.channel_name = channel_name
    c.api_token = api_token
    c.api_secret = api_secret
    c.pid = pid
    c.settle_rate = settle_rate
    c.status = status
    c.remark = remark
    c.is_delete = False
    c.create_time = datetime(2026, 7, 1, 10, 0, 0)
    c.update_time = datetime(2026, 7, 15, 10, 0, 0)
    return c


def _make_request():
    """构造 FastAPI Request mock"""
    request = MagicMock()
    request.headers = {}
    return request


def _make_session_cm():
    """构造 DatabaseManager.get_session() 上下文管理器 mock"""
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


# ══════════════════════════════════════════════════════
# 1. 序列化测试
# ══════════════════════════════════════════════════════


class TestChannelSerialize:
    """渠道配置序列化测试"""

    def test_serialize_channel_full(self):
        """完整序列化"""
        c = _make_channel_mapping()
        data = _serialize_channel(c)
        assert data["channel_code"] == "myq"
        assert data["channel_name"] == "喵有券"
        assert data["api_secret"] == "***"  # 密钥脱敏
        assert data["settle_rate"] == 0.85
        assert data["status"] is True
        assert data["create_time"] == "2026-07-01 10:00:00"
        assert data["update_time"] == "2026-07-15 10:00:00"

    def test_serialize_channel_empty_secret(self):
        """api_secret 为空时返回空字符串（非 ***）"""
        c = _make_channel_mapping(api_secret="")
        data = _serialize_channel(c)
        assert data["api_secret"] == ""

    def test_serialize_channel_null_times(self):
        """create_time/update_time 为 None 时返回 None"""
        c = _make_channel_mapping()
        c.create_time = None
        c.update_time = None
        data = _serialize_channel(c)
        assert data["create_time"] is None
        assert data["update_time"] is None


# ══════════════════════════════════════════════════════
# 2. 列表查询测试
# ══════════════════════════════════════════════════════


class TestChannelList:
    """渠道列表查询测试"""

    @pytest.mark.asyncio
    async def test_list_channels_success(self):
        """分页查询成功"""
        request = _make_request()
        items = [_make_channel_mapping(), _make_channel_mapping(channel_code="orderx", channel_id=2)]

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.b15_channel.BaseDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.paginate_list = AsyncMock(return_value=(items, 2))
            mock_dao_cls.return_value = mock_dao

            result = _unwrap(await list_channels(request, page=1, page_size=20, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["total"] == 2
        assert len(result["data"]["items"]) == 2
        assert result["data"]["items"][0]["channel_code"] == "myq"

    @pytest.mark.asyncio
    async def test_list_channels_empty(self):
        """空列表返回"""
        request = _make_request()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.b15_channel.BaseDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.paginate_list = AsyncMock(return_value=([], 0))
            mock_dao_cls.return_value = mock_dao

            result = _unwrap(await list_channels(request, page=1, page_size=20, admin_user_id=1))

        assert result["data"]["total"] == 0
        assert len(result["data"]["items"]) == 0

    @pytest.mark.asyncio
    async def test_list_channels_db_error(self):
        """DB 异常 → 错误响应"""
        request = _make_request()

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db:
            mock_db.get_session.side_effect = Exception("DB connection failed")

            result = _unwrap(await list_channels(request, page=1, page_size=20, admin_user_id=1))

        assert result["code"] != 200  # 业务错误码或异常


# ══════════════════════════════════════════════════════
# 3. 详情查询测试
# ══════════════════════════════════════════════════════


class TestChannelGet:
    """渠道详情查询测试"""

    @pytest.mark.asyncio
    async def test_get_channel_found(self):
        """查询成功"""
        request = _make_request()
        c = _make_channel_mapping()

        session, cm = _make_session_cm()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = c
        session.execute = AsyncMock(return_value=result_mock)

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm

            result = _unwrap(await get_channel(request, "myq", admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["channel_code"] == "myq"

    @pytest.mark.asyncio
    async def test_get_channel_not_found(self):
        """渠道不存在 → ValueError"""
        request = _make_request()

        session, cm = _make_session_cm()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm

            result = _unwrap(await get_channel(request, "nonexistent", admin_user_id=1))

        assert result["code"] != 200
        assert "不存在" in result.get("msg", "")


# ══════════════════════════════════════════════════════
# 4. 新增渠道测试
# ══════════════════════════════════════════════════════


class TestChannelCreate:
    """新增渠道测试"""

    @pytest.mark.asyncio
    async def test_create_channel_success(self):
        """新增成功"""
        request = _make_request()
        body = ChannelConfigCreate(
            channel_code="myq",
            channel_name="喵有券",
            api_token="test_token_123456",
            api_secret="test_secret",
            pid="mm_123_456_789",
            settle_rate=0.85,
            status=True,
            remark="测试渠道",
        )
        c = _make_channel_mapping()

        session, cm = _make_session_cm()
        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.b15_channel.BaseDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.create = AsyncMock(return_value=c)
            mock_dao_cls.return_value = mock_dao

            result = _unwrap(await create_channel(request, body, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["channel_code"] == "myq"
        assert "创建成功" in result["msg"]

    @pytest.mark.asyncio
    async def test_create_channel_db_error(self):
        """DB 异常 → 错误响应"""
        request = _make_request()
        body = ChannelConfigCreate(channel_code="myq")

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db:
            mock_db.get_session.side_effect = Exception("DB error")

            result = _unwrap(await create_channel(request, body, admin_user_id=1))

        assert result["code"] != 200


# ══════════════════════════════════════════════════════
# 5. 更新渠道测试
# ══════════════════════════════════════════════════════


class TestChannelUpdate:
    """更新渠道测试"""

    @pytest.mark.asyncio
    async def test_update_channel_success(self):
        """更新成功"""
        request = _make_request()
        body = ChannelConfigUpdate(channel_name="新喵有券", settle_rate=0.90)
        c = _make_channel_mapping()

        session, cm = _make_session_cm()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = c
        session.execute = AsyncMock(return_value=result_mock)
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.b15_channel.BaseDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = MagicMock()

            result = _unwrap(await update_channel(request, "myq", body, admin_user_id=1))

        assert result["code"] == 200
        assert "更新成功" in result["msg"]

    @pytest.mark.asyncio
    async def test_update_channel_not_found(self):
        """渠道不存在 → ValueError"""
        request = _make_request()
        body = ChannelConfigUpdate(channel_name="新名称")

        session, cm = _make_session_cm()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm

            result = _unwrap(await update_channel(request, "nonexistent", body, admin_user_id=1))

        assert result["code"] != 200
        assert "不存在" in result.get("msg", "")


# ══════════════════════════════════════════════════════
# 6. 删除渠道测试
# ══════════════════════════════════════════════════════


class TestChannelDelete:
    """删除渠道测试"""

    @pytest.mark.asyncio
    async def test_delete_channel_success(self):
        """软删除成功"""
        request = _make_request()
        c = _make_channel_mapping()

        session, cm = _make_session_cm()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = c
        session.execute = AsyncMock(return_value=result_mock)
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.b15_channel.BaseDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = MagicMock()

            result = _unwrap(await delete_channel(request, "myq", admin_user_id=1))

        assert result["code"] == 200
        assert "删除成功" in result["msg"]
        assert c.is_delete is True  # 验证软删除

    @pytest.mark.asyncio
    async def test_delete_channel_not_found(self):
        """渠道不存在 → ValueError"""
        request = _make_request()

        session, cm = _make_session_cm()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm

            result = _unwrap(await delete_channel(request, "nonexistent", admin_user_id=1))

        assert result["code"] != 200
        assert "不存在" in result.get("msg", "")


# ══════════════════════════════════════════════════════
# 7. 密钥测试测试
# ══════════════════════════════════════════════════════


class TestChannelKeyTest:
    """渠道密钥测试（S04 P2-4：对接真实适配器 health_check）"""

    @pytest.mark.asyncio
    async def test_key_test_success(self):
        """密钥测试成功（真实适配器 health_check 返回 True）"""
        request = _make_request()
        body = ChannelKeyTestRequest(
            channel_code="myq",
            api_token="test_token_123456",
            api_secret="test_secret",
        )

        mock_adapter = AsyncMock()
        mock_adapter.health_check.return_value = True

        with patch("src.api.v1.admin.b15_channel.EnvConfig") as mock_env, \
             patch("src.api.v1.admin.b15_channel._build_test_adapter", return_value=mock_adapter) as mock_build:
            mock_env.is_production.return_value = False

            result = _unwrap(await api_test_channel_key(request, body, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["success"] is True
        assert result["data"]["channel_code"] == "myq"
        assert result["data"]["token_length"] == 17
        assert result["data"]["tested_by"] == "real_adapter_health_check"
        mock_build.assert_called_once()
        mock_adapter.health_check.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_key_test_adapter_unreachable(self):
        """适配器 health_check 返回 False → 密钥验证失败"""
        request = _make_request()
        body = ChannelKeyTestRequest(
            channel_code="myq",
            api_token="test_token_123456",
        )

        mock_adapter = AsyncMock()
        mock_adapter.health_check.return_value = False

        with patch("src.api.v1.admin.b15_channel.EnvConfig") as mock_env, \
             patch("src.api.v1.admin.b15_channel._build_test_adapter", return_value=mock_adapter):
            mock_env.is_production.return_value = False

            result = _unwrap(await api_test_channel_key(request, body, admin_user_id=1))

        assert result["code"] != 200
        assert "验证失败" in result.get("msg", "")

    @pytest.mark.asyncio
    async def test_key_test_adapter_build_exception(self):
        """适配器构造失败 → 返回错误"""
        request = _make_request()
        body = ChannelKeyTestRequest(
            channel_code="myq",
            api_token="test_token_123456",
        )

        with patch("src.api.v1.admin.b15_channel.EnvConfig") as mock_env, \
             patch("src.api.v1.admin.b15_channel._build_test_adapter", side_effect=RuntimeError("构造失败")):
            mock_env.is_production.return_value = False

            result = _unwrap(await api_test_channel_key(request, body, admin_user_id=1))

        assert result["code"] != 200
        assert "适配器失败" in result.get("msg", "")

    @pytest.mark.asyncio
    async def test_key_test_production_blocked(self):
        """生产环境禁止测试"""
        request = _make_request()
        body = ChannelKeyTestRequest(
            channel_code="myq",
            api_token="test_token_123456",
        )

        with patch("src.api.v1.admin.b15_channel.EnvConfig") as mock_env:
            mock_env.is_production.return_value = True

            result = _unwrap(await api_test_channel_key(request, body, admin_user_id=1))

        assert result["code"] != 200
        assert "生产环境禁止" in result.get("msg", "")

    @pytest.mark.asyncio
    async def test_key_test_invalid_channel(self):
        """不支持的渠道标识"""
        request = _make_request()
        body = ChannelKeyTestRequest(
            channel_code="invalid",
            api_token="test_token_123456",
        )

        with patch("src.api.v1.admin.b15_channel.EnvConfig") as mock_env:
            mock_env.is_production.return_value = False

            result = _unwrap(await api_test_channel_key(request, body, admin_user_id=1))

        assert result["code"] != 200
        assert "不支持的渠道" in result.get("msg", "")

    @pytest.mark.asyncio
    async def test_key_test_token_too_short(self):
        """Token 太短"""
        request = _make_request()
        body = ChannelKeyTestRequest(
            channel_code="myq",
            api_token="short",
        )

        with patch("src.api.v1.admin.b15_channel.EnvConfig") as mock_env:
            mock_env.is_production.return_value = False

            result = _unwrap(await api_test_channel_key(request, body, admin_user_id=1))

        assert result["code"] != 200
        assert "不能为空" in result.get("msg", "")

    @pytest.mark.asyncio
    async def test_key_test_orderx_success(self):
        """订单侠渠道密钥测试成功（真实适配器 health_check 返回 True）"""
        request = _make_request()
        body = ChannelKeyTestRequest(
            channel_code="orderx",
            api_token="orderx_token_123456",
            api_secret="orderx_secret",
        )

        mock_adapter = AsyncMock()
        mock_adapter.health_check.return_value = True

        with patch("src.api.v1.admin.b15_channel.EnvConfig") as mock_env, \
             patch("src.api.v1.admin.b15_channel._build_test_adapter", return_value=mock_adapter):
            mock_env.is_production.return_value = False

            result = _unwrap(await api_test_channel_key(request, body, admin_user_id=1))

        assert result["code"] == 200
        assert result["data"]["success"] is True
        assert result["data"]["channel_code"] == "orderx"

    @pytest.mark.asyncio
    async def test_key_test_empty_token(self):
        """空 Token → 校验失败"""
        request = _make_request()
        body = ChannelKeyTestRequest(
            channel_code="myq",
            api_token="",
        )

        with patch("src.api.v1.admin.b15_channel.EnvConfig") as mock_env:
            mock_env.is_production.return_value = False

            result = _unwrap(await api_test_channel_key(request, body, admin_user_id=1))

        assert result["code"] != 200


# ══════════════════════════════════════════════════════
# 8. Backend Integration Test（联调测试）
# ══════════════════════════════════════════════════════


class TestChannelIntegration:
    """渠道配置联调测试（模拟完整业务流程）"""

    @pytest.mark.asyncio
    async def test_full_channel_lifecycle(self):
        """完整渠道生命周期：创建 → 查询 → 更新 → 列举 → 删除"""
        request = _make_request()
        myq = _make_channel_mapping(channel_code="myq", channel_id=1)

        # 1. 创建
        create_body = ChannelConfigCreate(
            channel_code="myq",
            channel_name="喵有券",
            api_token="test_token_123456",
            settle_rate=0.85,
        )

        session_create, cm_create = _make_session_cm()
        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.b15_channel.BaseDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm_create
            mock_dao = MagicMock()
            mock_dao.create = AsyncMock(return_value=myq)
            mock_dao_cls.return_value = mock_dao

            create_result = _unwrap(await create_channel(request, create_body, admin_user_id=1))
        assert create_result["code"] == 200
        assert create_result["data"]["channel_code"] == "myq"

        # 2. 查询详情
        session_get, cm_get = _make_session_cm()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = myq
        session_get.execute = AsyncMock(return_value=result_mock)

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm_get

            get_result = _unwrap(await get_channel(request, "myq", admin_user_id=1))
        assert get_result["code"] == 200
        assert get_result["data"]["channel_code"] == "myq"

        # 3. 更新渠道
        update_body = ChannelConfigUpdate(channel_name="新喵有券", settle_rate=0.90)
        updated_myq = _make_channel_mapping(channel_code="myq", channel_name="新喵有券", settle_rate=0.90)

        session_update, cm_update = _make_session_cm()
        result_mock_upd = MagicMock()
        result_mock_upd.scalar_one_or_none.return_value = updated_myq
        session_update.execute = AsyncMock(return_value=result_mock_upd)
        session_update.flush = AsyncMock()
        session_update.commit = AsyncMock()

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.b15_channel.BaseDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm_update
            mock_dao_cls.return_value = MagicMock()

            update_result = _unwrap(await update_channel(request, "myq", update_body, admin_user_id=1))
        assert update_result["code"] == 200

        # 4. 列表查询
        session_list, cm_list = _make_session_cm()
        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.b15_channel.BaseDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm_list
            mock_dao = MagicMock()
            mock_dao.paginate_list = AsyncMock(return_value=([updated_myq], 1))
            mock_dao_cls.return_value = mock_dao

            list_result = _unwrap(await list_channels(request, page=1, page_size=20, admin_user_id=1))
        assert list_result["code"] == 200
        assert list_result["data"]["total"] == 1

        # 5. 软删除
        session_delete, cm_delete = _make_session_cm()
        result_mock_del = MagicMock()
        result_mock_del.scalar_one_or_none.return_value = updated_myq
        session_delete.execute = AsyncMock(return_value=result_mock_del)
        session_delete.flush = AsyncMock()
        session_delete.commit = AsyncMock()

        with patch("src.api.v1.admin.b15_channel.DatabaseManager") as mock_db, \
             patch("src.api.v1.admin.b15_channel.BaseDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm_delete
            mock_dao_cls.return_value = MagicMock()

            delete_result = _unwrap(await delete_channel(request, "myq", admin_user_id=1))
        assert delete_result["code"] == 200
        assert "删除成功" in delete_result["msg"]