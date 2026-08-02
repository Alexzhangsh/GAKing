# @ai-generated
"""
B07 佣金结算 API 接口 + Scheduler 任务测试

覆盖场景：
1. 接口参数校验：非法 flow_type / transfer_status / channel_code → 422
2. settle/batch 接口：正常触发/Service 异常 → 响应封装
3. settle/single 接口：正常/订单不存在/状态非 SETTLED
4. refund-deduct/batch 接口：单笔模式/批量模式
5. refund-deduct/single 接口：正常/异常
6. recalculate 接口：正常/已锁定拒绝
7. flows 查询接口：正常/筛选/分页
8. orders 查询接口：正常/筛选/分页
9. Scheduler 注册：两任务 cron/任务存在性
10. 定时任务函数：开关关闭跳过/异常兜底/正常执行

运行：PYTHONPATH=. .venv/bin/python -m pytest tests/test_commission_settlement_api.py -v
"""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from src.api.v1.admin.commission_settlement import (
    get_settlement_service,
    router as commission_settlement_router,
)
from src.scheduler.commission_settlement_jobs import (
    batch_settle_commissions,
    deduct_single_order_job,
    process_refund_deductions_job,
    register_commission_settlement_jobs,
    settle_single_order_job,
)


# ── 测试工具 ─────────────────────────────────────────


def _get_admin_user_id_func():
    """获取 get_admin_user_id 函数引用（用于 dependency_overrides）"""
    from src.api.v1.admin.commission_settlement import get_admin_user_id

    return get_admin_user_id


def _make_app_with_mock_auth(mock_svc: MagicMock = None):
    """构造带 mock 权限 + mock service 的 FastAPI app

    通过 app.dependency_overrides 覆盖 get_admin_user_id 和 get_settlement_service，
    绕过真实 JWT/RBAC 和 DatabaseManager.get_session()（避免 DB 未初始化报错）。
    """
    app = FastAPI()
    app.include_router(commission_settlement_router)

    # 覆盖 get_admin_user_id 依赖，绕过 JWT/RBAC
    async def mock_admin_id():
        return 1

    app.dependency_overrides[_get_admin_user_id_func()] = mock_admin_id

    # 覆盖 get_settlement_service 依赖，注入 mock service
    if mock_svc is not None:

        async def mock_get_svc():
            return mock_svc

        app.dependency_overrides[get_settlement_service] = mock_get_svc

    return app


def _make_mock_svc():
    """构造 mock CommissionSettlementService"""
    svc = MagicMock()
    svc.batch_settle_orders = AsyncMock(
        return_value={
            "status": "success",
            "total": 2,
            "success_count": 2,
            "failed_count": 0,
            "skipped_count": 0,
            "details": [],
        }
    )
    svc.settle_single_order = AsyncMock(
        return_value={
            "status": "success",
            "order_id": 1,
            "flow_id": 100,
            "amount": 80.0,
            "transfer_batch_id": "B07_SETTLE_xxx_1",
        }
    )
    svc.process_refund_deductions = AsyncMock(
        return_value={
            "status": "success",
            "total": 1,
            "success_count": 1,
            "failed_count": 0,
            "skipped_count": 0,
            "details": [],
        }
    )
    svc.process_single_refund = AsyncMock(
        return_value={
            "status": "success",
            "order_id": 1,
            "deduct_flow_id": 200,
            "deduct_amount": 80.0,
        }
    )
    svc.recalculate_order_commission = AsyncMock(
        return_value={
            "order_id": 1,
            "old_user_commission": 80.0,
            "new_user_commission": 85.0,
            "old_platform_commission": 20.0,
            "new_platform_commission": 15.0,
            "user_rate": 0.85,
            "platform_rate": 0.15,
        }
    )
    svc.list_settlement_flows = AsyncMock(
        return_value={
            "list": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }
    )
    svc.list_settlement_orders = AsyncMock(
        return_value={
            "list": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }
    )
    return svc


# ══════════════════════════════════════════════════════
# 1. 参数校验测试
# ══════════════════════════════════════════════════════


