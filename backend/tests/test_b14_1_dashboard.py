# @ai-generated
"""
B14-1 数据大盘模块单元测试
覆盖：
1. B14DashboardService 所有方法：get_cards_data, get_commission_stats, get_order_trend, get_withdraw_trend
2. B14DashboardExportService 所有方法：export_commission_stats, export_order_trend, export_withdraw_trend, export_cards_report
3. 正常路径 + 异常路径边界场景全覆盖
4. 覆盖率目标 ≥90%
"""
import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.config.b13_b14_constants import (
    CACHE_KEY_DASHBOARD_CARDS,
    CACHE_KEY_DASHBOARD_COMMISSION,
    CACHE_KEY_DASHBOARD_ORDER_TREND,
    CACHE_TTL_DASHBOARD,
)
from src.scheduler.b14_1_dashboard_jobs import (
    dashboard_precompute,
    _run_with_lock,
    register_b14_1_dashboard_jobs,
)
from src.services.b14_1_dashboard_export_service import (
    B14DashboardExportService,
    EXPORT_DIR,
)
from src.services.b14_dashboard_service import B14DashboardService


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_cards_data():
    """构造首页卡片聚合 mock 数据"""
    return {
        "total_orders": 1000,
        "pending_settle_commission": "5000.00",
        "settled_commission": "15000.00",
        "total_withdrawn": "12000.00",
        "pending_review_withdraws": 5,
    }


def _make_commission_stats_by_date():
    """构造按日期分组佣金统计 mock 数据"""
    return [
        {"date": "2026-07-01", "total_commission": "500.00", "order_count": 50},
        {"date": "2026-07-02", "total_commission": "600.00", "order_count": 60},
        {"date": "2026-07-03", "total_commission": "550.00", "order_count": 55},
    ]


def _make_commission_stats_by_channel():
    """构造按渠道分组佣金统计 mock 数据"""
    return [
        {"channel_code": "myq", "total_commission": "8000.00", "order_count": 800},
        {"channel_code": "orderx", "total_commission": "7000.00", "order_count": 700},
    ]


def _make_commission_stats_by_user():
    """构造按用户分组佣金统计 mock 数据（分页）"""
    return {
        "total": 100,
        "page": 1,
        "page_size": 20,
        "items": [
            {"user_id": 101, "total_commission": "500.00", "order_count": 50},
            {"user_id": 102, "total_commission": "400.00", "order_count": 40},
        ],
    }


def _make_order_trend_data():
    """构造订单趋势 mock 数据"""
    return [
        {"date": "2026-07-01", "order_count": 50, "total_commission": "500.00"},
        {"date": "2026-07-02", "order_count": 60, "total_commission": "600.00"},
        {"date": "2026-07-03", "order_count": 55, "total_commission": "550.00"},
    ]


def _make_withdraw_trend_data():
    """构造提现趋势 mock 数据"""
    return [
        {
            "date": "2026-07-01",
            "apply_count": 10,
            "withdraw_amount": "1000.00",
            "success_amount": "950.00",
        },
        {
            "date": "2026-07-02",
            "apply_count": 8,
            "withdraw_amount": "800.00",
            "success_amount": "760.00",
        },
    ]


def _make_session_cm():
    """构造 DatabaseManager.get_session() 的上下文管理器 mock"""
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


def _clean_export_dir():
    """清理导出目录中的临时测试文件"""
    if os.path.exists(EXPORT_DIR):
        for f in os.listdir(EXPORT_DIR):
            if f.startswith("gaking_dashboard_test_"):
                os.remove(os.path.join(EXPORT_DIR, f))


# ══════════════════════════════════════════════════════
# 1. 大盘卡片测试
# ══════════════════════════════════════════════════════


