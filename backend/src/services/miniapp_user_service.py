# @ai-generated
"""
小程序C端用户登录服务（M03 新建）

职责：
1. 对接微信官方 code2session 接口，用 wx.login() 返回的 code 换取 openid + session_key
2. 按 openid 查找或创建 MiniappUser 记录（user_id 取主键 id，保证全局唯一）
3. 首次登录自动联动创建 UserCommissionAccount（与 B08 佣金账户域打通）
4. 开发兜底：WX_MINI_APPID 未配置时，按 code 生成稳定 mock openid，无需真实微信凭证

业务边界：
- 仅处理 C 端小程序用户登录鉴权，不涉及后台管理员 RBAC
- 不存储明文 session_key 到日志，不打印完整 token
- user_id 生成策略：使用 MiniappUser 主键自增 id 作为 user_id，保证与 orders / user_commission_account 联动
"""
import hashlib
import logging
from typing import Optional, Tuple

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from src.common.mock_user_util import MOCK_OPENID_PREFIX, is_mock_openid
from src.config.env_config import EnvConfig
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.db.init_db import DatabaseManager
from src.models.business.miniapp_user_model import MiniappUser

logger = logging.getLogger("services.miniapp_user")

# 微信 code2session 官方接口
WX_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
WX_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WX_GET_PHONE_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"
WX_REQUEST_TIMEOUT = 10.0  # 微信接口超时 10s

# 账号状态枚举
USER_STATUS_NORMAL = 0
USER_STATUS_BANNED = 1

# 微信 access_token 缓存（进程内，提前 300s 刷新）
_wx_access_token_cache: dict = {"token": "", "expires_at": 0.0}


class WxLoginError(Exception):
    """微信登录业务异常"""

    def __init__(self, message: str, errcode: int = 0) -> None:
        super().__init__(message)
        self.errcode = errcode
        self.message = message


