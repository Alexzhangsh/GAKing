# @ai-generated
"""
X01-1 MiniappUserService mock 用户逻辑单元测试（纯函数，无 DB/Redis 依赖）

覆盖范围：
1. _dev_mock_openid
   - 同一 code → 稳定同一 openid（确定性）
   - 不同 code → 不同 openid
   - 生成结果带 dev_ 前缀（与 mock_user_util.MOCK_OPENID_PREFIX 对齐）
2. is_mock_openid 类方法
   - dev_ 前缀 → True
   - 真实 openid → False
   - 空字符串 → False
3. login_by_code 开发兜底分支（mock openid 生成路径）
   - WX_MINI_APPID 为空 → 走 _dev_mock_openid
   - 新用户创建 / 老用户登录
"""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.common.mock_user_util import MOCK_OPENID_PREFIX
from src.services.miniapp_user_service import MiniappUserService


# ══════════════════════════════════════════════════════
# _dev_mock_openid
# ══════════════════════════════════════════════════════


class TestDevMockOpenid:
    def test_stable_for_same_code(self):
        openid1 = MiniappUserService._dev_mock_openid("code_abc_123")
        openid2 = MiniappUserService._dev_mock_openid("code_abc_123")
        assert openid1 == openid2

    def test_different_codes_different_openid(self):
        openid1 = MiniappUserService._dev_mock_openid("code_abc")
        openid2 = MiniappUserService._dev_mock_openid("code_def")
        assert openid1 != openid2

    def test_dev_prefix(self):
        openid = MiniappUserService._dev_mock_openid("any_code")
        assert openid.startswith(MOCK_OPENID_PREFIX)
        assert openid.startswith("dev_")

    def test_length(self):
        openid = MiniappUserService._dev_mock_openid("any_code")
        # dev_ + 32 位 md5 hex
        assert len(openid) == 4 + 32


# ══════════════════════════════════════════════════════
# is_mock_openid 类方法
# ══════════════════════════════════════════════════════


class TestIsMockOpenidClassmethod:
    def test_mock_openid_true(self):
        assert MiniappUserService.is_mock_openid("dev_abc123") is True

    def test_real_openid_false(self):
        assert MiniappUserService.is_mock_openid("oX8Kj5tQ2mWvYzAbCdEfGhIjKlMnOpQr") is False

    def test_empty_false(self):
        assert MiniappUserService.is_mock_openid("") is False


# ══════════════════════════════════════════════════════
# login_by_code 开发兜底分支
# ══════════════════════════════════════════════════════


class TestLoginByCodeDevMode:
    @pytest.mark.asyncio
    async def test_dev_mode_new_user_creates_mock_openid(self):
        """开发模式（WX_MINI_APPID 为空）→ 生成 mock openid 并创建新用户"""
        mock_user = MagicMock()
        mock_user.user_id = 1
        mock_user.nickname = "微信用户"
        mock_user.avatar = ""
        mock_user.status = 0

        with patch.object(
            MiniappUserService, "_code2session_via_wx", new=AsyncMock()
        ) as mock_wx, patch.object(
            MiniappUserService, "_get_user_by_openid", new=AsyncMock(return_value=None)
        ), patch.object(
            MiniappUserService, "_create_user", new=AsyncMock(return_value=mock_user)
        ) as mock_create, patch.object(
            MiniappUserService, "_update_session_key", new=AsyncMock()
        ), patch(
            "src.services.miniapp_user_service.EnvConfig.WX_MINI_APPID", ""
        ):
            user, is_new = await MiniappUserService.login_by_code("dev_code_001")

        # 开发模式不调用微信官方接口
        mock_wx.assert_not_called()
        assert is_new is True
        assert user.user_id == 1
        # 创建用户时使用 mock openid
        call_openid = mock_create.call_args.kwargs["openid"]
        assert call_openid.startswith("dev_")

    @pytest.mark.asyncio
    async def test_dev_mode_existing_user_refreshes_session(self):
        """开发模式老用户登录 → 刷新 session_key，不重复创建"""
        mock_user = MagicMock()
        mock_user.user_id = 5
        mock_user.nickname = "老用户"
        mock_user.avatar = ""
        mock_user.status = 0

        with patch.object(
            MiniappUserService, "_code2session_via_wx", new=AsyncMock()
        ) as mock_wx, patch.object(
            MiniappUserService,
            "_get_user_by_openid",
            new=AsyncMock(return_value=mock_user),
        ), patch.object(
            MiniappUserService, "_create_user", new=AsyncMock()
        ) as mock_create, patch.object(
            MiniappUserService, "_update_session_key", new=AsyncMock()
        ) as mock_update, patch(
            "src.services.miniapp_user_service.EnvConfig.WX_MINI_APPID", ""
        ):
            user, is_new = await MiniappUserService.login_by_code("dev_code_002")

        mock_wx.assert_not_called()
        mock_create.assert_not_called()
        mock_update.assert_awaited_once()
        assert is_new is False
        assert user.user_id == 5

    @pytest.mark.asyncio
    async def test_prod_mode_calls_wx_code2session(self):
        """生产模式（WX_MINI_APPID 已配置）→ 调用微信官方 code2session"""
        mock_user = MagicMock()
        mock_user.user_id = 9
        mock_user.nickname = "真实用户"
        mock_user.avatar = ""
        mock_user.status = 0

        with patch.object(
            MiniappUserService,
            "_code2session_via_wx",
            new=AsyncMock(
                return_value={
                    "openid": "oXREAL1234567890",
                    "session_key": "sk_real",
                    "unionid": "u_real",
                }
            ),
        ) as mock_wx, patch.object(
            MiniappUserService,
            "_get_user_by_openid",
            new=AsyncMock(return_value=mock_user),
        ), patch.object(
            MiniappUserService, "_create_user", new=AsyncMock()
        ), patch.object(
            MiniappUserService, "_update_session_key", new=AsyncMock()
        ), patch(
            "src.services.miniapp_user_service.EnvConfig.WX_MINI_APPID", "wx_appid_1"
        ):
            user, is_new = await MiniappUserService.login_by_code("real_code")

        mock_wx.assert_awaited_once()
        assert is_new is False
        assert user.user_id == 9