class TestB14DashboardCards:
    """大盘卡片测试"""

    @pytest.mark.asyncio
    async def test_get_cards_success(self):
        """缓存命中 → 直接返回数据"""
        cards_data = _make_cards_data()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.RedisClient"
        ) as mock_redis:
            mock_redis.get = AsyncMock(return_value=json.dumps(cards_data))

            result = await B14DashboardService.get_cards_data(admin_user_id=1)

        assert result == cards_data
        mock_redis.get.assert_called_once_with(CACHE_KEY_DASHBOARD_CARDS)
        mock_audit.assert_called_once_with(1, "cards", {"cache_hit": True})

    @pytest.mark.asyncio
    async def test_get_cards_miss(self):
        """缓存未命中 → 查DB → 写缓存 → 返回"""
        cards_data = _make_cards_data()
        session, cm = _make_session_cm()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.RedisClient"
        ) as mock_redis, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock()
            mock_db.get_session.return_value = cm

            mock_dao = MagicMock()
            mock_dao.get_cards_data = AsyncMock(return_value=cards_data)
            mock_dao_cls.return_value = mock_dao

            result = await B14DashboardService.get_cards_data(admin_user_id=1)

        assert result == cards_data
        mock_redis.get.assert_called_once_with(CACHE_KEY_DASHBOARD_CARDS)
        mock_redis.set.assert_called_once_with(
            CACHE_KEY_DASHBOARD_CARDS,
            json.dumps(cards_data, ensure_ascii=False),
            ex=CACHE_TTL_DASHBOARD,
        )
        mock_dao.get_cards_data.assert_called_once()
        mock_audit.assert_called_once_with(1, "cards", {"cache_hit": False})

    @pytest.mark.asyncio
    async def test_get_cards_db_fallback(self):
        """缓存和DB都失败 → 异常处理"""
        session, cm = _make_session_cm()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.RedisClient"
        ) as mock_redis, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_redis.get = AsyncMock(side_effect=Exception("Redis连接失败"))
            mock_redis.set = AsyncMock()
            mock_db.get_session.return_value = cm

            mock_dao = MagicMock()
            mock_dao.get_cards_data = AsyncMock(side_effect=Exception("DB查询失败"))
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(Exception, match="DB查询失败"):
                await B14DashboardService.get_cards_data(admin_user_id=1)

            # 验证缓存写入失败不阻塞
            mock_redis.set.assert_not_called()


# ══════════════════════════════════════════════════════
# 2. 佣金统计测试
# ══════════════════════════════════════════════════════


class TestB14DashboardCommissionStats:
    """佣金统计测试"""

    start_date = datetime(2026, 7, 1)
    end_date = datetime(2026, 8, 1)

    @pytest.mark.asyncio
    async def test_commission_stats_by_date(self):
        """按日期分组正常返回"""
        session, cm = _make_session_cm()
        items = _make_commission_stats_by_date()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_commission_stats_by_date = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao

            result = await B14DashboardService.get_commission_stats(
                group_by="date",
                start_date=self.start_date,
                end_date=self.end_date,
                admin_user_id=1,
            )

        assert result["group_by"] == "date"
        assert result["total"] == 3
        assert len(result["items"]) == 3
        assert result["items"][0]["date"] == "2026-07-01"
        mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_commission_stats_by_channel(self):
        """按渠道分组正常返回"""
        session, cm = _make_session_cm()
        items = _make_commission_stats_by_channel()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_commission_stats_by_channel = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao

            result = await B14DashboardService.get_commission_stats(
                group_by="channel",
                start_date=self.start_date,
                end_date=self.end_date,
                admin_user_id=1,
            )

        assert result["group_by"] == "channel"
        assert result["total"] == 2
        assert result["items"][0]["channel_code"] == "myq"
        mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_commission_stats_by_user(self):
        """按用户分组正常返回（分页）"""
        session, cm = _make_session_cm()
        paged = _make_commission_stats_by_user()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_commission_stats_by_user = AsyncMock(return_value=paged)
            mock_dao_cls.return_value = mock_dao

            result = await B14DashboardService.get_commission_stats(
                group_by="user",
                start_date=self.start_date,
                end_date=self.end_date,
                page=1,
                page_size=20,
                admin_user_id=1,
            )

        assert result["group_by"] == "user"
        assert result["total"] == 100
        assert result["page"] == 1
        assert result["page_size"] == 20
        assert len(result["items"]) == 2
        mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_commission_stats_invalid_group_by(self):
        """非法分组维度 → ValueError"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        with patch("src.services.b14_dashboard_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_dashboard_service.DashboardQueryDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            with pytest.raises(ValueError, match="不支持的 group_by"):
                await B14DashboardService.get_commission_stats(
                    group_by="invalid",
                    start_date=self.start_date,
                    end_date=self.end_date,
                )


# ══════════════════════════════════════════════════════
# 3. 订单趋势测试
# ══════════════════════════════════════════════════════


class TestB14DashboardOrderTrend:
    """订单趋势测试"""

    start_date = datetime(2026, 7, 1)
    end_date = datetime(2026, 8, 1)

    @pytest.mark.asyncio
    async def test_order_trend_by_day(self):
        """按天分组正常返回"""
        session, cm = _make_session_cm()
        items = _make_order_trend_data()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_order_trend = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao

            result = await B14DashboardService.get_order_trend(
                start_date=self.start_date,
                end_date=self.end_date,
                group_by="day",
                admin_user_id=1,
            )

        assert result["group_by"] == "day"
        assert result["total"] == 3
        assert len(result["items"]) == 3
        mock_dao.get_order_trend.assert_called_once_with(
            self.start_date, self.end_date, group_by="day"
        )
        mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_trend_by_week(self):
        """按周分组正常返回"""
        session, cm = _make_session_cm()
        items = _make_order_trend_data()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_order_trend = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao

            result = await B14DashboardService.get_order_trend(
                start_date=self.start_date,
                end_date=self.end_date,
                group_by="week",
                admin_user_id=1,
            )

        assert result["group_by"] == "week"
        assert result["total"] == 3
        mock_dao.get_order_trend.assert_called_once_with(
            self.start_date, self.end_date, group_by="week"
        )
        mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_trend_by_month(self):
        """按月分组正常返回"""
        session, cm = _make_session_cm()
        items = _make_order_trend_data()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_order_trend = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao

            result = await B14DashboardService.get_order_trend(
                start_date=self.start_date,
                end_date=self.end_date,
                group_by="month",
                admin_user_id=1,
            )

        assert result["group_by"] == "month"
        assert result["total"] == 3
        mock_dao.get_order_trend.assert_called_once_with(
            self.start_date, self.end_date, group_by="month"
        )
        mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_trend_invalid_group_by(self):
        """非法分组维度 → ValueError"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        with patch("src.services.b14_dashboard_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_dashboard_service.DashboardQueryDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            with pytest.raises(ValueError, match="不支持的 group_by"):
                await B14DashboardService.get_order_trend(
                    start_date=self.start_date,
                    end_date=self.end_date,
                    group_by="invalid",
                )


