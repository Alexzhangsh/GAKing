# @ai-generated
"""
B14 系统配置服务 + 限流中间件单元测试
覆盖：
1. B14ConfigService：list/get/create/update/batch_update/delete/refresh_cache/validate
2. _validate_value：int/bool/decimal/json/str 类型 + min/max 范围校验
3. B14RateLimitMiddleware：放行/拦截(429)/跳过白名单/Redis异常降级/限流关闭
4. 配置热更新：写后失效缓存（B14ConfigUtil.invalidate）

覆盖率目标：单文件 ≥90%
"""
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.config.b14_constants import B14_CONFIG_REGISTRY
from src.services.b14_config_service import B14ConfigService
from src.schemas.b14_config import (
    SystemConfigBatchUpdateItem,
    SystemConfigCreateRequest,
    SystemConfigUpdateRequest,
)


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_config(
    config_id: int = 1,
    config_key: str = "settlement_delay_days",
    config_value: str = "30",
    config_name: str = "佣金结算延迟天数",
    remark: str = "",
):
    cfg = MagicMock()
    cfg.id = config_id
    cfg.config_key = config_key
    cfg.config_value = config_value
    cfg.config_name = config_name
    cfg.remark = remark
    cfg.create_time = None
    cfg.update_time = None
    return cfg


def _make_session_cm():
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


# ══════════════════════════════════════════════════════
# 1. 查询接口测试
# ══════════════════════════════════════════════════════


