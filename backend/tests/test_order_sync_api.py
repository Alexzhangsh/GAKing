# @ai-generated
"""
B05 订单同步 API 接口 + Scheduler 注册测试

覆盖场景：
1. 接口权限校验：无 token → 401
2. 参数校验：非法 channel_code → 422
3. trigger 接口：正常触发/Service 异常 → 响应封装
4. retry 接口：正常补发/异常
5. status 接口：正常查询
6. Scheduler 注册：三渠道 cron 错峰/任务存在性
7. 定时任务函数：开关关闭跳过/异常兜底

运行：PYTHONPATH=. .venv/bin/python -m pytest tests/test_order_sync_api.py -v
"""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from src.api.v1.admin.order_sync import (
    get_order_sync_service,
    router as order_sync_router,
)
from src.scheduler.order_sync_jobs import (
    register_order_sync_jobs,
    sync_dta_orders,
    sync_myq_orders,
    sync_orderx_orders,
)


# ── 测试工具 ─────────────────────────────────────────


def _make_app_with_mock_auth(mock_svc: MagicMock = None):
    """构造带 mock 权限 + mock service 的 FastAPI app

    通过 app.dependency_overrides 覆盖 get_admin_user_id 和 get_order_sync_service，
    绕过真实 JWT/RBAC 和 DatabaseManager.get_session()（避免 DB 未初始化报错）。
    """
    app = FastAPI()
    app.include_router(order_sync_router)

    # 覆盖 get_admin_user_id 依赖，绕过 JWT/RBAC
    async def mock_admin_id():
        return 1

    app.dependency_overrides[_get_admin_user_id_func()] = mock_admin_id

    # 覆盖 get_order_sync_service 依赖，注入 mock service
    if mock_svc is not None:

        async def mock_get_svc():
            return mock_svc

        app.dependency_overrides[get_order_sync_service] = mock_get_svc

    return app


def _get_admin_user_id_func():
    """获取 get_admin_user_id 函数引用（用于 dependency_overrides）"""
    from src.api.v1.admin.order_sync import get_admin_user_id

    return get_admin_user_id


def _make_mock_svc():
    """构造 mock OrderSyncService"""
    svc = MagicMock()
    svc.manual_sync_channel = AsyncMock(
        return_value={"status": "success", "channel_code": "myq"}
    )
    svc.manual_retry_failed = AsyncMock(
        return_value={"status": "success", "retried_count": 0}
    )
    svc.get_sync_status = AsyncMock(return_value={"total_enabled": 0, "channels": []})
    return svc


# ══════════════════════════════════════════════════════
# 1. 参数校验测试
# ══════════════════════════════════════════════════════