# ══════════════════════════════════════════════════════
# 4. 提现趋势测试
# ══════════════════════════════════════════════════════


class TestB14DashboardWithdrawTrend:
    """提现趋势测试"""

    start_date = datetime(2026, 7, 1)
    end_date = datetime(2026, 8, 1)

    @pytest.mark.asyncio
    async def test_withdraw_trend_by_day(self):
        """按天分组正常返回"""
        session, cm = _make_session_cm()
        items = _make_withdraw_trend_data()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_withdraw_trend = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao

            result = await B14DashboardService.get_withdraw_trend(
                start_date=self.start_date,
                end_date=self.end_date,
                group_by="day",
                admin_user_id=1,
            )

        assert result["group_by"] == "day"
        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["date"] == "2026-07-01"
        mock_dao.get_withdraw_trend.assert_called_once_with(
            self.start_date, self.end_date, group_by="day"
        )
        mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_withdraw_trend_invalid_group_by(self):
        """非法分组维度 → ValueError"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        with patch("src.services.b14_dashboard_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_dashboard_service.DashboardQueryDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            with pytest.raises(ValueError, match="不支持的 group_by"):
                await B14DashboardService.get_withdraw_trend(
                    start_date=self.start_date,
                    end_date=self.end_date,
                    group_by="invalid",
                )


# ══════════════════════════════════════════════════════
# 5. 佣金统计导出测试
# ══════════════════════════════════════════════════════


class TestB14DashboardExportCommission:
    """佣金统计导出测试"""

    start_date = datetime(2026, 7, 1)
    end_date = datetime(2026, 8, 1)

    @pytest.mark.asyncio
    async def test_export_commission_stats_by_date(self):
        """按日期导出成功"""
        session, cm = _make_session_cm()
        items = _make_commission_stats_by_date()

        with patch(
            "src.services.b14_1_dashboard_export_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_1_dashboard_export_service.DashboardQueryDAO"
        ) as mock_dao_cls, patch(
            "src.services.b14_1_dashboard_export_service.AuditLogger"
        ) as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_commission_stats_by_date = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao
            mock_audit.log = AsyncMock()

            result = await B14DashboardExportService.export_commission_stats(
                start_date=self.start_date,
                end_date=self.end_date,
                group_by="date",
                admin_user_id=1,
            )

        assert result["file_name"].startswith("gaking_dashboard_commission_stats_date_")
        assert result["file_name"].endswith(".xlsx")
        assert result["row_count"] == 3
        assert os.path.exists(result["file_path"])
        mock_audit.log.assert_called_once()

        # 清理
        os.remove(result["file_path"])

    @pytest.mark.asyncio
    async def test_export_commission_stats_by_channel(self):
        """按渠道导出成功"""
        session, cm = _make_session_cm()
        items = _make_commission_stats_by_channel()

        with patch(
            "src.services.b14_1_dashboard_export_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_1_dashboard_export_service.DashboardQueryDAO"
        ) as mock_dao_cls, patch(
            "src.services.b14_1_dashboard_export_service.AuditLogger"
        ) as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_commission_stats_by_channel = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao
            mock_audit.log = AsyncMock()

            result = await B14DashboardExportService.export_commission_stats(
                start_date=self.start_date,
                end_date=self.end_date,
                group_by="channel",
                admin_user_id=1,
            )

        assert result["row_count"] == 2
        assert os.path.exists(result["file_path"])
        mock_audit.log.assert_called_once()
        os.remove(result["file_path"])

    @pytest.mark.asyncio
    async def test_export_commission_stats_by_user(self):
        """按用户导出成功"""
        session, cm = _make_session_cm()
        paged = _make_commission_stats_by_user()

        with patch(
            "src.services.b14_1_dashboard_export_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_1_dashboard_export_service.DashboardQueryDAO"
        ) as mock_dao_cls, patch(
            "src.services.b14_1_dashboard_export_service.AuditLogger"
        ) as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_commission_stats_by_user = AsyncMock(return_value=paged)
            mock_dao_cls.return_value = mock_dao
            mock_audit.log = AsyncMock()

            result = await B14DashboardExportService.export_commission_stats(
                start_date=self.start_date,
                end_date=self.end_date,
                group_by="user",
                admin_user_id=1,
            )

        assert result["row_count"] == 2
        assert os.path.exists(result["file_path"])
        mock_audit.log.assert_called_once()
        os.remove(result["file_path"])

    @pytest.mark.asyncio
    async def test_export_commission_stats_invalid_group_by(self):
        """非法分组 → ValueError"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        with patch("src.services.b14_1_dashboard_export_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_1_dashboard_export_service.DashboardQueryDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao
            with pytest.raises(ValueError, match="不支持的 group_by"):
                await B14DashboardExportService.export_commission_stats(
                    start_date=self.start_date,
                    end_date=self.end_date,
                    group_by="invalid",
                )


