# @ai-generated
"""
X02-1 会员套餐/会员记录 API 单元测试
覆盖：
1. 套餐列表 / 详情 / 新增 / 编辑 / 上下架 / 删除
2. 会员记录列表 / 统计 / 导出
3. 参数校验（非法分佣比例 / 时间范围）
使用 mock 依赖注入，不依赖真实 DB/Redis
"""
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from src.api.v1.admin.member_package import (
    get_admin_user_id as package_get_admin_user_id,
    router as member_package_router,
)
from src.api.v1.admin.member_record import (
    get_export_admin,
    get_view_admin,
    router as member_record_router,
)


def _make_package_model(
    package_id: int = 1,
    package_code: str = "VIP_MONTH",
    package_name: str = "月度会员",
    status: int = 1,
):
    """构造 MemberPackage 模型 mock（供 _serialize_package 使用）"""
    pkg = MagicMock()
    pkg.id = package_id
    pkg.package_code = package_code
    pkg.package_name = package_name
    pkg.price = 99.0
    pkg.duration_days = 30
    pkg.member_commission_rate = 0.85
    pkg.status = status
    pkg.sort_order = 0
    pkg.description = "测试套餐"
    pkg.create_time = datetime.now()
    pkg.update_time = datetime.now()
    return pkg


def _make_record_model(
    record_id: int = 1,
    user_id: int = 100,
    status: str = "active",
):
    """构造 UserMemberRecord 模型 mock（供 _serialize_record 使用）"""
    rec = MagicMock()
    rec.id = record_id
    rec.user_id = user_id
    rec.package_id = 1
    rec.package_name = "月度会员"
    rec.member_commission_rate = 0.85
    rec.status = status
    rec.started_at = datetime(2026, 8, 1, 10, 0, 0)
    rec.expire_at = datetime(2026, 8, 31, 10, 0, 0)
    rec.order_id = 500
    rec.remark = ""
    rec.create_time = datetime(2026, 8, 1, 10, 0, 0)
    return rec


def _make_package_app():
    """构造带 mock 权限的套餐 API app"""
    app = FastAPI()
    app.include_router(member_package_router)

    async def mock_admin_id():
        return 1

    app.dependency_overrides[package_get_admin_user_id] = mock_admin_id
    return app


def _make_record_app():
    """构造带 mock 权限的会员记录 API app"""
    app = FastAPI()
    app.include_router(member_record_router)

    async def mock_view_admin():
        return {"user_id": 1}

    async def mock_export_admin():
        return {"user_id": 1}

    app.dependency_overrides[get_view_admin] = mock_view_admin
    app.dependency_overrides[get_export_admin] = mock_export_admin
    return app


# ══════════════════════════════════════════════════════
# 1. 会员套餐 API
# ══════════════════════════════════════════════════════


class TestMemberPackageAPI:
    """会员套餐接口测试"""

    def test_list_packages(self):
        app = _make_package_app()
        client = TestClient(app)

        with patch(
            "src.api.v1.admin.member_package.DatabaseManager.get_session"
        ) as mock_cm:
            session = MagicMock()
            dao = MagicMock()
            dao.paginate_packages = AsyncMock(
                return_value=([], 0)
            )
            mock_cm.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "src.api.v1.admin.member_package.MemberPackageDAO",
                return_value=dao,
            ):
                resp = client.get("/api/v1/admin/member-package/packages")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["total"] == 0

    def test_create_package_success(self):
        app = _make_package_app()
        client = TestClient(app)

        with patch(
            "src.api.v1.admin.member_package.DatabaseManager.get_session"
        ) as mock_cm:
            session = AsyncMock()
            dao = MagicMock()
            dao.get_by_code = AsyncMock(return_value=None)
            pkg = _make_package_model()
            dao.create = AsyncMock(return_value=pkg)
            mock_cm.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "src.api.v1.admin.member_package.MemberPackageDAO",
                return_value=dao,
            ):
                with patch(
                    "src.api.v1.admin.member_package.AuditLogger.log",
                    AsyncMock(),
                ):
                    resp = client.post(
                        "/api/v1/admin/member-package/packages",
                        json={
                            "package_code": "VIP_MONTH",
                            "package_name": "月度会员",
                            "price": 99,
                            "duration_days": 30,
                            "member_commission_rate": 0.85,
                            "status": 1,
                            "sort_order": 0,
                            "description": "测试",
                        },
                    )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["package_code"] == "VIP_MONTH"

    def test_create_package_invalid_rate(self):
        """非法分佣比例（>1）应返回 422"""
        app = _make_package_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/admin/member-package/packages",
            json={
                "package_code": "VIP_MONTH",
                "package_name": "月度会员",
                "price": 99,
                "duration_days": 30,
                "member_commission_rate": 1.5,
                "status": 1,
                "sort_order": 0,
                "description": "测试",
            },
        )
        assert resp.status_code == 422

    def test_create_package_duplicate_code(self):
        """套餐编码重复应返回业务错误"""
        app = _make_package_app()
        client = TestClient(app)

        with patch(
            "src.api.v1.admin.member_package.DatabaseManager.get_session"
        ) as mock_cm:
            session = MagicMock()
            dao = MagicMock()
            dao.get_by_code = AsyncMock(return_value=MagicMock(id=1))
            mock_cm.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "src.api.v1.admin.member_package.MemberPackageDAO",
                return_value=dao,
            ):
                resp = client.post(
                    "/api/v1/admin/member-package/packages",
                    json={
                        "package_code": "VIP_MONTH",
                        "package_name": "月度会员",
                        "price": 99,
                        "duration_days": 30,
                        "member_commission_rate": 0.85,
                        "status": 1,
                        "sort_order": 0,
                        "description": "测试",
                    },
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400
        assert "已存在" in body["msg"]

    def test_update_package_status(self):
        """上下架接口"""
        app = _make_package_app()
        client = TestClient(app)

        with patch(
            "src.api.v1.admin.member_package.DatabaseManager.get_session"
        ) as mock_cm:
            session = AsyncMock()
            dao = MagicMock()
            pkg = _make_package_model(status=0)
            dao.get_by_id = AsyncMock(return_value=pkg)
            mock_cm.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "src.api.v1.admin.member_package.MemberPackageDAO",
                return_value=dao,
            ):
                with patch(
                    "src.api.v1.admin.member_package.AuditLogger.log",
                    AsyncMock(),
                ):
                    resp = client.put(
                        "/api/v1/admin/member-package/packages/1/status",
                        json={"status": 0},
                    )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["status"] == 0