class MiniappUserService:
    """小程序C端用户登录服务

    提供 wx.login code → openid → 用户注册/登录的完整链路
    """

    # ─────────────────────────────────────────────────────
    # 微信 code2session 对接
    # ─────────────────────────────────────────────────────

    @classmethod
    async def _code2session_via_wx(cls, code: str) -> dict:
        """调用微信官方 code2session 接口换取 openid + session_key

        Args:
            code: wx.login() 返回的临时登录凭证
        Returns:
            {"openid": str, "session_key": str, "unionid": str (可选)}
        Raises:
            WxLoginError: 微信接口调用失败或返回错误码
        """
        params = {
            "appid": EnvConfig.WX_MINI_APPID,
            "secret": EnvConfig.WX_MINI_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(WX_REQUEST_TIMEOUT)
            ) as client:
                response = await client.get(WX_CODE2SESSION_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as e:
            logger.error("[wx-login] code2session 请求超时: %s", e)
            raise WxLoginError("微信登录服务超时，请稍后重试") from e
        except httpx.HTTPError as e:
            logger.error("[wx-login] code2session 请求失败: %s", e)
            raise WxLoginError("微信登录服务异常，请稍后重试") from e
        except ValueError as e:
            logger.error("[wx-login] code2session 响应解析失败: %s", e)
            raise WxLoginError("微信登录响应解析失败") from e

        # 微信返回 errcode 非 0 表示业务错误
        errcode = data.get("errcode", 0)
        if errcode != 0:
            errmsg = data.get("errmsg", "unknown error")
            logger.warning(
                "[wx-login] code2session 业务失败 errcode=%s errmsg=%s",
                errcode,
                errmsg,
            )
            # 常见错误码：40029 invalid code、45011 频率限制、-1 系统繁忙
            if errcode == 40029:
                raise WxLoginError("微信登录凭证无效，请重新登录", errcode=errcode)
            if errcode == 45011:
                raise WxLoginError("登录请求过于频繁，请稍后重试", errcode=errcode)
            raise WxLoginError(f"微信登录失败: {errmsg}", errcode=errcode)

        openid = data.get("openid", "")
        session_key = data.get("session_key", "")
        unionid = data.get("unionid", "")

        if not openid:
            logger.error("[wx-login] code2session 返回 openid 为空: %s", data)
            raise WxLoginError("微信登录返回数据异常")

        return {
            "openid": openid,
            "session_key": session_key,
            "unionid": unionid,
        }

    @classmethod
    def _dev_mock_openid(cls, code: str) -> str:
        """开发兜底：按 code 生成稳定的 mock openid

        开发环境（WX_MINI_APPID 为空）使用，同一 code 始终映射到同一 openid，
        便于本地无真实微信凭证时测试完整登录链路。

        Args:
            code: wx.login() 返回的临时凭证
        Returns:
            32位 mock openid 字符串（dev_ 前缀，便于区分）
        """
        digest = hashlib.md5(code.encode("utf-8")).hexdigest()
        return f"{MOCK_OPENID_PREFIX}{digest}"

    @classmethod
    def is_mock_openid(cls, openid: str) -> bool:
        """判断 openid 是否为开发 mock openid（dev_ 前缀）

        复用 src.common.mock_user_util.is_mock_openid，
        供提现/打款等业务链路识别 mock 用户并做边界处理。
        """
        return is_mock_openid(openid)

    # ─────────────────────────────────────────────────────
    # 用户查找/创建核心逻辑
    # ─────────────────────────────────────────────────────

    @classmethod
    async def _get_user_by_openid(cls, openid: str) -> Optional[MiniappUser]:
        """按 openid 查询用户（自动过滤软删除）"""
        async with DatabaseManager.get_session() as session:
            stmt = select(MiniappUser).where(
                MiniappUser.openid == openid,
                MiniappUser.is_delete == False,  # noqa: E712
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @classmethod
    async def _create_user(
        cls,
        openid: str,
        unionid: str = "",
        nickname: str = "微信用户",
        avatar: str = "",
        session_key: str = "",
    ) -> MiniappUser:
        """创建新小程序用户

        user_id 生成策略：使用 MiniappUser 主键自增 id 作为 user_id
        - 先插入 user_id=0 占位
        - flush 后获取自增 id
        - 更新 user_id = id
        - 同事务内联动创建 UserCommissionAccount

        保证 user_id 全局唯一，且与 orders / user_commission_account 联动。
        """
        async with DatabaseManager.get_session() as session:
            # Step1: 插入占位记录
            user = MiniappUser(
                user_id=0,  # 占位，flush 后更新为主键 id
                openid=openid,
                unionid=unionid,
                nickname=nickname,
                avatar=avatar,
                session_key=session_key,
                status=USER_STATUS_NORMAL,
            )
            session.add(user)
            try:
                await session.flush()  # 获取自增主键 id
            except IntegrityError as e:
                await session.rollback()
                # openid 唯一索引冲突 → 并发登录场景，回退为查询已有用户
                logger.warning(
                    "[wx-login] 创建用户时 openid 冲突，回退查询 openid=%s: %s",
                    openid[:8] + "***",
                    e,
                )
                existing = await cls._get_user_by_openid(openid)
                if existing is not None:
                    return existing
                raise WxLoginError("用户创建失败（openid 冲突且查询无记录）") from e

            # Step2: 用主键 id 作为 user_id（保证全局唯一）
            user.user_id = user.id

            try:
                await session.flush()
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("[wx-login] 更新 user_id 失败 openid=%s: %s", openid[:8] + "***", e)
                raise WxLoginError("用户创建失败") from e

            await session.refresh(user)
            logger.info(
                "[wx-login] 新用户创建成功 user_id=%s openid=%s",
                user.user_id,
                openid[:8] + "***",
            )

            # Step3: 联动创建佣金账户（首次登录自动开通，与 B08 打通）
            try:
                async with DatabaseManager.get_session() as account_session:
                    account_dao = UserCommissionAccountDAO(account_session)
                    await account_dao.get_or_create_by_user_id(user.user_id)
            except Exception as e:
                # 佣金账户创建失败不阻断登录（下次登录会重试创建）
                logger.warning(
                    "[wx-login] 佣金账户联动创建失败 user_id=%s: %s",
                    user.user_id,
                    e,
                )

            return user

    @classmethod
    async def _update_session_key(
        cls, user_id: int, session_key: str, nickname: str = "", avatar: str = ""
    ) -> None:
        """更新用户 session_key（每次登录刷新，用于后续解密 encryptedData）

        Args:
            user_id: 平台用户ID
            session_key: 微信返回的新会话密钥
            nickname: 可选，用户授权后的新昵称
            avatar: 可选，用户授权后的新头像
        """
        async with DatabaseManager.get_session() as session:
            values: dict = {"session_key": session_key}
            if nickname:
                values["nickname"] = nickname
            if avatar:
                values["avatar"] = avatar

            stmt = (
                update(MiniappUser)
                .where(
                    MiniappUser.user_id == user_id,
                    MiniappUser.is_delete == False,  # noqa: E712
                )
                .values(**values)
            )
            await session.execute(stmt)
            await session.commit()

    # ─────────────────────────────────────────────────────
    # 登录主流程
    # ─────────────────────────────────────────────────────

    @classmethod
    async def login_by_code(
        cls,
        code: str,
        nickname: str = "微信用户",
        avatar: str = "",
    ) -> Tuple[MiniappUser, bool]:
        """微信登录主入口

        流程：
        1. WX_MINI_APPID 非空 → 调用微信 code2session 换取真实 openid
           WX_MINI_APPID 为空 → 开发兜底，按 code 生成稳定 mock openid
        2. 按 openid 查找用户
           - 存在且状态正常 → 刷新 session_key，返回用户
           - 存在但被禁用 → 抛 WxLoginError
           - 不存在 → 创建新用户（联动佣金账户）
        3. 返回 (user, is_new_user)

        Args:
            code: wx.login() 返回的临时登录凭证（5分钟有效）
            nickname: 用户昵称（可选，默认"微信用户"）
            avatar: 用户头像URL（可选）
        Returns:
            (MiniappUser 实例, 是否首次注册)
        Raises:
            WxLoginError: 微信接口失败 / 用户被禁用 / 创建失败
        """
        if not code:
            raise WxLoginError("登录凭证 code 不能为空")

        is_dev_mode = not EnvConfig.WX_MINI_APPID

        if is_dev_mode:
            # 开发兜底：无需真实微信凭证，按 code 生成稳定 mock openid
            openid = cls._dev_mock_openid(code)
            session_key = "dev_mock_session_key"
            unionid = ""
            logger.info(
                "[wx-login] 开发兜底模式 mock openid=%s (前8位)",
                openid[:12] + "***",
            )
        else:
            # 生产模式：调用微信官方 code2session
            wx_data = await cls._code2session_via_wx(code)
            openid = wx_data["openid"]
            session_key = wx_data["session_key"]
            unionid = wx_data["unionid"]

        # 按 openid 查找用户
        user = await cls._get_user_by_openid(openid)

        if user is not None:
            # 用户已存在
            if user.status == USER_STATUS_BANNED:
                logger.warning(
                    "[wx-login] 用户被禁用 user_id=%s openid=%s",
                    user.user_id,
                    openid[:8] + "***",
                )
                raise WxLoginError("账号已被禁用，请联系客服")

            # 刷新 session_key + 可选昵称/头像
            await cls._update_session_key(
                user_id=user.user_id,
                session_key=session_key,
                nickname=nickname if nickname and nickname != "微信用户" else "",
                avatar=avatar,
            )
            logger.info(
                "[wx-login] 老用户登录 user_id=%s openid=%s",
                user.user_id,
                openid[:8] + "***",
            )
            return user, False

        # 用户不存在 → 创建新用户
        user = await cls._create_user(
            openid=openid,
            unionid=unionid,
            nickname=nickname,
            avatar=avatar,
            session_key=session_key,
        )
        return user, True

    @classmethod
    async def get_user_by_user_id(cls, user_id: int) -> Optional[MiniappUser]:
        """按 user_id 查询用户（用于 token 校验后获取用户信息）"""
        async with DatabaseManager.get_session() as session:
            stmt = select(MiniappUser).where(
                MiniappUser.user_id == user_id,
                MiniappUser.is_delete == False,  # noqa: E712
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @classmethod
    async def update_profile(
        cls,
        user_id: int,
        fields: dict,
    ) -> Optional[MiniappUser]:
        """更新用户资料（仅更新 fields 中传入的非 None 字段）

        支持字段：nickname / avatar / phone / real_name / id_card /
                  bank_card / bank_name / bank_branch
        """
        allowed = {
            "nickname", "avatar", "phone", "real_name", "id_card",
            "bank_card", "bank_name", "bank_branch",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return await cls.get_user_by_user_id(user_id)

        async with DatabaseManager.get_session() as session:
            stmt = select(MiniappUser).where(
                MiniappUser.user_id == user_id,
                MiniappUser.is_delete == False,  # noqa: E712
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user is None:
                return None
            for key, value in updates.items():
                setattr(user, key, value)
            try:
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("[update_profile] 更新用户资料失败 user_id=%s: %s", user_id, e)
                raise
            await session.refresh(user)
            logger.info("[update_profile] 用户资料更新成功 user_id=%s fields=%s", user_id, list(updates.keys()))
            return user

    # ─────────────────────────────────────────────────────
    # 微信手机号授权（getPhoneNumber code → 手机号）
    # ─────────────────────────────────────────────────────

    @classmethod
    async def _get_wx_access_token(cls) -> str:
        """获取微信小程序 access_token（带进程内缓存，提前 300s 刷新）

        微信 access_token 有效期 7200s，缓存到内存避免频繁调用。
        """
        import time
        now = time.time()
        if _wx_access_token_cache["token"] and _wx_access_token_cache["expires_at"] > now + 300:
            return _wx_access_token_cache["token"]

        if not EnvConfig.WX_MINI_APPID or not EnvConfig.WX_MINI_SECRET:
            raise WxLoginError("微信小程序配置缺失（WX_MINI_APPID/WX_MINI_SECRET）")

        params = {
            "grant_type": "client_credential",
            "appid": EnvConfig.WX_MINI_APPID,
            "secret": EnvConfig.WX_MINI_SECRET,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(WX_REQUEST_TIMEOUT)) as client:
                response = await client.get(WX_ACCESS_TOKEN_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error("[wx-phone] 获取 access_token 失败: %s", e)
            raise WxLoginError("获取微信 access_token 失败") from e

        errcode = data.get("errcode", 0)
        if errcode != 0:
            logger.warning("[wx-phone] access_token 业务失败 errcode=%s errmsg=%s", errcode, data.get("errmsg"))
            raise WxLoginError(f"获取微信 access_token 失败: {data.get('errmsg')}", errcode=errcode)

        token = data.get("access_token", "")
        expires_in = data.get("expires_in", 7200)
        if not token:
            raise WxLoginError("微信 access_token 返回为空")

        _wx_access_token_cache["token"] = token
        _wx_access_token_cache["expires_at"] = now + expires_in
        return token

    @classmethod
    async def get_phone_by_code(cls, code: str) -> dict:
        """用微信 getPhoneNumber 回调 code 换取手机号

        Args:
            code: 小程序 button open-type="getPhoneNumber" 回调返回的 code
        Returns:
            {"phone": str, "countryCode": str}
        Raises:
            WxLoginError: 微信接口调用失败或 code 无效
        """
        if not code:
            raise WxLoginError("手机号授权 code 为空")

        access_token = await cls._get_wx_access_token()
        url = f"{WX_GET_PHONE_URL}?access_token={access_token}"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(WX_REQUEST_TIMEOUT)) as client:
                response = await client.post(url, json={"code": code})
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error("[wx-phone] 换手机号请求失败: %s", e)
            raise WxLoginError("获取手机号失败，请重试") from e

        errcode = data.get("errcode", 0)
        if errcode != 0:
            errmsg = data.get("errmsg", "unknown")
            logger.warning("[wx-phone] 换手机号业务失败 errcode=%s errmsg=%s", errcode, errmsg)
            if errcode == 40029:
                raise WxLoginError("手机号授权凭证无效，请重新授权", errcode=errcode)
            raise WxLoginError(f"获取手机号失败: {errmsg}", errcode=errcode)

        phone_info = data.get("phone_info", {})
        phone = phone_info.get("phoneNumber", "") or phone_info.get("purePhoneNumber", "")
        country_code = phone_info.get("countryCode", "")

        if not phone:
            logger.error("[wx-phone] 手机号返回为空: %s", data)
            raise WxLoginError("微信返回手机号为空")

        return {"phone": phone, "countryCode": country_code}