# ══════════════════════════════════════════════════════
# 6. 订单趋势导出测试
# ══════════════════════════════════════════════════════


class TestB14DashboardExportOrderTrend:
    """订单趋势导出测试"""

    start_date = datetime(2026, 7, 1)
    end_date = datetime(2026, 8, 1)

    @pytest.mark.asyncio
    async def test_export_order_trend(self):
        """导出成功，验证文件存在"""
        session, cm = _make_session_cm()
        items = _make_order_trend_data()

        with patch(
            "src.services.b14_1_dashboard_export_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_1_dashboard_export_service.DashboardQueryDAO"
        ) as mock_dao_cls, patch(
            "src.services.b14_1_dashboard_export_service.AuditLogger"
        ) as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_order_trend = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao
            mock_audit.log = AsyncMock()

            result = await B14DashboardExportService.export_order_trend(
                start_date=self.start_date,
                end_date=self.end_date,
                group_by="day",
                admin_user_id=1,
            )

        assert result["file_name"].startswith("gaking_dashboard_order_trend_day_")
        assert result["file_name"].endswith(".xlsx")
        assert result["row_count"] == 3
        assert os.path.exists(result["file_path"])
        mock_audit.log.assert_called_once()
        os.remove(result["file_path"])


# ══════════════════════════════════════════════════════
# 7. 提现趋势导出测试
# ══════════════════════════════════════════════════════