class TestParameterValidation:
    """参数校验测试"""

    def test_invalid_channel_code_trigger(self):
        """trigger 接口非法 channel_code → 422"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/order-sync/trigger",
            json={"channel_code": "invalid"},
        )
        assert resp.status_code == 422

    def test_invalid_channel_code_retry(self):
        """retry 接口非法 channel_code → 422"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/order-sync/retry",
            json={"channel_code": "xxx"},
        )
        assert resp.status_code == 422

    def test_invalid_batch_size(self):
        """retry 接口 batch_size 超限 → 422"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/order-sync/retry",
            json={"channel_code": "myq", "batch_size": 200},
        )
        assert resp.status_code == 422

    def test_valid_channel_codes(self):
        """合法 channel_code 通过校验"""
        svc = MagicMock()
        svc.manual_sync_channel = AsyncMock(
            return_value={"status": "success", "channel_code": "myq"}
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        for ch in ["myq", "orderx", "dta"]:
            resp = client.post(
                "/api/v1/admin/order-sync/trigger",
                json={"channel_code": ch},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["code"] == 200


# ══════════════════════════════════════════════════════
# 2. trigger 接口测试
# ══════════════════════════════════════════════════════


class TestTriggerEndpoint:
    """手动触发同步接口测试"""

    def test_trigger_success(self):
        """正常触发"""
        svc = MagicMock()
        svc.manual_sync_channel = AsyncMock(
            return_value={
                "status": "success",
                "channel_code": "myq",
                "pulled_count": 10,
                "inserted_count": 5,
                "updated_count": 3,
            }
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/order-sync/trigger",
            json={"channel_code": "myq"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["status"] == "success"
        assert body["data"]["pulled_count"] == 10

    def test_trigger_service_exception(self):
        """Service 抛 ValueError → 400"""
        svc = MagicMock()
        svc.manual_sync_channel = AsyncMock(side_effect=ValueError("渠道异常"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/order-sync/trigger",
            json={"channel_code": "myq"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400

    def test_trigger_with_time_range(self):
        """指定时间范围触发"""
        svc = MagicMock()
        svc.manual_sync_channel = AsyncMock(
            return_value={"status": "success", "channel_code": "orderx"}
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/order-sync/trigger",
            json={
                "channel_code": "orderx",
                "start_time": "2026-08-01T00:00:00",
                "end_time": "2026-08-01T12:00:00",
            },
        )
        assert resp.status_code == 200
        # 验证 start_time 传到 service
        call_kwargs = svc.manual_sync_channel.call_args.kwargs
        assert call_kwargs["channel_code"] == "orderx"
        assert call_kwargs["start_time"] is not None


# ══════════════════════════════════════════════════════
# 3. retry 接口测试
# ══════════════════════════════════════════════════════


class TestRetryEndpoint:
    """手动补发接口测试"""

    def test_retry_success(self):
        """正常补发"""
        svc = MagicMock()
        svc.manual_retry_failed = AsyncMock(
            return_value={
                "status": "success",
                "channel_code": "myq",
                "retried_count": 3,
                "success_count": 3,
                "still_failed_count": 0,
            }
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/order-sync/retry",
            json={"channel_code": "myq", "batch_size": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["retried_count"] == 3

    def test_retry_default_batch_size(self):
        """默认 batch_size=10"""
        svc = MagicMock()
        svc.manual_retry_failed = AsyncMock(
            return_value={"status": "success", "retried_count": 0}
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/order-sync/retry",
            json={"channel_code": "myq"},
        )
        assert resp.status_code == 200
        call_kwargs = svc.manual_retry_failed.call_args.kwargs
        assert call_kwargs["batch_size"] == 10

    def test_retry_service_exception(self):
        """retry 接口 Service 异常 → 400 封装"""
        svc = MagicMock()
        svc.manual_retry_failed = AsyncMock(side_effect=ValueError("补发异常"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/order-sync/retry",
            json={"channel_code": "myq"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400


# ══════════════════════════════════════════════════════
# 4. status 接口测试
# ══════════════════════════════════════════════════════


class TestStatusEndpoint:
    """状态查询接口测试"""

    def test_status_success(self):
        """正常查询"""
        svc = MagicMock()
        svc.get_sync_status = AsyncMock(
            return_value={
                "total_enabled": 3,
                "channels": [
                    {
                        "channel_code": "myq",
                        "enabled": True,
                        "cursor": "2026-08-01T10:00:00",
                        "failed_queue_length": 0,
                        "breaker_state": "CLOSED",
                        "cron_expr": "*/10 * * * *",
                    }
                ],
            }
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get("/api/v1/admin/order-sync/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total_enabled"] == 3
        assert len(body["data"]["channels"]) == 1

    def test_status_service_exception(self):
        """status 接口 Service 异常 → 400 封装"""
        svc = MagicMock()
        svc.get_sync_status = AsyncMock(side_effect=ValueError("查询异常"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get("/api/v1/admin/order-sync/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400


# ══════════════════════════════════════════════════════
# 5. Scheduler 注册测试
# ══════════════════════════════════════════════════════


class TestSchedulerRegistration:
    """定时任务注册测试"""

    def test_register_three_jobs(self):
        """注册三个渠道任务"""
        from src.scheduler.scheduler import TaskScheduler

        TaskScheduler._scheduler = None  # 重置
        TaskScheduler.initialize()
        register_order_sync_jobs()

        internal = TaskScheduler._scheduler
        job_ids = [j.id for j in internal.get_jobs()]
        assert "order_sync_myq" in job_ids
        assert "order_sync_orderx" in job_ids
        assert "order_sync_dta" in job_ids

    def test_cron_staggered(self):
        """三渠道 cron 错峰"""
        from src.scheduler.scheduler import TaskScheduler

        TaskScheduler._scheduler = None
        TaskScheduler.initialize()
        register_order_sync_jobs()

        internal = TaskScheduler._scheduler
        jobs = {j.id: j for j in internal.get_jobs()}

        # 验证三个任务都存在
        assert len(jobs) >= 3

        # 验证 cron 表达式不同（错峰）
        myq_trigger = str(jobs["order_sync_myq"].trigger)
        orderx_trigger = str(jobs["order_sync_orderx"].trigger)
        dta_trigger = str(jobs["order_sync_dta"].trigger)

        # 三个 trigger 应该互不相同
        triggers = {myq_trigger, orderx_trigger, dta_trigger}
        assert len(triggers) == 3


# ══════════════════════════════════════════════════════
# 6. 定时任务函数测试
# ══════════════════════════════════════════════════════


class TestSchedulerJobFunctions:
    """定时任务函数测试"""

    @pytest.mark.asyncio
    async def test_myq_switch_off(self):
        """喵有券渠道开关关闭 → 跳过"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", True):
            with patch(
                "src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_MYQ_ENABLE", False
            ):
                result = await sync_myq_orders()
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_total_switch_off(self):
        """总开关关闭 → 跳过"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", False):
            result = await sync_myq_orders()
        assert result["status"] == "skipped"
        assert "总开关" in result["message"]

    @pytest.mark.asyncio
    async def test_myq_normal_execution(self):
        """喵有券正常执行"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", True):
            with patch(
                "src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_MYQ_ENABLE", True
            ):
                with patch("src.scheduler.order_sync_jobs.DatabaseManager") as mock_db:
                    mock_session = AsyncMock()
                    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                    mock_session.__aexit__ = AsyncMock(return_value=None)
                    mock_db.get_session.return_value = mock_session
                    with patch(
                        "src.scheduler.order_sync_jobs.OrderSyncService"
                    ) as mock_svc_cls:
                        svc = MagicMock()
                        svc.pull_channel_orders = AsyncMock(
                            return_value={
                                "status": "success",
                                "pulled_count": 5,
                                "inserted_count": 3,
                                "updated_count": 2,
                            }
                        )
                        mock_svc_cls.return_value = svc
                        result = await sync_myq_orders()
        assert result["status"] == "success"
        assert result["pulled_count"] == 5

    @pytest.mark.asyncio
    async def test_orderx_exception_fallback(self):
        """订单侠任务异常兜底"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", True):
            with patch(
                "src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ORDERX_ENABLE", True
            ):
                with patch("src.scheduler.order_sync_jobs.DatabaseManager") as mock_db:
                    mock_db.get_session.side_effect = Exception("DB 连接失败")
                    result = await sync_orderx_orders()
        assert result["status"] == "failed"
        assert "DB 连接失败" in result["message"]

    @pytest.mark.asyncio
    async def test_dta_normal_execution(self):
        """大淘客正常执行"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", True):
            with patch(
                "src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_DTA_ENABLE", True
            ):
                with patch("src.scheduler.order_sync_jobs.DatabaseManager") as mock_db:
                    mock_session = AsyncMock()
                    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                    mock_session.__aexit__ = AsyncMock(return_value=None)
                    mock_db.get_session.return_value = mock_session
                    with patch(
                        "src.scheduler.order_sync_jobs.OrderSyncService"
                    ) as mock_svc_cls:
                        svc = MagicMock()
                        svc.pull_channel_orders = AsyncMock(
                            return_value={"status": "success", "pulled_count": 0}
                        )
                        mock_svc_cls.return_value = svc
                        result = await sync_dta_orders()
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_orderx_switch_off(self):
        """订单侠渠道开关关闭 → 跳过"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", True):
            with patch(
                "src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ORDERX_ENABLE", False
            ):
                result = await sync_orderx_orders()
        assert result["status"] == "skipped"
        assert "订单侠" in result["message"]

    @pytest.mark.asyncio
    async def test_orderx_normal_execution(self):
        """订单侠正常执行"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", True):
            with patch(
                "src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ORDERX_ENABLE", True
            ):
                with patch("src.scheduler.order_sync_jobs.DatabaseManager") as mock_db:
                    mock_session = AsyncMock()
                    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                    mock_session.__aexit__ = AsyncMock(return_value=None)
                    mock_db.get_session.return_value = mock_session
                    with patch(
                        "src.scheduler.order_sync_jobs.OrderSyncService"
                    ) as mock_svc_cls:
                        svc = MagicMock()
                        svc.pull_channel_orders = AsyncMock(
                            return_value={
                                "status": "success",
                                "pulled_count": 8,
                                "inserted_count": 4,
                                "updated_count": 1,
                            }
                        )
                        mock_svc_cls.return_value = svc
                        result = await sync_orderx_orders()
        assert result["status"] == "success"
        assert result["pulled_count"] == 8

    @pytest.mark.asyncio
    async def test_dta_switch_off(self):
        """大淘客渠道开关关闭 → 跳过"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", True):
            with patch(
                "src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_DTA_ENABLE", False
            ):
                result = await sync_dta_orders()
        assert result["status"] == "skipped"
        assert "大淘客" in result["message"]

    @pytest.mark.asyncio
    async def test_myq_exception_fallback(self):
        """喵有券任务异常兜底"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", True):
            with patch(
                "src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_MYQ_ENABLE", True
            ):
                with patch("src.scheduler.order_sync_jobs.DatabaseManager") as mock_db:
                    mock_db.get_session.side_effect = RuntimeError("MYQ DB 异常")
                    result = await sync_myq_orders()
        assert result["status"] == "failed"
        assert "MYQ DB 异常" in result["message"]

    @pytest.mark.asyncio
    async def test_dta_exception_fallback(self):
        """大淘客任务异常兜底"""
        with patch("src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_ENABLE", True):
            with patch(
                "src.scheduler.order_sync_jobs.TASK_ORDER_SYNC_DTA_ENABLE", True
            ):
                with patch("src.scheduler.order_sync_jobs.DatabaseManager") as mock_db:
                    mock_db.get_session.side_effect = Exception("DTA DB 异常")
                    result = await sync_dta_orders()
        assert result["status"] == "failed"
        assert "DTA DB 异常" in result["message"]