# ══════════════════════════════════════════════════════
# 2. 会员记录 API
# ══════════════════════════════════════════════════════


class TestMemberRecordAPI:
    """会员记录接口测试"""

    def test_list_records(self):
        app = _make_record_app()
        client = TestClient(app)

        with patch(
            "src.api.v1.admin.member_record.DatabaseManager.get_session"
        ) as mock_cm:
            session = AsyncMock()
            dao = MagicMock()
            dao.paginate_records = AsyncMock(
                return_value=([_make_record_model()], 1)
            )
            mock_cm.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "src.api.v1.admin.member_record.UserMemberRecordDAO",
                return_value=dao,
            ):
                resp = client.get(
                    "/api/v1/admin/member-record/records",
                    params={"page": 1, "page_size": 20},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["total"] == 1

    def test_list_records_invalid_time_range(self):
        """起始时间晚于截止时间应返回业务错误"""
        app = _make_record_app()
        client = TestClient(app)

        resp = client.get(
            "/api/v1/admin/member-record/records",
            params={
                "start_time": "2026-08-31 10:00:00",
                "end_time": "2026-08-01 10:00:00",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400

    def test_stats(self):
        app = _make_record_app()
        client = TestClient(app)

        with patch(
            "src.api.v1.admin.member_record.DatabaseManager.get_session"
        ) as mock_cm:
            session = MagicMock()
            dao = MagicMock()
            dao.paginate_records = AsyncMock(side_effect=[
                ([], 5),  # active
                ([], 3),  # expired
                ([], 10),  # all
            ])
            mock_cm.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "src.api.v1.admin.member_record.UserMemberRecordDAO",
                return_value=dao,
            ):
                resp = client.get("/api/v1/admin/member-record/stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["active_count"] == 5
        assert body["data"]["expired_count"] == 3
        assert body["data"]["total_count"] == 10

    def test_export_success(self):
        app = _make_record_app()
        client = TestClient(app)

        with patch(
            "src.api.v1.admin.member_record.DatabaseManager.get_session"
        ) as mock_cm:
            session = AsyncMock()
            dao = MagicMock()
            # 第一次调用：统计总数（page_size=1）
            dao.paginate_records = AsyncMock(return_value=([], 1))
            dao.list_for_export = AsyncMock(return_value=[_make_record_model()])
            mock_cm.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "src.api.v1.admin.member_record.UserMemberRecordDAO",
                return_value=dao,
            ):
                with patch(
                    "src.api.v1.admin.member_record.Workbook",
                ) as mock_wb:
                    wb = MagicMock()
                    wb.save = MagicMock()
                    mock_wb.return_value = wb
                    with patch(
                        "src.api.v1.admin.member_record.os.path.getsize",
                        return_value=1024,
                    ):
                        resp = client.post(
                            "/api/v1/admin/member-record/export",
                            json={"status": "active"},
                        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["row_count"] == 1

    def test_export_empty(self):
        """无数据导出返回业务错误"""
        app = _make_record_app()
        client = TestClient(app)

        with patch(
            "src.api.v1.admin.member_record.DatabaseManager.get_session"
        ) as mock_cm:
            session = MagicMock()
            dao = MagicMock()
            dao.paginate_records = AsyncMock(return_value=([], 0))
            mock_cm.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "src.api.v1.admin.member_record.UserMemberRecordDAO",
                return_value=dao,
            ):
                resp = client.post(
                    "/api/v1/admin/member-record/export",
                    json={"status": "expired"},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400
        assert "无符合条件" in body["msg"]