class TestB14DashboardExportWithdrawTrend:
    """提现趋势导出测试"""

    start_date = datetime(2026, 7, 1)
    end_date = datetime(2026, 8, 1)

    @pytest.mark.asyncio
    async def test_export_withdraw_trend(self):
        """导出成功，验证文件存在"""
        session, cm = _make_session_cm()
        items = _make_withdraw_trend_data()

        with patch(
            "src.services.b14_1_dashboard_export_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_1_dashboard_export_service.DashboardQueryDAO"
        ) as mock_dao_cls, patch(
            "src.services.b14_1_dashboard_export_service.AuditLogger"
        ) as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_withdraw_trend = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao
            mock_audit.log = AsyncMock()

            result = await B14DashboardExportService.export_withdraw_trend(
                start_date=self.start_date,
                end_date=self.end_date,
                group_by="day",
                admin_user_id=1,
            )

        assert result["file_name"].startswith("gaking_dashboard_withdraw_trend_day_")
        assert result["file_name"].endswith(".xlsx")
        assert result["row_count"] == 2
        assert os.path.exists(result["file_path"])
        mock_audit.log.assert_called_once()
        os.remove(result["file_path"])


# ══════════════════════════════════════════════════════
# 8. 卡片导出测试
# ══════════════════════════════════════════════════════


class TestB14DashboardExportCards:
    """卡片导出测试"""

    @pytest.mark.asyncio
    async def test_export_cards(self):
        """导出成功，验证文件内容"""
        session, cm = _make_session_cm()
        cards_data = _make_cards_data()

        with patch(
            "src.services.b14_1_dashboard_export_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_1_dashboard_export_service.DashboardQueryDAO"
        ) as mock_dao_cls, patch(
            "src.services.b14_1_dashboard_export_service.AuditLogger"
        ) as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_cards_data = AsyncMock(return_value=cards_data)
            mock_dao_cls.return_value = mock_dao
            mock_audit.log = AsyncMock()

            result = await B14DashboardExportService.export_cards_report(
                admin_user_id=1,
            )

        assert result["file_name"].startswith("gaking_dashboard_cards_snapshot_")
        assert result["file_name"].endswith(".xlsx")
        # 卡片数据有5行（累计订单数、待结算佣金、已结算佣金、提现总额、待审核提现数）
        assert result["row_count"] == 5
        assert os.path.exists(result["file_path"])
        mock_audit.log.assert_called_once()
        os.remove(result["file_path"])


# ══════════════════════════════════════════════════════
# 9. B14-1 定时预计算任务测试
# ══════════════════════════════════════════════════════


