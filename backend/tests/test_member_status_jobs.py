# @ai-generated
"""
X02-1 会员状态定时刷新任务单元测试
覆盖：member_status_refresh（开关跳过 / 成功标记到期 / 失败兜底）
使用 AsyncMock 模拟 DatabaseManager 与 DAO，不依赖真实 DB/Redis
"""
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.scheduler.member_status_jobs import member_status_refresh


def _make_run_log(log_id: int = 1):
    log = MagicMock()
    log.id = log_id
    return log


class TestMemberStatusRefresh:
    """会员状态刷新任务测试"""

    @pytest.mark.asyncio
    async def test_skipped_when_disabled(self):
        """任务开关关闭时跳过"""
        with patch(
            "src.scheduler.member_status_jobs.TASK_MEMBER_STATUS_REFRESH_ENABLE",
            False,
        ):
            result = await member_status_refresh()
        assert result["status"] == "skipped"
        assert result["expired_count"] == 0

    @pytest.mark.asyncio
    async def test_success_mark_expired(self):
        """正常执行：标记到期并记录运行日志"""
        run_log = _make_run_log()

        # mock DatabaseManager.get_session 上下文管理器
        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        session_cm.__aexit__ = AsyncMock(return_value=False)

        log_dao = MagicMock()
        log_dao.create_run_log = AsyncMock(return_value=run_log)
        log_dao.update_run_log = AsyncMock()

        record_dao = MagicMock()
        record_dao.mark_expired_before = AsyncMock(return_value=5)

        with patch(
            "src.scheduler.member_status_jobs.DatabaseManager.get_session",
            return_value=session_cm,
        ):
            with patch(
                "src.scheduler.member_status_jobs.ScheduledTaskRunLogDAO",
                return_value=log_dao,
            ):
                with patch(
                    "src.scheduler.member_status_jobs.UserMemberRecordDAO",
                    return_value=record_dao,
                ):
                    result = await member_status_refresh()

        assert result["status"] == "success"
        assert result["expired_count"] == 5
        log_dao.create_run_log.assert_awaited_once()
        log_dao.update_run_log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failure_records_failed_log(self):
        """执行异常时记录 failed 日志并返回失败"""
        run_log = _make_run_log()

        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        session_cm.__aexit__ = AsyncMock(return_value=False)

        log_dao = MagicMock()
        log_dao.create_run_log = AsyncMock(return_value=run_log)
        log_dao.update_run_log = AsyncMock()

        record_dao = MagicMock()
        record_dao.mark_expired_before = AsyncMock(
            side_effect=RuntimeError("db down")
        )

        with patch(
            "src.scheduler.member_status_jobs.DatabaseManager.get_session",
            return_value=session_cm,
        ):
            with patch(
                "src.scheduler.member_status_jobs.ScheduledTaskRunLogDAO",
                return_value=log_dao,
            ):
                with patch(
                    "src.scheduler.member_status_jobs.UserMemberRecordDAO",
                    return_value=record_dao,
                ):
                    result = await member_status_refresh()

        assert result["status"] == "failed"
        assert result["expired_count"] == 0
        assert "db down" in result["message"]
        # failed 日志记录（update_run_log 至少被调用一次）
        log_dao.update_run_log.assert_awaited()