class TestB14ConfigQuery:
    """配置查询测试"""

    @pytest.mark.asyncio
    async def test_list_configs(self):
        """分页查询配置列表"""
        cfg = _make_config()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.list_with_pagination.return_value = ([cfg], 1)

        with patch("src.services.b14_config_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_config_service.SystemConfigB14DAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            items, total = await B14ConfigService.list_configs(page=1, page_size=20)
        assert total == 1
        assert len(items) == 1
        assert items[0].config_key == "settlement_delay_days"

    @pytest.mark.asyncio
    async def test_get_config_by_key_found(self):
        """按 key 查询配置 - 找到"""
        cfg = _make_config()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_key.return_value = cfg

        with patch("src.services.b14_config_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_config_service.SystemConfigB14DAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14ConfigService.get_config_by_key("settlement_delay_days")
        assert result is not None
        assert result.config_key == "settlement_delay_days"

    @pytest.mark.asyncio
    async def test_get_config_by_key_not_found(self):
        """按 key 查询配置 - 未找到"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_key.return_value = None

        with patch("src.services.b14_config_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_config_service.SystemConfigB14DAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14ConfigService.get_config_by_key("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_config_detail_success(self):
        """获取配置详情（含元信息）"""
        cfg = _make_config()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_key.return_value = cfg

        with patch("src.services.b14_config_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_config_service.SystemConfigB14DAO") as mock_dao_cls, \
             patch("src.services.b14_config_service.B14ConfigUtil") as mock_util:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_util.get = AsyncMock(return_value="30")

            data = await B14ConfigService.get_config_detail("settlement_delay_days")
        assert data["config_key"] == "settlement_delay_days"
        assert data["config_type"] == "int"
        assert data["current_value"] == "30"
        assert data["db_record"] is not None

    @pytest.mark.asyncio
    async def test_get_config_detail_key_not_in_registry(self):
        """配置 key 不在注册表 → ValueError"""
        with pytest.raises(ValueError, match="不在注册表白名单"):
            await B14ConfigService.get_config_detail("nonexistent_key")

    @pytest.mark.asyncio
    async def test_list_registry(self):
        """获取全量注册表"""
        with patch("src.services.b14_config_service.B14ConfigUtil") as mock_util, \
             patch.object(B14ConfigService, "get_config_by_key", new_callable=AsyncMock) as mock_get:
            mock_util.get = AsyncMock(return_value="30")
            mock_get.return_value = None

            items = await B14ConfigService.list_registry()
        assert len(items) == len(B14_CONFIG_REGISTRY)
        assert items[0]["config_key"] in B14_CONFIG_REGISTRY


# ══════════════════════════════════════════════════════
# 2. 写操作测试
# ══════════════════════════════════════════════════════


class TestB14ConfigWrite:
    """配置写操作测试"""

    @pytest.mark.asyncio
    async def test_create_config_success(self):
        """新增配置成功"""
        cfg = _make_config()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.upsert_by_key.return_value = cfg

        request = SystemConfigCreateRequest(
            config_key="settlement_delay_days",
            config_value="30",
            config_name="佣金结算延迟天数",
        )

        with patch("src.services.b14_config_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_config_service.SystemConfigB14DAO") as mock_dao_cls, \
             patch("src.services.b14_config_service.B14ConfigUtil") as mock_util, \
             patch.object(B14ConfigService, "get_config_by_key", new_callable=AsyncMock) as mock_get:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_get.return_value = None
            mock_util.invalidate = AsyncMock()

            result = await B14ConfigService.create_config(request)
        assert result.config_key == "settlement_delay_days"
        mock_util.invalidate.assert_awaited()

    @pytest.mark.asyncio
    async def test_create_config_key_not_in_registry(self):
        """key 不在白名单 → ValueError"""
        request = SystemConfigCreateRequest(
            config_key="nonexistent_key",
            config_value="30",
        )
        with pytest.raises(ValueError, match="不在注册表白名单"):
            await B14ConfigService.create_config(request)

    @pytest.mark.asyncio
    async def test_create_config_invalid_value(self):
        """值类型不合法 → ValueError"""
        request = SystemConfigCreateRequest(
            config_key="settlement_delay_days",
            config_value="not_an_int",
        )
        with pytest.raises(ValueError, match="不是有效整数"):
            await B14ConfigService.create_config(request)

    @pytest.mark.asyncio
    async def test_create_config_already_exists(self):
        """key 已存在 → ValueError"""
        request = SystemConfigCreateRequest(
            config_key="settlement_delay_days",
            config_value="30",
        )
        with patch.object(B14ConfigService, "get_config_by_key", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _make_config()
            with pytest.raises(ValueError, match="已存在"):
                await B14ConfigService.create_config(request)

    @pytest.mark.asyncio
    async def test_update_config_success(self):
        """更新配置成功"""
        cfg = _make_config()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.upsert_by_key.return_value = cfg

        request = SystemConfigUpdateRequest(config_value="60")

        with patch("src.services.b14_config_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_config_service.SystemConfigB14DAO") as mock_dao_cls, \
             patch("src.services.b14_config_service.B14ConfigUtil") as mock_util, \
             patch.object(B14ConfigService, "get_config_by_key", new_callable=AsyncMock) as mock_get:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_get.return_value = cfg
            mock_util.invalidate = AsyncMock()

            result = await B14ConfigService.update_config("settlement_delay_days", request)
        assert result.config_value == "30"  # mock returns original
        mock_util.invalidate.assert_awaited()

    @pytest.mark.asyncio
    async def test_update_config_not_in_registry(self):
        """key 不在白名单 → ValueError"""
        request = SystemConfigUpdateRequest(config_value="60")
        with pytest.raises(ValueError, match="不在注册表白名单"):
            await B14ConfigService.update_config("nonexistent_key", request)

    @pytest.mark.asyncio
    async def test_update_config_not_exists(self):
        """配置不存在 → ValueError"""
        request = SystemConfigUpdateRequest(config_value="60")
        with patch.object(B14ConfigService, "get_config_by_key", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            with pytest.raises(ValueError, match="不存在"):
                await B14ConfigService.update_config("settlement_delay_days", request)

    @pytest.mark.asyncio
    async def test_update_config_invalid_value(self):
        """值超出范围 → ValueError"""
        cfg = _make_config()
        request = SystemConfigUpdateRequest(config_value="99999")  # 超出 max=365
        with patch.object(B14ConfigService, "get_config_by_key", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = cfg
            with pytest.raises(ValueError, match="大于最大值"):
                await B14ConfigService.update_config("settlement_delay_days", request)

    @pytest.mark.asyncio
    async def test_delete_config_success(self):
        """删除配置成功"""
        cfg = _make_config()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.logic_delete_by_id = AsyncMock()

        with patch("src.services.b14_config_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_config_service.SystemConfigB14DAO") as mock_dao_cls, \
             patch("src.services.b14_config_service.B14ConfigUtil") as mock_util, \
             patch.object(B14ConfigService, "get_config_by_key", new_callable=AsyncMock) as mock_get:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_get.return_value = cfg
            mock_util.invalidate = AsyncMock()

            result = await B14ConfigService.delete_config("settlement_delay_days")
        assert result is True
        mock_dao.logic_delete_by_id.assert_awaited()

    @pytest.mark.asyncio
    async def test_delete_config_not_exists(self):
        """配置不存在 → ValueError"""
        with patch.object(B14ConfigService, "get_config_by_key", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            with pytest.raises(ValueError, match="不存在"):
                await B14ConfigService.delete_config("nonexistent_key")


# ══════════════════════════════════════════════════════
# 3. 批量更新测试
# ══════════════════════════════════════════════════════


class TestB14ConfigBatchUpdate:
    """批量更新测试"""

    @pytest.mark.asyncio
    async def test_batch_update_success(self):
        """批量更新开关类配置成功"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.upsert_by_key = AsyncMock()

        items = [
            SystemConfigBatchUpdateItem(
                config_key="task_settlement_freeze_enable", config_value="false"
            ),
            SystemConfigBatchUpdateItem(
                config_key="task_order_sync_enable", config_value="true"
            ),
        ]

        with patch("src.services.b14_config_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_config_service.SystemConfigB14DAO") as mock_dao_cls, \
             patch("src.services.b14_config_service.B14ConfigUtil") as mock_util:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            mock_util.invalidate = AsyncMock()

            result = await B14ConfigService.batch_update_configs(items)
        assert len(result.updated) == 2
        assert len(result.skipped) == 0
        assert len(result.failed) == 0

    @pytest.mark.asyncio
    async def test_batch_update_skip_non_switch(self):
        """跳过非 task_*_enable 配置"""
        items = [
            SystemConfigBatchUpdateItem(
                config_key="settlement_delay_days", config_value="60"
            ),
        ]
        result = await B14ConfigService.batch_update_configs(items)
        assert len(result.skipped) == 1
        assert len(result.updated) == 0

    @pytest.mark.asyncio
    async def test_batch_update_invalid_bool_value(self):
        """无效布尔值 → failed"""
        items = [
            SystemConfigBatchUpdateItem(
                config_key="task_settlement_freeze_enable", config_value="maybe"
            ),
        ]
        result = await B14ConfigService.batch_update_configs(items)
        assert len(result.failed) == 1
        assert len(result.updated) == 0


# ══════════════════════════════════════════════════════
# 4. 缓存管理测试
# ══════════════════════════════════════════════════════


class TestB14ConfigCache:
    """缓存管理测试"""

    @pytest.mark.asyncio
    async def test_refresh_cache_success(self):
        """刷新缓存成功"""
        with patch("src.services.b14_config_service.B14ConfigUtil") as mock_util:
            mock_util.refresh = AsyncMock()
            mock_util.get_all_memory.return_value = {"key1": "val1", "key2": "val2"}

            result = await B14ConfigService.refresh_cache()
        assert result["success"] is True
        assert result["loaded_count"] == 2

    @pytest.mark.asyncio
    async def test_refresh_cache_fail(self):
        """刷新缓存失败"""
        with patch("src.services.b14_config_service.B14ConfigUtil") as mock_util:
            mock_util.refresh = AsyncMock(side_effect=Exception("DB down"))

            result = await B14ConfigService.refresh_cache()
        assert result["success"] is False
        assert result["loaded_count"] == 0


# ══════════════════════════════════════════════════════
# 5. 值校验测试
# ══════════════════════════════════════════════════════


class TestB14ConfigValidate:
    """配置值校验测试"""

    def test_validate_int_valid(self):
        """校验整数 - 合法"""
        result = B14ConfigService.validate_config_value("settlement_delay_days", "30")
        assert result["valid"] is True
        assert result["parsed_value"] == 30

    def test_validate_int_invalid(self):
        """校验整数 - 非法"""
        result = B14ConfigService.validate_config_value("settlement_delay_days", "abc")
        assert result["valid"] is False
        assert "不是有效整数" in result["error_message"]

    def test_validate_int_below_min(self):
        """校验整数 - 小于最小值"""
        result = B14ConfigService.validate_config_value("settlement_delay_days", "0")
        assert result["valid"] is False
        assert "小于最小值" in result["error_message"]

    def test_validate_int_above_max(self):
        """校验整数 - 大于最大值"""
        result = B14ConfigService.validate_config_value("settlement_delay_days", "999")
        assert result["valid"] is False
        assert "大于最大值" in result["error_message"]

    def test_validate_bool_valid(self):
        """校验布尔 - 合法"""
        result = B14ConfigService.validate_config_value(
            "task_settlement_freeze_enable", "true"
        )
        assert result["valid"] is True
        assert result["parsed_value"] is True

    def test_validate_bool_invalid(self):
        """校验布尔 - 非法"""
        result = B14ConfigService.validate_config_value(
            "task_settlement_freeze_enable", "maybe"
        )
        assert result["valid"] is False

    def test_validate_decimal_valid(self):
        """校验金额 - 合法"""
        result = B14ConfigService.validate_config_value("amount_tolerance", "0.05")
        assert result["valid"] is True
        assert result["parsed_value"] == Decimal("0.05")

    def test_validate_decimal_invalid(self):
        """校验金额 - 非法"""
        result = B14ConfigService.validate_config_value("amount_tolerance", "abc")
        assert result["valid"] is False

    def test_validate_key_not_in_registry(self):
        """key 不在注册表 → 无效"""
        result = B14ConfigService.validate_config_value("nonexistent_key", "30")
        assert result["valid"] is False
        assert "不在注册表白名单" in result["error_message"]

    def test_validate_value_int_type_internal(self):
        """_validate_value int 类型内部方法"""
        parsed = B14ConfigService._validate_value("circuit_breaker_threshold", "10")
        assert parsed == 10

    def test_validate_value_str_type_internal(self):
        """_validate_value str 类型内部方法"""
        parsed = B14ConfigService._validate_value("reconciliation_cron", "0 2 * * *")
        assert parsed == "0 2 * * *"

    def test_serialize_config(self):
        """_serialize_config 序列化"""
        cfg = _make_config()
        data = B14ConfigService._serialize_config(cfg)
        assert data["config_key"] == "settlement_delay_days"
        assert data["config_value"] == "30"


# ══════════════════════════════════════════════════════
# 6. 限流中间件测试
# ══════════════════════════════════════════════════════


class TestB14RateLimitMiddleware:
    """限流中间件测试"""

    @pytest.mark.asyncio
    async def test_rate_limit_skip_non_admin_path(self):
        """非 admin 路径放行"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        middleware = B14RateLimitMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/cps/orders"
        call_next = AsyncMock(return_value=MagicMock())

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited()

    @pytest.mark.asyncio
    async def test_rate_limit_skip_whitelist(self):
        """白名单路径放行（如 login）"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        middleware = B14RateLimitMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/auth/login"
        request.headers = {}
        call_next = AsyncMock(return_value=MagicMock())

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited()

    @pytest.mark.asyncio
    async def test_rate_limit_allowed(self):
        """未超限 → 放行 + 设置响应头"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        middleware = B14RateLimitMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/config/"
        request.headers = MagicMock()
        request.headers.get.side_effect = lambda key, default="": (
            "192.168.1.1" if key == "X-Forwarded-For" else default
        )
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with patch("src.common.b14_rate_limit_middleware.B14ConfigUtil") as mock_config, \
             patch("src.common.b14_rate_limit_middleware.RateLimitUtil") as mock_rate:
            mock_config.get_int = AsyncMock(return_value=60)
            mock_rate.check_sliding_window = AsyncMock(return_value=(True, 10))

            response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited()

    @pytest.mark.asyncio
    async def test_rate_limit_blocked(self):
        """超限 → 429"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        middleware = B14RateLimitMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/config/"
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        call_next = AsyncMock()

        with patch("src.common.b14_rate_limit_middleware.B14ConfigUtil") as mock_config, \
             patch("src.common.b14_rate_limit_middleware.RateLimitUtil") as mock_rate, \
             patch("src.common.b14_rate_limit_middleware.get_request_id", return_value="req_test"):
            mock_config.get_int = AsyncMock(return_value=60)
            mock_rate.check_sliding_window = AsyncMock(return_value=(False, 60))

            response = await middleware.dispatch(request, call_next)
        assert response.status_code == 429
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rate_limit_disabled(self):
        """限流阈值=0 → 关限流，放行"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        middleware = B14RateLimitMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/config/"
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        call_next = AsyncMock(return_value=MagicMock())

        with patch("src.common.b14_rate_limit_middleware.B14ConfigUtil") as mock_config:
            mock_config.get_int = AsyncMock(return_value=0)
            response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited()

    @pytest.mark.asyncio
    async def test_rate_limit_redis_error_degraded(self):
        """Redis 异常 → 降级放行"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        middleware = B14RateLimitMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/config/"
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        call_next = AsyncMock(return_value=MagicMock())

        with patch("src.common.b14_rate_limit_middleware.B14ConfigUtil") as mock_config, \
             patch("src.common.b14_rate_limit_middleware.RateLimitUtil") as mock_rate:
            mock_config.get_int = AsyncMock(return_value=60)
            mock_rate.check_sliding_window = AsyncMock(
                side_effect=Exception("Redis down")
            )
            response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited()

    def test_get_client_ip_forwarded(self):
        """从 X-Forwarded-For 提取 IP"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get.side_effect = lambda key, default="": (
            "10.0.0.1, 192.168.1.1" if key == "X-Forwarded-For" else default
        )
        ip = B14RateLimitMiddleware._get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_get_client_ip_direct(self):
        """无 X-Forwarded-For 时从 client.host 提取"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.client = MagicMock()
        request.client.host = "192.168.1.100"
        ip = B14RateLimitMiddleware._get_client_ip(request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_no_client(self):
        """无 X-Forwarded-For 也无 client → unknown"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.client = None
        ip = B14RateLimitMiddleware._get_client_ip(request)
        assert ip == "unknown"

    @pytest.mark.asyncio
    async def test_rate_limit_config_read_exception_degraded(self):
        """B14ConfigUtil 抛异常 → 降级 EnvConfig 默认值继续执行"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        middleware = B14RateLimitMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/config/"
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        call_next = AsyncMock(return_value=MagicMock())

        with patch("src.common.b14_rate_limit_middleware.B14ConfigUtil") as mock_config, \
             patch("src.common.b14_rate_limit_middleware.RateLimitUtil") as mock_rate:
            # 配置读取抛异常，触发降级
            mock_config.get_int = AsyncMock(side_effect=Exception("Redis down"))
            mock_rate.check_sliding_window = AsyncMock(return_value=(True, 5))

            response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited()

    @pytest.mark.asyncio
    async def test_rate_limit_set_response_header_failure_ignored(self):
        """响应头设置异常被吞掉（response.headers 不可写）"""
        from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

        middleware = B14RateLimitMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/config/"
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        # 构造一个 response.headers 赋值会抛异常的 mock
        mock_response = MagicMock()
        type(mock_response.headers).__setitem__ = MagicMock(
            side_effect=TypeError("read-only")
        )
        call_next = AsyncMock(return_value=mock_response)

        with patch("src.common.b14_rate_limit_middleware.B14ConfigUtil") as mock_config, \
             patch("src.common.b14_rate_limit_middleware.RateLimitUtil") as mock_rate:
            mock_config.get_int = AsyncMock(return_value=60)
            mock_rate.check_sliding_window = AsyncMock(return_value=(True, 5))

            # 不应抛异常
            response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited()


# ══════════════════════════════════════════════════════
# 5. B14ConfigUtil 配置读写工具测试
# ══════════════════════════════════════════════════════


class TestB14ConfigUtil:
    """B14ConfigUtil 双层缓存读写工具测试"""

    def setup_method(self):
        """每个测试前重置类变量缓存状态"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {}
        B14ConfigUtil._cache_loaded = False

    @pytest.mark.asyncio
    async def test_load_all_from_db_success(self):
        """load_all：DB 加载成功 → 内存 + Redis 写入"""
        from src.common.b14_config_util import B14ConfigUtil

        # 构造 mock configs
        config1 = MagicMock()
        config1.config_key = "admin_rate_limit_per_minute"
        config1.config_value = "60"
        config2 = MagicMock()
        config2.config_key = "settlement_delay_days"
        config2.config_value = "30"

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [config1, config2]
        session.execute = AsyncMock(return_value=result_mock)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.common.b14_config_util.DatabaseManager"
        ) as mock_db, \
             patch(
                 "src.common.b14_config_util.RedisClient"
             ) as mock_redis:
            mock_db.get_session.return_value = cm
            mock_redis.set_json = AsyncMock()

            await B14ConfigUtil.load_all()

        assert B14ConfigUtil._cache_loaded is True
        assert B14ConfigUtil._memory_cache["admin_rate_limit_per_minute"] == "60"
        assert B14ConfigUtil._memory_cache["settlement_delay_days"] == "30"
        mock_redis.set_json.assert_awaited()

    @pytest.mark.asyncio
    async def test_load_all_db_failure_fallback_redis(self):
        """load_all：DB 异常 → 降级 Redis"""
        from src.common.b14_config_util import B14ConfigUtil

        with patch(
            "src.common.b14_config_util.DatabaseManager"
        ) as mock_db, \
             patch(
                 "src.common.b14_config_util.RedisClient"
             ) as mock_redis:
            mock_db.get_session.side_effect = Exception("DB down")
            mock_redis.get_json = AsyncMock(
                return_value={"admin_rate_limit_per_minute": "100"}
            )
            mock_redis.set_json = AsyncMock()

            await B14ConfigUtil.load_all()

        assert B14ConfigUtil._cache_loaded is True
        assert B14ConfigUtil._memory_cache["admin_rate_limit_per_minute"] == "100"

    @pytest.mark.asyncio
    async def test_load_all_redis_write_failure_ignored(self):
        """load_all：Redis 写入失败 → 不抛异常"""
        from src.common.b14_config_util import B14ConfigUtil

        config1 = MagicMock()
        config1.config_key = "k1"
        config1.config_value = "v1"

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [config1]
        session.execute = AsyncMock(return_value=result_mock)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.common.b14_config_util.DatabaseManager"
        ) as mock_db, \
             patch(
                 "src.common.b14_config_util.RedisClient"
             ) as mock_redis:
            mock_db.get_session.return_value = cm
            mock_redis.set_json = AsyncMock(side_effect=Exception("Redis down"))

            # 不应抛异常
            await B14ConfigUtil.load_all()
        assert B14ConfigUtil._cache_loaded is True

    @pytest.mark.asyncio
    async def test_get_from_memory_hit(self):
        """get：内存命中"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "value1"}
        B14ConfigUtil._cache_loaded = True

        result = await B14ConfigUtil.get("k1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_from_registry_default(self):
        """get：内存未命中 → 注册表默认值"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._cache_loaded = True
        # 注册表中存在的 key（取自 b14_constants.B14_CONFIG_REGISTRY）
        registry_key = next(iter(B14_CONFIG_REGISTRY.keys()))

        result = await B14ConfigUtil.get(registry_key)
        assert result == B14_CONFIG_REGISTRY[registry_key]["default"]

    @pytest.mark.asyncio
    async def test_get_unknown_key_returns_default(self):
        """get：未知 key → 返回 default 参数"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._cache_loaded = True
        result = await B14ConfigUtil.get("nonexistent_key", default="fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_get_str(self):
        """get_str：字符串转换"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "123"}
        B14ConfigUtil._cache_loaded = True
        assert await B14ConfigUtil.get_str("k1") == "123"
        assert await B14ConfigUtil.get_str("missing", default="def") == "def"

    @pytest.mark.asyncio
    async def test_get_int_valid(self):
        """get_int：合法整数"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "42"}
        B14ConfigUtil._cache_loaded = True
        assert await B14ConfigUtil.get_int("k1") == 42

    @pytest.mark.asyncio
    async def test_get_int_invalid_returns_default(self):
        """get_int：非法值 → 返回默认"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "not_a_number"}
        B14ConfigUtil._cache_loaded = True
        assert await B14ConfigUtil.get_int("k1", default=99) == 99

    @pytest.mark.asyncio
    async def test_get_int_from_registry_default(self):
        """get_int：default=None → 注册表默认值"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._cache_loaded = True
        # 使用注册表中已知 key
        registry_key = next(iter(B14_CONFIG_REGISTRY.keys()))
        expected_default = int(B14_CONFIG_REGISTRY[registry_key]["default"])

        # 内存未命中时返回注册表默认值字符串，再转 int
        result = await B14ConfigUtil.get_int(registry_key)
        assert result == expected_default

    @pytest.mark.asyncio
    async def test_get_bool_various_inputs(self):
        """get_bool：多种输入转换"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._cache_loaded = True

        B14ConfigUtil._memory_cache = {"k1": "true", "k2": "1", "k3": "yes", "k4": "on"}
        assert await B14ConfigUtil.get_bool("k1") is True
        assert await B14ConfigUtil.get_bool("k2") is True
        assert await B14ConfigUtil.get_bool("k3") is True
        assert await B14ConfigUtil.get_bool("k4") is True

        B14ConfigUtil._memory_cache = {"k5": "false", "k6": "0", "k7": "no"}
        assert await B14ConfigUtil.get_bool("k5") is False
        assert await B14ConfigUtil.get_bool("k6") is False
        assert await B14ConfigUtil.get_bool("k7") is False

    @pytest.mark.asyncio
    async def test_get_decimal_valid(self):
        """get_decimal：合法 Decimal"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "99.50"}
        B14ConfigUtil._cache_loaded = True
        result = await B14ConfigUtil.get_decimal("k1")
        assert result == Decimal("99.50")

    @pytest.mark.asyncio
    async def test_get_decimal_invalid_returns_default(self):
        """get_decimal：非法值 → 默认"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "not_a_decimal"}
        B14ConfigUtil._cache_loaded = True
        result = await B14ConfigUtil.get_decimal("k1", default=Decimal("0.01"))
        assert result == Decimal("0.01")

    @pytest.mark.asyncio
    async def test_get_json_valid(self):
        """get_json：合法 JSON 字符串"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": '{"a": 1, "b": "x"}'}
        B14ConfigUtil._cache_loaded = True
        result = await B14ConfigUtil.get_json("k1")
        assert result == {"a": 1, "b": "x"}

    @pytest.mark.asyncio
    async def test_get_json_invalid_returns_default(self):
        """get_json：非法 JSON → 默认"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "not_json"}
        B14ConfigUtil._cache_loaded = True
        result = await B14ConfigUtil.get_json("k1", default={"fallback": True})
        assert result == {"fallback": True}

    @pytest.mark.asyncio
    async def test_invalidate_single_key(self):
        """invalidate：单 key 失效"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "v1", "k2": "v2"}
        B14ConfigUtil._cache_loaded = True

        with patch(
            "src.common.b14_config_util.RedisClient"
        ) as mock_redis:
            mock_redis.set_json = AsyncMock()
            await B14ConfigUtil.invalidate("k1")

        assert "k1" not in B14ConfigUtil._memory_cache
        assert "k2" in B14ConfigUtil._memory_cache

    @pytest.mark.asyncio
    async def test_invalidate_all(self):
        """invalidate：key=None 全量刷新"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "v1", "k2": "v2"}
        B14ConfigUtil._cache_loaded = True

        config1 = MagicMock()
        config1.config_key = "new_k"
        config1.config_value = "new_v"
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [config1]
        session.execute = AsyncMock(return_value=result_mock)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.common.b14_config_util.DatabaseManager"
        ) as mock_db, \
             patch(
                 "src.common.b14_config_util.RedisClient"
             ) as mock_redis:
            mock_db.get_session.return_value = cm
            mock_redis.delete = AsyncMock()
            mock_redis.set_json = AsyncMock()

            await B14ConfigUtil.invalidate(None)

        # 全量刷新后内存只剩新加载的 new_k
        assert "k1" not in B14ConfigUtil._memory_cache
        assert B14ConfigUtil._memory_cache.get("new_k") == "new_v"

    @pytest.mark.asyncio
    async def test_set_value_success(self):
        """set：写入 DB + 内存 + Redis"""
        from src.common.b14_config_util import B14ConfigUtil

        # 构造 DB session：先 select 无记录，再 add 新配置
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.common.b14_config_util.DatabaseManager"
        ) as mock_db, \
             patch(
                 "src.common.b14_config_util.RedisClient"
             ) as mock_redis:
            mock_db.get_session.return_value = cm
            mock_redis.set_json = AsyncMock()

            await B14ConfigUtil.set("new_key", "new_value")

        assert B14ConfigUtil._memory_cache["new_key"] == "new_value"
        session.add.assert_called_once()
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_set_value_dict_serialized(self):
        """set：dict/list 自动 JSON 序列化"""
        from src.common.b14_config_util import B14ConfigUtil

        existing_config = MagicMock()
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing_config
        session.execute = AsyncMock(return_value=result_mock)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.common.b14_config_util.DatabaseManager"
        ) as mock_db, \
             patch(
                 "src.common.b14_config_util.RedisClient"
             ) as mock_redis:
            mock_db.get_session.return_value = cm
            mock_redis.set_json = AsyncMock()

            await B14ConfigUtil.set("json_key", {"a": 1, "b": [2, 3]})

        # dict 被序列化为 JSON 字符串
        import json
        assert json.loads(B14ConfigUtil._memory_cache["json_key"]) == {
            "a": 1,
            "b": [2, 3],
        }

    @pytest.mark.asyncio
    async def test_set_db_failure_raises(self):
        """set：DB 写入失败 → 抛异常"""
        from src.common.b14_config_util import B14ConfigUtil

        with patch(
            "src.common.b14_config_util.DatabaseManager"
        ) as mock_db:
            mock_db.get_session.side_effect = Exception("DB down")

            with pytest.raises(Exception, match="DB down"):
                await B14ConfigUtil.set("k1", "v1")

    def test_get_all_memory(self):
        """get_all_memory：返回内存副本"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"k1": "v1", "k2": "v2"}
        snapshot = B14ConfigUtil.get_all_memory()
        assert snapshot == {"k1": "v1", "k2": "v2"}
        # 修改副本不影响原数据
        snapshot["k3"] = "v3"
        assert "k3" not in B14ConfigUtil._memory_cache

    @pytest.mark.asyncio
    async def test_refresh_clears_and_reloads(self):
        """refresh：清空内存 + Redis 删除 + 重新加载"""
        from src.common.b14_config_util import B14ConfigUtil

        B14ConfigUtil._memory_cache = {"old": "data"}
        B14ConfigUtil._cache_loaded = True

        new_config = MagicMock()
        new_config.config_key = "fresh"
        new_config.config_value = "value"
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [new_config]
        session.execute = AsyncMock(return_value=result_mock)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.common.b14_config_util.DatabaseManager"
        ) as mock_db, \
             patch(
                 "src.common.b14_config_util.RedisClient"
             ) as mock_redis:
            mock_db.get_session.return_value = cm
            mock_redis.delete = AsyncMock()
            mock_redis.set_json = AsyncMock()

            await B14ConfigUtil.refresh()

        assert "old" not in B14ConfigUtil._memory_cache
        assert B14ConfigUtil._memory_cache["fresh"] == "value"
        mock_redis.delete.assert_awaited()