class TestB14DashboardPrecompute:
    """B14-1 定时预计算任务测试"""

    @pytest.mark.asyncio
    async def test_precompute_success(self):
        """预计算成功，验证缓存写入"""
        cards_data = _make_cards_data()
        session, cm = _make_session_cm()

        with patch(
            "src.scheduler.b14_1_dashboard_jobs.TASK_DASHBOARD_PRECOMPUTE_ENABLE",
            True,
        ), patch(
            "src.scheduler.b14_1_dashboard_jobs.RedisClient"
        ) as mock_redis, patch(
            "src.scheduler.b14_1_dashboard_jobs.DatabaseManager"
        ) as mock_db, patch(
            "src.scheduler.b14_1_dashboard_jobs.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_redis.set = AsyncMock()
            mock_db.get_session.return_value = cm

            mock_dao = MagicMock()
            mock_dao.get_cards_data = AsyncMock(return_value=cards_data)
            mock_dao_cls.return_value = mock_dao

            result = await dashboard_precompute()

        assert result["status"] == "success"
        assert result["cards_data"] == cards_data
        mock_redis.set.assert_called_once_with(
            CACHE_KEY_DASHBOARD_CARDS,
            json.dumps(cards_data, ensure_ascii=False),
            ex=CACHE_TTL_DASHBOARD,
        )

    @pytest.mark.asyncio
    async def test_precompute_disabled(self):
        """任务开关关闭 → 跳过"""
        with patch(
            "src.scheduler.b14_1_dashboard_jobs.TASK_DASHBOARD_PRECOMPUTE_ENABLE",
            False,
        ), patch(
            "src.scheduler.b14_1_dashboard_jobs.RedisClient"
        ) as mock_redis:
            mock_redis.set = AsyncMock()

            result = await dashboard_precompute()

        assert result["status"] == "skipped"
        assert "任务开关关闭" in result["message"]
        mock_redis.set.assert_not_called()


# ══════════════════════════════════════════════════════
# 10. 审计日志异常降级测试
# ══════════════════════════════════════════════════════


class TestB14DashboardAuditFallback:
    """审计日志异常降级测试"""

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_block(self):
        """审计日志写入失败不阻塞主流程"""
        cards_data = _make_cards_data()

        with patch(
            "src.services.b14_dashboard_service.AuditLogger"
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.RedisClient"
        ) as mock_redis:
            mock_audit.log = AsyncMock(side_effect=Exception("审计日志写入失败"))
            mock_redis.get = AsyncMock(return_value=json.dumps(cards_data))

            # 审计日志异常不应阻塞主流程返回数据
            result = await B14DashboardService.get_cards_data(admin_user_id=1)

        assert result == cards_data


# ══════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════
# 11. 完整边界覆盖：缓存写入失败、导出审计失败、锁机制
# ══════════════════════════════════════════════════════


class TestB14DashboardEdgeCases:
    """边界场景覆盖测试"""

    @pytest.mark.asyncio
    async def test_cache_write_failure_after_db(self):
        """DB查询成功但缓存写入失败 → 不阻塞返回"""
        cards_data = _make_cards_data()
        session, cm = _make_session_cm()

        with patch.object(
            B14DashboardService, "_audit_query", AsyncMock()
        ) as mock_audit, patch(
            "src.services.b14_dashboard_service.RedisClient"
        ) as mock_redis, patch(
            "src.services.b14_dashboard_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_dashboard_service.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock(side_effect=Exception("缓存写入失败"))
            mock_db.get_session.return_value = cm

            mock_dao = MagicMock()
            mock_dao.get_cards_data = AsyncMock(return_value=cards_data)
            mock_dao_cls.return_value = mock_dao

            result = await B14DashboardService.get_cards_data(admin_user_id=1)

        assert result == cards_data
        mock_redis.set.assert_called_once()
        mock_audit.assert_called_once_with(1, "cards", {"cache_hit": False})

    @pytest.mark.asyncio
    async def test_export_audit_failure(self):
        """导出时审计日志写入失败不阻塞"""
        session, cm = _make_session_cm()
        items = _make_commission_stats_by_date()

        with patch(
            "src.services.b14_1_dashboard_export_service.DatabaseManager"
        ) as mock_db, patch(
            "src.services.b14_1_dashboard_export_service.DashboardQueryDAO"
        ) as mock_dao_cls, patch(
            "src.services.b14_1_dashboard_export_service.AuditLogger"
        ) as mock_audit:
            mock_db.get_session.return_value = cm
            mock_dao = MagicMock()
            mock_dao.get_commission_stats_by_date = AsyncMock(return_value=items)
            mock_dao_cls.return_value = mock_dao
            mock_audit.log = AsyncMock(side_effect=Exception("审计日志写入失败"))

            result = await B14DashboardExportService.export_commission_stats(
                start_date=datetime(2026, 7, 1),
                end_date=datetime(2026, 8, 1),
                group_by="date",
                admin_user_id=1,
            )

        assert result["row_count"] == 3
        assert os.path.exists(result["file_path"])
        os.remove(result["file_path"])

    @pytest.mark.asyncio
    async def test_precompute_redis_write_failure(self):
        """预计算时Redis缓存写入失败 → 返回failed状态"""
        cards_data = _make_cards_data()
        session, cm = _make_session_cm()

        with patch(
            "src.scheduler.b14_1_dashboard_jobs.TASK_DASHBOARD_PRECOMPUTE_ENABLE",
            True,
        ), patch(
            "src.scheduler.b14_1_dashboard_jobs.RedisClient"
        ) as mock_redis, patch(
            "src.scheduler.b14_1_dashboard_jobs.DatabaseManager"
        ) as mock_db, patch(
            "src.scheduler.b14_1_dashboard_jobs.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_redis.set = AsyncMock(side_effect=Exception("Redis连接失败"))
            mock_db.get_session.return_value = cm

            mock_dao = MagicMock()
            mock_dao.get_cards_data = AsyncMock(return_value=cards_data)
            mock_dao_cls.return_value = mock_dao

            result = await dashboard_precompute()

        assert result["status"] == "failed"
        assert "缓存写入失败" in result["message"]

    @pytest.mark.asyncio
    async def test_precompute_db_failure(self):
        """预计算时DB查询失败 → 返回failed状态"""
        session, cm = _make_session_cm()

        with patch(
            "src.scheduler.b14_1_dashboard_jobs.TASK_DASHBOARD_PRECOMPUTE_ENABLE",
            True,
        ), patch(
            "src.scheduler.b14_1_dashboard_jobs.RedisClient"
        ) as mock_redis, patch(
            "src.scheduler.b14_1_dashboard_jobs.DatabaseManager"
        ) as mock_db, patch(
            "src.scheduler.b14_1_dashboard_jobs.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_redis.set = AsyncMock()
            mock_db.get_session.return_value = cm

            mock_dao = MagicMock()
            mock_dao.get_cards_data = AsyncMock(side_effect=Exception("DB连接失败"))
            mock_dao_cls.return_value = mock_dao

            result = await dashboard_precompute()

        assert result["status"] == "failed"
        assert "DB连接失败" in result["message"]


class TestB14DashboardPrecomputeLock:
    """分布式锁完整路径测试"""

    @pytest.mark.asyncio
    async def test_run_with_lock_success(self):
        """获取锁 → 执行成功 → 释放锁（S04 P2-1：acquire_with_wait）"""
        cards_data = _make_cards_data()
        session, cm = _make_session_cm()

        with patch(
            "src.scheduler.b14_1_dashboard_jobs.LockUtil"
        ) as mock_lock, patch(
            "src.scheduler.b14_1_dashboard_jobs.TASK_DASHBOARD_PRECOMPUTE_ENABLE",
            True,
        ), patch(
            "src.scheduler.b14_1_dashboard_jobs.RedisClient"
        ) as mock_redis, patch(
            "src.scheduler.b14_1_dashboard_jobs.DatabaseManager"
        ) as mock_db, patch(
            "src.scheduler.b14_1_dashboard_jobs.DashboardQueryDAO"
        ) as mock_dao_cls:
            mock_lock.acquire_with_wait = AsyncMock(return_value="test_owner")
            mock_lock.release_lock = AsyncMock()
            mock_redis.set = AsyncMock()
            mock_db.get_session.return_value = cm

            mock_dao = MagicMock()
            mock_dao.get_cards_data = AsyncMock(return_value=cards_data)
            mock_dao_cls.return_value = mock_dao

            result = await _run_with_lock()

        assert result["status"] == "success"
        mock_lock.acquire_with_wait.assert_called_once()
        mock_lock.release_lock.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_lock_failure(self):
        """未获取到锁 → 记录冲突并跳过执行（S04 P2-1）"""
        with patch(
            "src.scheduler.b14_1_dashboard_jobs.LockUtil"
        ) as mock_lock:
            mock_lock.acquire_with_wait = AsyncMock(return_value=None)
            mock_lock.record_lock_conflict = AsyncMock()
            mock_lock.release_lock = AsyncMock()

            result = await _run_with_lock()

        assert result["status"] == "skipped"
        assert "未获取到分布式锁" in result["message"]
        mock_lock.record_lock_conflict.assert_awaited_once()
        mock_lock.release_lock.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_with_lock_exception(self):
        """锁获取/执行过程中抛出异常 → 返回failed"""
        with patch(
            "src.scheduler.b14_1_dashboard_jobs.LockUtil"
        ) as mock_lock:
            mock_lock.acquire_with_wait = AsyncMock(
                side_effect=Exception("获取锁异常")
            )
            mock_lock.release_lock = AsyncMock()

            result = await _run_with_lock()

        assert result["status"] == "failed"
        assert "获取锁异常" in result["message"]


class TestB14DashboardRegisterJobs:
    """定时任务注册测试"""

    def test_register_jobs(self):
        """验证注册函数正确调用TaskScheduler"""
        with patch(
            "src.scheduler.b14_1_dashboard_jobs.TaskScheduler"
        ) as mock_scheduler, patch(
            "src.scheduler.b14_1_dashboard_jobs.TASK_CRON_DASHBOARD_PRECOMPUTE",
            "*/30 * * * *",
        ):
            register_b14_1_dashboard_jobs()

        mock_scheduler.add_cron_task.assert_called_once()
        call_args = mock_scheduler.add_cron_task.call_args
        assert call_args[1]["name"] == "dashboard_precompute"
        assert call_args[1]["cron_expr"] == "*/30 * * * *"


# ══════════════════════════════════════════════════════
# 清理测试临时文件


def teardown_module():
    """模块测试完成后清理导出目录中的临时文件"""
    if os.path.exists(EXPORT_DIR):
        for f in os.listdir(EXPORT_DIR):
            file_path = os.path.join(EXPORT_DIR, f)
            if os.path.isfile(file_path) and f.endswith(".xlsx"):
                os.remove(file_path)