class TestParameterValidation:
    """参数校验测试"""

    def test_invalid_flow_type(self):
        """flows 接口非法 flow_type → 422"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/flows",
            params={"flow_type": "INVALID"},
        )
        assert resp.status_code == 422

    def test_invalid_transfer_status(self):
        """flows 接口非法 transfer_status → 422"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/flows",
            params={"transfer_status": "XXX"},
        )
        assert resp.status_code == 422

    def test_invalid_channel_code(self):
        """orders 接口非法 channel_code → 422"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/orders",
            params={"channel_code": "invalid"},
        )
        assert resp.status_code == 422

    def test_invalid_order_status_range(self):
        """orders 接口 order_status 超范围 → 422"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/orders",
            params={"order_status": 99},
        )
        assert resp.status_code == 422

    def test_invalid_order_id_in_recalculate(self):
        """recalculate 接口 order_id <= 0 → 422"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/recalculate",
            json={"order_id": 0},
        )
        assert resp.status_code == 422

    def test_invalid_limit_in_settle_batch(self):
        """settle/batch 接口 limit 超限 → 422"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/settle/batch",
            json={"limit": 99999},
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════
# 2. 批量结算接口测试
# ══════════════════════════════════════════════════════


class TestBatchSettleEndpoint:
    """批量结算接口测试"""

    def test_batch_settle_success(self):
        """批量结算正常触发"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/settle/batch",
            json={"limit": 100},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["status"] == "success"
        assert body["data"]["success_count"] == 2
        svc.batch_settle_orders.assert_awaited_once_with(limit=100)

    def test_batch_settle_default_limit(self):
        """批量结算默认 limit"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/settle/batch",
            json={},
        )
        assert resp.status_code == 200
        # 默认 limit 来自 TASK_BATCH_SETTLE_BATCH_SIZE
        from src.config.b07_constants import TASK_BATCH_SETTLE_BATCH_SIZE

        svc.batch_settle_orders.assert_awaited_once_with(
            limit=TASK_BATCH_SETTLE_BATCH_SIZE
        )

    def test_batch_settle_service_exception(self):
        """批量结算 Service 异常 → 400 封装"""
        svc = _make_mock_svc()
        svc.batch_settle_orders = AsyncMock(side_effect=ValueError("DB 异常"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/settle/batch",
            json={"limit": 100},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400
        assert "DB 异常" in body["msg"]


# ══════════════════════════════════════════════════════
# 3. 单笔结算接口测试
# ══════════════════════════════════════════════════════


class TestSettleSingleEndpoint:
    """单笔结算接口测试"""

    def test_settle_single_success(self):
        """单笔结算正常"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/settle/single",
            json={"order_id": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "success"
        assert body["data"]["flow_id"] == 100
        svc.settle_single_order.assert_awaited_once_with(1)

    def test_settle_single_order_not_found(self):
        """单笔结算订单不存在 → 400"""
        svc = _make_mock_svc()
        svc.settle_single_order = AsyncMock(
            side_effect=ValueError("订单不存在: order_id=999")
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/settle/single",
            json={"order_id": 999},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400

    def test_settle_single_wrong_status(self):
        """单笔结算订单状态非 SETTLED → 400"""
        svc = _make_mock_svc()
        svc.settle_single_order = AsyncMock(
            side_effect=ValueError("订单状态非 SETTLED")
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/settle/single",
            json={"order_id": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400


# ══════════════════════════════════════════════════════
# 4. 退款扣减接口测试
# ══════════════════════════════════════════════════════


class TestRefundDeductEndpoint:
    """退款扣减接口测试"""

    def test_batch_refund_deduct_single_mode(self):
        """批量退款扣减接口 - 单笔模式（order_id 非空）"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/refund-deduct/batch",
            json={"order_id": 1, "limit": 100},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "success"
        # 单笔模式调用 process_single_refund
        svc.process_single_refund.assert_awaited_once_with(1)
        svc.process_refund_deductions.assert_not_awaited()

    def test_batch_refund_deduct_batch_mode(self):
        """批量退款扣减接口 - 批量模式（order_id 为空）"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/refund-deduct/batch",
            json={"limit": 50},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "success"
        svc.process_refund_deductions.assert_awaited_once_with(limit=50)
        svc.process_single_refund.assert_not_awaited()

    def test_refund_deduct_single_success(self):
        """单笔退款扣减正常"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/refund-deduct/single",
            json={"order_id": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["deduct_flow_id"] == 200
        svc.process_single_refund.assert_awaited_once_with(1)

    def test_refund_deduct_single_exception(self):
        """单笔退款扣减异常 → 400"""
        svc = _make_mock_svc()
        svc.process_single_refund = AsyncMock(
            side_effect=ValueError("订单状态非 REFUNDED")
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/refund-deduct/single",
            json={"order_id": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400


# ══════════════════════════════════════════════════════
# 5. 佣金重算接口测试
# ══════════════════════════════════════════════════════


class TestRecalculateEndpoint:
    """佣金重算接口测试"""

    def test_recalculate_success(self):
        """重算正常"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/recalculate",
            json={"order_id": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["new_user_commission"] == 85.0
        svc.recalculate_order_commission.assert_awaited_once_with(1)

    def test_recalculate_locked(self):
        """重算已锁定订单 → 400"""
        svc = _make_mock_svc()
        svc.recalculate_order_commission = AsyncMock(
            side_effect=ValueError("订单已生成佣金流水，锁定不可重算")
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/recalculate",
            json={"order_id": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400
        assert "锁定" in body["msg"]


# ══════════════════════════════════════════════════════
# 6. 查询接口测试
# ══════════════════════════════════════════════════════


class TestQueryEndpoints:
    """查询接口测试"""

    def test_list_flows_success(self):
        """流水查询正常"""
        svc = _make_mock_svc()
        svc.list_settlement_flows = AsyncMock(
            return_value={
                "list": [{"id": 1, "flow_type": "ORDER"}],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/flows",
            params={"user_id": 10001, "flow_type": "ORDER", "page": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 1
        assert len(body["data"]["list"]) == 1
        svc.list_settlement_flows.assert_awaited_once()

    def test_list_flows_with_all_filters(self):
        """流水查询全部筛选条件"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/flows",
            params={
                "user_id": 10001,
                "order_id": 1,
                "flow_type": "DEDUCT",
                "transfer_status": "SUCCESS",
                "page": 2,
                "page_size": 50,
            },
        )
        assert resp.status_code == 200
        call_kwargs = svc.list_settlement_flows.call_args.kwargs
        assert call_kwargs["user_id"] == 10001
        assert call_kwargs["order_id"] == 1
        assert call_kwargs["flow_type"] == "DEDUCT"
        assert call_kwargs["transfer_status"] == "SUCCESS"
        assert call_kwargs["page"] == 2
        assert call_kwargs["page_size"] == 50

    def test_list_orders_success(self):
        """订单查询正常"""
        svc = _make_mock_svc()
        svc.list_settlement_orders = AsyncMock(
            return_value={
                "list": [{"id": 1, "order_status": 40}],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/orders",
            params={"order_status": 40, "channel_code": "myq", "has_flow": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 1
        call_kwargs = svc.list_settlement_orders.call_args.kwargs
        assert call_kwargs["order_status"] == 40
        assert call_kwargs["channel_code"] == "myq"
        assert call_kwargs["has_flow"] is True

    def test_list_flows_service_exception(self):
        """流水查询 Service 异常 → 500 封装"""
        svc = _make_mock_svc()
        svc.list_settlement_flows = AsyncMock(side_effect=RuntimeError("内部错误"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/flows",
        )
        # RuntimeError（非 ValueError）→ code=500, http_status=500
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == 500


# ══════════════════════════════════════════════════════
# 7. Scheduler 注册测试
# ══════════════════════════════════════════════════════


class TestSchedulerRegistration:
    """定时任务注册测试"""

    def test_register_two_jobs(self):
        """注册两个佣金结算任务"""
        from src.scheduler.scheduler import TaskScheduler

        TaskScheduler._scheduler = None  # 重置
        TaskScheduler.initialize()
        register_commission_settlement_jobs()

        internal = TaskScheduler._scheduler
        job_ids = [j.id for j in internal.get_jobs()]
        assert "batch_settle_commissions" in job_ids
        assert "process_refund_deductions" in job_ids

    def test_cron_expressions(self):
        """验证 cron 表达式"""
        from src.scheduler.scheduler import TaskScheduler

        TaskScheduler._scheduler = None
        TaskScheduler.initialize()
        register_commission_settlement_jobs()

        internal = TaskScheduler._scheduler
        jobs = {j.id: j for j in internal.get_jobs()}

        # 批量结算每15分钟，退款扣减每10分钟
        assert "*/15" in str(jobs["batch_settle_commissions"].trigger)
        assert "*/10" in str(jobs["process_refund_deductions"].trigger)


# ══════════════════════════════════════════════════════
# 8. 定时任务函数测试
# ══════════════════════════════════════════════════════


class TestSchedulerJobFunctions:
    """定时任务函数测试"""

    @pytest.mark.asyncio
    async def test_batch_settle_switch_off(self):
        """批量结算任务开关关闭 → 跳过"""
        with patch(
            "src.scheduler.commission_settlement_jobs.TASK_BATCH_SETTLE_ENABLE",
            False,
        ):
            result = await batch_settle_commissions()
        assert result["status"] == "skipped"
        assert "开关关闭" in result["message"]

    @pytest.mark.asyncio
    async def test_refund_deduct_switch_off(self):
        """退款扣减任务开关关闭 → 跳过"""
        with patch(
            "src.scheduler.commission_settlement_jobs.TASK_REFUND_DEDUCT_ENABLE",
            False,
        ):
            result = await process_refund_deductions_job()
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_batch_settle_normal_execution(self):
        """批量结算正常执行"""
        with patch(
            "src.scheduler.commission_settlement_jobs.TASK_BATCH_SETTLE_ENABLE",
            True,
        ):
            with patch(
                "src.scheduler.commission_settlement_jobs.DatabaseManager"
            ) as mock_db:
                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                mock_db.get_session.return_value = mock_session
                with patch(
                    "src.scheduler.commission_settlement_jobs._build_service"
                ) as mock_build:
                    svc = MagicMock()
                    svc.batch_settle_orders = AsyncMock(
                        return_value={
                            "status": "success",
                            "total": 3,
                            "success_count": 3,
                            "failed_count": 0,
                            "skipped_count": 0,
                            "details": [],
                        }
                    )
                    mock_build.return_value = svc
                    result = await batch_settle_commissions()
        assert result["status"] == "success"
        assert result["total"] == 3
        assert result["success_count"] == 3

    @pytest.mark.asyncio
    async def test_batch_settle_exception_fallback(self):
        """批量结算任务异常兜底"""
        with patch(
            "src.scheduler.commission_settlement_jobs.TASK_BATCH_SETTLE_ENABLE",
            True,
        ):
            with patch(
                "src.scheduler.commission_settlement_jobs.DatabaseManager"
            ) as mock_db:
                mock_db.get_session.side_effect = Exception("DB 连接失败")
                result = await batch_settle_commissions()
        assert result["status"] == "failed"
        assert "DB 连接失败" in result["message"]

    @pytest.mark.asyncio
    async def test_refund_deduct_normal_execution(self):
        """退款扣减正常执行"""
        with patch(
            "src.scheduler.commission_settlement_jobs.TASK_REFUND_DEDUCT_ENABLE",
            True,
        ):
            with patch(
                "src.scheduler.commission_settlement_jobs.DatabaseManager"
            ) as mock_db:
                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                mock_db.get_session.return_value = mock_session
                with patch(
                    "src.scheduler.commission_settlement_jobs._build_service"
                ) as mock_build:
                    svc = MagicMock()
                    svc.process_refund_deductions = AsyncMock(
                        return_value={
                            "status": "success",
                            "total": 2,
                            "success_count": 2,
                            "failed_count": 0,
                            "skipped_count": 0,
                            "details": [],
                        }
                    )
                    mock_build.return_value = svc
                    result = await process_refund_deductions_job()
        assert result["status"] == "success"
        assert result["success_count"] == 2

    @pytest.mark.asyncio
    async def test_refund_deduct_exception_fallback(self):
        """退款扣减任务异常兜底"""
        with patch(
            "src.scheduler.commission_settlement_jobs.TASK_REFUND_DEDUCT_ENABLE",
            True,
        ):
            with patch(
                "src.scheduler.commission_settlement_jobs.DatabaseManager"
            ) as mock_db:
                mock_db.get_session.side_effect = RuntimeError("Redis 异常")
                result = await process_refund_deductions_job()
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_settle_single_order_job_success(self):
        """单笔结算任务正常"""
        with patch(
            "src.scheduler.commission_settlement_jobs.DatabaseManager"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_session
            with patch(
                "src.scheduler.commission_settlement_jobs._build_service"
            ) as mock_build:
                svc = MagicMock()
                svc.settle_single_order = AsyncMock(
                    return_value={
                        "status": "success",
                        "order_id": 5,
                        "flow_id": 99,
                    }
                )
                mock_build.return_value = svc
                result = await settle_single_order_job(order_id=5)
        assert result["status"] == "success"
        assert result["order_id"] == 5

    @pytest.mark.asyncio
    async def test_settle_single_order_job_exception(self):
        """单笔结算任务异常兜底"""
        with patch(
            "src.scheduler.commission_settlement_jobs.DatabaseManager"
        ) as mock_db:
            mock_db.get_session.side_effect = Exception("DB 异常")
            result = await settle_single_order_job(order_id=5)
        assert result["status"] == "failed"
        assert result["order_id"] == 5

    @pytest.mark.asyncio
    async def test_deduct_single_order_job_success(self):
        """单笔退款扣减任务正常"""
        with patch(
            "src.scheduler.commission_settlement_jobs.DatabaseManager"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_session
            with patch(
                "src.scheduler.commission_settlement_jobs._build_service"
            ) as mock_build:
                svc = MagicMock()
                svc.process_single_refund = AsyncMock(
                    return_value={
                        "status": "success",
                        "order_id": 7,
                        "deduct_flow_id": 88,
                    }
                )
                mock_build.return_value = svc
                result = await deduct_single_order_job(order_id=7)
        assert result["status"] == "success"
        assert result["order_id"] == 7

    @pytest.mark.asyncio
    async def test_deduct_single_order_job_exception(self):
        """单笔退款扣减任务异常兜底"""
        with patch(
            "src.scheduler.commission_settlement_jobs.DatabaseManager"
        ) as mock_db:
            mock_db.get_session.side_effect = Exception("DB 异常")
            result = await deduct_single_order_job(order_id=7)
        assert result["status"] == "failed"
        assert result["order_id"] == 7


# ══════════════════════════════════════════════════════
# 9. 配置加载器测试
# ══════════════════════════════════════════════════════


class TestConfigLoader:
    """配置加载器测试"""

    @pytest.mark.asyncio
    async def test_config_loader_redis_hit(self):
        """Redis 缓存命中"""
        from src.scheduler.commission_settlement_jobs import _make_config_loader

        mock_db = MagicMock()
        with patch(
            "src.scheduler.commission_settlement_jobs.RedisClient"
        ) as mock_redis:
            mock_redis.get = AsyncMock(return_value='{"NORMAL": {"user_rate": "0.85"}}')
            mock_redis.set_empty_cache = AsyncMock()
            mock_redis.set = AsyncMock()
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:default")
        assert result == '{"NORMAL": {"user_rate": "0.85"}}'
        mock_redis.get.assert_awaited_once_with("commission_rule:default")
        # 命中缓存不应查库
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_config_loader_empty_cache(self):
        """Redis 空标记命中 → 返回 None"""
        from src.scheduler.commission_settlement_jobs import _make_config_loader

        mock_db = MagicMock()
        with patch(
            "src.scheduler.commission_settlement_jobs.RedisClient"
        ) as mock_redis:
            mock_redis.get = AsyncMock(return_value="__EMPTY__")
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:default")
        assert result is None

    @pytest.mark.asyncio
    async def test_config_loader_db_fallback(self):
        """Redis 未命中 → 查库回填"""
        from src.scheduler.commission_settlement_jobs import _make_config_loader

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(
            return_value=('{"NORMAL": {"user_rate": "0.80"}}',)
        )
        mock_db.execute = AsyncMock(return_value=mock_result)
        with patch(
            "src.scheduler.commission_settlement_jobs.RedisClient"
        ) as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock()
            mock_redis.set_empty_cache = AsyncMock()
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:default")
        assert result == '{"NORMAL": {"user_rate": "0.80"}}'
        mock_redis.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_config_loader_db_not_found(self):
        """Redis 未命中 + 库无记录 → 空值防穿透"""
        from src.scheduler.commission_settlement_jobs import _make_config_loader

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)
        with patch(
            "src.scheduler.commission_settlement_jobs.RedisClient"
        ) as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set_empty_cache = AsyncMock()
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:default")
        assert result is None
        mock_redis.set_empty_cache.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_config_loader_db_exception(self):
        """查库异常 → 返回 None（兜底常量）"""
        from src.scheduler.commission_settlement_jobs import _make_config_loader

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB 异常"))
        with patch(
            "src.scheduler.commission_settlement_jobs.RedisClient"
        ) as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:default")
        assert result is None


# ══════════════════════════════════════════════════════
# 10. 补充：异常分支 & 依赖注入函数覆盖测试
# ══════════════════════════════════════════════════════


class TestAdditionalEndpointCoverage:
    """补充覆盖 endpoint 异常分支"""

    def test_batch_refund_deduct_single_mode_exception(self):
        """refund-deduct/batch 单笔模式 Service 异常 → 400"""
        svc = _make_mock_svc()
        svc.process_single_refund = AsyncMock(
            side_effect=ValueError("订单状态非 REFUNDED")
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/refund-deduct/batch",
            json={"order_id": 1, "limit": 100},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400

    def test_batch_refund_deduct_batch_mode_exception(self):
        """refund-deduct/batch 批量模式 Service 异常 → 400"""
        svc = _make_mock_svc()
        svc.process_refund_deductions = AsyncMock(
            side_effect=ValueError("批量扣减异常")
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/refund-deduct/batch",
            json={"limit": 50},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400

    def test_list_orders_service_exception(self):
        """orders 查询 Service 异常 → 500"""
        svc = _make_mock_svc()
        svc.list_settlement_orders = AsyncMock(side_effect=RuntimeError("内部错误"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/orders",
        )
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == 500

    def test_list_orders_value_error(self):
        """orders 查询 ValueError → 400"""
        svc = _make_mock_svc()
        svc.list_settlement_orders = AsyncMock(side_effect=ValueError("参数错误"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.get(
            "/api/v1/admin/commission-settlement/orders",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400

    def test_settle_batch_runtime_error(self):
        """settle/batch RuntimeError → 500"""
        svc = _make_mock_svc()
        svc.batch_settle_orders = AsyncMock(side_effect=RuntimeError("严重错误"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/settle/batch",
            json={"limit": 100},
        )
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == 500

    def test_settle_single_runtime_error(self):
        """settle/single RuntimeError → 500"""
        svc = _make_mock_svc()
        svc.settle_single_order = AsyncMock(side_effect=RuntimeError("严重错误"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/settle/single",
            json={"order_id": 1},
        )
        assert resp.status_code == 500

    def test_refund_deduct_single_runtime_error(self):
        """refund-deduct/single RuntimeError → 500"""
        svc = _make_mock_svc()
        svc.process_single_refund = AsyncMock(side_effect=RuntimeError("严重错误"))
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/refund-deduct/single",
            json={"order_id": 1},
        )
        assert resp.status_code == 500

    def test_recalculate_runtime_error(self):
        """recalculate RuntimeError → 500"""
        svc = _make_mock_svc()
        svc.recalculate_order_commission = AsyncMock(
            side_effect=RuntimeError("严重错误")
        )
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/recalculate",
            json={"order_id": 1},
        )
        assert resp.status_code == 500

    def test_batch_refund_deduct_default_limit(self):
        """refund-deduct/batch 批量模式默认 limit"""
        svc = _make_mock_svc()
        app = _make_app_with_mock_auth(svc)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/admin/commission-settlement/refund-deduct/batch",
            json={},
        )
        assert resp.status_code == 200
        from src.config.b07_constants import TASK_REFUND_DEDUCT_BATCH_SIZE

        svc.process_refund_deductions.assert_awaited_once_with(
            limit=TASK_REFUND_DEDUCT_BATCH_SIZE
        )


class TestDependencyFunctions:
    """依赖注入函数直接测试"""

    @pytest.mark.asyncio
    async def test_get_admin_user_id(self):
        """get_admin_user_id 从 payload 提取 user_id"""
        from src.api.v1.admin.commission_settlement import get_admin_user_id

        result = await get_admin_user_id(payload={"user_id": 42})
        assert result == 42

    @pytest.mark.asyncio
    async def test_get_db_session(self):
        """get_db 生成器 yield session"""
        from src.api.v1.admin.commission_settlement import get_db

        with patch("src.api.v1.admin.commission_settlement.DatabaseManager") as mock_db:
            mock_session = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_ctx

            gen = get_db()
            session = await gen.__anext__()
            assert session is mock_session
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

    @pytest.mark.asyncio
    async def test_api_config_loader_redis_hit(self):
        """API 层 config_loader Redis 命中"""
        from src.api.v1.admin.commission_settlement import _make_config_loader

        mock_db = MagicMock()
        with patch("src.api.v1.admin.commission_settlement.RedisClient") as mock_redis:
            mock_redis.get = AsyncMock(return_value='{"NORMAL": {"user_rate": "0.85"}}')
            mock_redis.set_empty_cache = AsyncMock()
            mock_redis.set = AsyncMock()
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:default")
        assert result == '{"NORMAL": {"user_rate": "0.85"}}'

    @pytest.mark.asyncio
    async def test_api_config_loader_empty_cache(self):
        """API 层 config_loader 空标记"""
        from src.api.v1.admin.commission_settlement import _make_config_loader

        mock_db = MagicMock()
        with patch("src.api.v1.admin.commission_settlement.RedisClient") as mock_redis:
            mock_redis.get = AsyncMock(return_value="__EMPTY__")
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:default")
        assert result is None

    @pytest.mark.asyncio
    async def test_api_config_loader_db_fallback(self):
        """API 层 config_loader DB 回填"""
        from src.api.v1.admin.commission_settlement import _make_config_loader

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(
            return_value=('{"NORMAL": {"user_rate": "0.80"}}',)
        )
        mock_db.execute = AsyncMock(return_value=mock_result)
        with patch("src.api.v1.admin.commission_settlement.RedisClient") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock()
            mock_redis.set_empty_cache = AsyncMock()
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:channel:myq")
        assert result == '{"NORMAL": {"user_rate": "0.80"}}'
        mock_redis.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_api_config_loader_db_not_found(self):
        """API 层 config_loader DB 无记录 → 空值防穿透"""
        from src.api.v1.admin.commission_settlement import _make_config_loader

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)
        with patch("src.api.v1.admin.commission_settlement.RedisClient") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set_empty_cache = AsyncMock()
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:default")
        assert result is None
        mock_redis.set_empty_cache.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_api_config_loader_db_exception(self):
        """API 层 config_loader DB 异常 → None"""
        from src.api.v1.admin.commission_settlement import _make_config_loader

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB 异常"))
        with patch("src.api.v1.admin.commission_settlement.RedisClient") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            loader = await _make_config_loader(mock_db)
            result = await loader("commission_rule:default")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_settlement_service(self):
        """get_settlement_service 构造 Service 实例"""
        from src.api.v1.admin.commission_settlement import get_settlement_service

        mock_db = AsyncMock()
        with patch(
            "src.api.v1.admin.commission_settlement._make_config_loader",
            AsyncMock(return_value=AsyncMock()),
        ):
            with patch(
                "src.api.v1.admin.commission_settlement.CommissionRuleEngine"
            ) as mock_engine_cls:
                mock_engine_cls.return_value = MagicMock()
                svc = await get_settlement_service(mock_db)
        assert svc is not None
        assert hasattr(svc, "batch_settle_orders")
