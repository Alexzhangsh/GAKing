# @ai-generated
"""
C端用户认证 API（M03 升级：微信官方OAuth登录 + 开发兜底）
路由前缀：/api/v1/user/auth

本模块提供C端小程序用户的登录鉴权接口：
1. POST /api/v1/user/auth/wx-login    微信官方登录（wx.login code → openid → JWT）
   - WX_MINI_APPID 已配置：走 code2session 官方流程
   - WX_MINI_APPID 未配置：走 dev 兜底（按 code 生成稳定 mock openid）
2. POST /api/v1/user/auth/verify      Token 校验（前端启动时检测登录态）
3. POST /api/v1/user/auth/mock-login  Mock登录（保留开发测试用，仅开发环境）
4. GET  /api/v1/user/auth/profile     获取当前用户信息

业务边界（遵循《小程序&后台登录权限专项规范》）：
- JWT 载荷仅存 user_id / username / role_id，不存敏感信息
- /api/v1/user/auth/** 路由层级为公开接口，无需 JwtAuthGuard
- 业务接口（订单/佣金/提现）通过 Bearer Token 鉴权
"""
import logging
from typing import Optional

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from src.api.v1.response_util import (
    get_request_id,
    success_response,
    error_response,
    handle_service_exception,
)
from src.common.auth_util import JwtAuthGuard
from src.config.env_config import EnvConfig
from src.services.miniapp_user_service import MiniappUserService, WxLoginError

logger = logging.getLogger("api.c_user_auth")

router = APIRouter(prefix="/api/v1/user/auth", tags=["C端用户认证"])


# ─────────────────────────────────────────────────────
# 请求/响应 Schema
# ─────────────────────────────────────────────────────


class WxLoginRequest(BaseModel):
    """微信登录请求

    code: wx.login() 返回的临时登录凭证（5分钟有效）
    nickname: 用户昵称（可选，默认"微信用户"，用户授权后可更新）
    avatar: 用户头像URL（可选）
    """

    code: str = Field(..., min_length=1, description="wx.login() 返回的临时登录凭证")
    nickname: Optional[str] = Field(default="微信用户", description="用户昵称")
    avatar: Optional[str] = Field(default="", description="头像URL")


class VerifyTokenRequest(BaseModel):
    """Token 校验请求（可选，支持 body 传 token 或 header 传 Bearer）"""

    token: Optional[str] = Field(default=None, description="JWT Token（与 Authorization 头二选一）")


class MockLoginRequest(BaseModel):
    """Mock登录请求（仅开发测试用）"""

    user_id: int = Field(..., ge=1, le=100000, description="用户ID（测试用，1-100000）")
    nickname: Optional[str] = Field(default="测试用户", description="用户昵称")
    avatar: Optional[str] = Field(default="", description="头像URL")


class LoginResponse(BaseModel):
    """登录成功响应"""

    user_id: int
    nickname: str
    avatar: str = ""
    token: str
    expires_in: int
    is_new_user: bool = False


class VerifyResponse(BaseModel):
    """Token 校验响应"""

    valid: bool
    user_id: int = 0
    nickname: str = ""
    avatar: str = ""
    expires_in: int = 0


class UserProfileResponse(BaseModel):
    """用户信息响应"""

    user_id: int
    nickname: str
    avatar: str = ""
    token: str = ""
    expires_in: int = 0
    # ── 提款报税所需个人资料 ──
    phone: str = ""
    real_name: str = ""
    id_card: str = ""
    bank_card: str = ""
    bank_name: str = ""
    bank_branch: str = ""


class UpdateProfileRequest(BaseModel):
    """更新用户资料请求（所有字段可选，仅更新传入的字段）"""

    nickname: Optional[str] = Field(default=None, description="用户昵称")
    avatar: Optional[str] = Field(default=None, description="头像URL")
    phone: Optional[str] = Field(default=None, description="手机号")
    real_name: Optional[str] = Field(default=None, description="真实姓名")
    id_card: Optional[str] = Field(default=None, description="身份证号")
    bank_card: Optional[str] = Field(default=None, description="银行卡号")
    bank_name: Optional[str] = Field(default=None, description="发卡银行")
    bank_branch: Optional[str] = Field(default=None, description="开户支行")


# ─────────────────────────────────────────────────────
# 微信官方登录接口（M03 主入口）
# ─────────────────────────────────────────────────────


@router.post("/wx-login")
async def wx_login(body: WxLoginRequest, request: Request):
    """微信官方OAuth登录

    流程：
    1. 接收小程序 wx.login() 返回的 code
    2. 调用 MiniappUserService.login_by_code 换取 openid
       - WX_MINI_APPID 已配置：走 code2session 官方流程
       - WX_MINI_APPID 未配置：走 dev 兜底（按 code 生成稳定 mock openid）
    3. 按 openid 查找或创建 MiniappUser（首次自动开通佣金账户）
    4. 生成 JWT Token 返回

    返回：LoginResponse（含 token / user_id / is_new_user）
    """
    request_id = get_request_id(request)

    try:
        # Step1: code → openid → 用户查找/创建
        user, is_new_user = await MiniappUserService.login_by_code(
            code=body.code,
            nickname=body.nickname or "微信用户",
            avatar=body.avatar or "",
        )

        # Step2: 生成 JWT（role_id=0 标识 C 端普通用户）
        token = JwtAuthGuard.create_token(
            user_id=user.user_id,
            username=user.nickname,
            role_id=0,
        )

        result = LoginResponse(
            user_id=user.user_id,
            nickname=user.nickname,
            avatar=user.avatar,
            token=token,
            expires_in=JwtAuthGuard._expires_in,
            is_new_user=is_new_user,
        )

        logger.info(
            "[request_id=%s] 微信登录成功 user_id=%s is_new_user=%s",
            request_id,
            user.user_id,
            is_new_user,
        )

        return success_response(
            data=result.model_dump(),
            msg="登录成功",
            request_id=request_id,
        )

    except WxLoginError as exc:
        logger.warning(
            "[request_id=%s] 微信登录业务失败: %s (errcode=%s)",
            request_id,
            exc.message,
            exc.errcode,
        )
        return error_response(
            code=400,
            msg=exc.message,
            request_id=request_id,
        )
    except Exception as exc:
        logger.error(
            "[request_id=%s] 微信登录异常: %s",
            request_id,
            str(exc),
            exc_info=True,
        )
        return handle_service_exception(exc, request_id)


# ─────────────────────────────────────────────────────
# Token 校验接口（前端启动时检测登录态）
# ─────────────────────────────────────────────────────


@router.post("/verify")
async def verify_token(
    request: Request,
    body: Optional[VerifyTokenRequest] = None,
    authorization: Optional[str] = Header(default=None),
):
    """Token 校验接口

    支持两种传参方式：
    1. Authorization: Bearer <token> 请求头
    2. body.token 字段

    返回：VerifyResponse（valid=true 时附带用户信息）
    - Token 无效/过期 → valid=false（HTTP 200，业务码 200，前端据此跳转登录）
    """
    request_id = get_request_id(request)

    # 提取 token：优先 body，其次 Authorization 头
    token = ""
    if body and body.token:
        token = body.token
    elif authorization:
        # 兼容 "Bearer xxx" 和 "xxx" 两种格式
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token:
        result = VerifyResponse(valid=False)
        return success_response(
            data=result.model_dump(),
            msg="未提供 Token",
            request_id=request_id,
        )

    # 校验 token
    payload = JwtAuthGuard.verify_token(token)
    if not payload:
        logger.info("[request_id=%s] Token 校验失败（无效或过期）", request_id)
        result = VerifyResponse(valid=False)
        return success_response(
            data=result.model_dump(),
            msg="Token 已过期，请重新登录",
            request_id=request_id,
        )

    user_id = int(payload.get("user_id", 0))
    if user_id <= 0:
        result = VerifyResponse(valid=False)
        return success_response(
            data=result.model_dump(),
            msg="Token 载荷无效",
            request_id=request_id,
        )

    # 查询用户信息（确认用户仍存在且未禁用）
    user = await MiniappUserService.get_user_by_user_id(user_id)
    if user is None:
        logger.info("[request_id=%s] Token 对应用户不存在 user_id=%s", request_id, user_id)
        result = VerifyResponse(valid=False)
        return success_response(
            data=result.model_dump(),
            msg="用户不存在，请重新登录",
            request_id=request_id,
        )

    # 返回配置的过期时长（前端基于 JWT payload.exp 自行计算剩余有效期）
    expires_in = JwtAuthGuard._expires_in

    result = VerifyResponse(
        valid=True,
        user_id=user.user_id,
        nickname=user.nickname,
        avatar=user.avatar,
        expires_in=expires_in,
    )

    return success_response(
        data=result.model_dump(),
        msg="Token 有效",
        request_id=request_id,
    )


# ─────────────────────────────────────────────────────
# Mock 登录接口（保留开发测试用）
# ─────────────────────────────────────────────────────


@router.post("/mock-login")
async def mock_login(body: MockLoginRequest, request: Request):
    """Mock登录接口（仅用于开发测试）

    生产环境请使用 /wx-login 接口走真实微信登录流程。
    开发环境可直接指定 user_id 获取 token，便于测试不同用户的订单/佣金数据。
    """
    request_id = get_request_id(request)

    # 生产环境禁用 mock-login
    if EnvConfig.is_production():
        return error_response(
            code=403,
            msg="生产环境禁止使用 mock-login",
            request_id=request_id,
        )

    try:
        # 生成JWT token（C端用户使用 role_id=0 标识为普通用户）
        token = JwtAuthGuard.create_token(
            user_id=body.user_id,
            username=body.nickname,
            role_id=0,
        )

        result = LoginResponse(
            user_id=body.user_id,
            nickname=body.nickname or "测试用户",
            avatar=body.avatar or "",
            token=token,
            expires_in=JwtAuthGuard._expires_in,
            is_new_user=False,
        )

        logger.info(
            "[request_id=%s] Mock登录成功 user_id=%s nickname=%s",
            request_id,
            body.user_id,
            body.nickname,
        )

        return success_response(
            data=result.model_dump(),
            msg="登录成功",
            request_id=request_id,
        )
    except Exception as exc:
        logger.error(
            "[request_id=%s] Mock登录失败: %s",
            request_id,
            str(exc),
        )
        return handle_service_exception(exc, request_id)


# ─────────────────────────────────────────────────────
# 获取当前用户信息（通过 Bearer Token）
# ─────────────────────────────────────────────────────


@router.get("/profile")
async def get_profile(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    """获取当前用户信息

    支持两种鉴权方式：
    1. Authorization: Bearer <token>（推荐，标准 JWT 鉴权）
    2. X-User-Id: <user_id>（兼容旧版 mock 登录，仅开发环境）

    返回：UserProfileResponse
    """
    request_id = get_request_id(request)

    try:
        user_id = 0

        # 优先解析 Bearer Token
        if authorization:
            token = authorization.strip()
            if token.lower().startswith("bearer "):
                token = token[7:].strip()
            payload = JwtAuthGuard.verify_token(token)
            if payload:
                user_id = int(payload.get("user_id", 0))
            else:
                return error_response(
                    code=401,
                    msg="登录已超时，请重新登录",
                    request_id=request_id,
                )
        elif x_user_id:
            # 兼容旧版 X-User-Id 头（仅开发环境）
            try:
                user_id = int(x_user_id)
            except (ValueError, TypeError):
                user_id = 0

        if user_id <= 0:
            return error_response(
                code=401,
                msg="未登录",
                request_id=request_id,
            )

        # 查询用户信息
        user = await MiniappUserService.get_user_by_user_id(user_id)
        if user is None:
            return error_response(
                code=401,
                msg="用户不存在，请重新登录",
                request_id=request_id,
            )

        if user.status == 1:
            return error_response(
                code=403,
                msg="账号已被禁用",
                request_id=request_id,
            )

        result = UserProfileResponse(
            user_id=user.user_id,
            nickname=user.nickname,
            avatar=user.avatar,
            expires_in=JwtAuthGuard._expires_in,
            phone=getattr(user, "phone", "") or "",
            real_name=getattr(user, "real_name", "") or "",
            id_card=getattr(user, "id_card", "") or "",
            bank_card=getattr(user, "bank_card", "") or "",
            bank_name=getattr(user, "bank_name", "") or "",
            bank_branch=getattr(user, "bank_branch", "") or "",
        )

        return success_response(
            data=result.model_dump(),
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ─────────────────────────────────────────────────────
# 更新当前用户资料（PUT /profile）
# ─────────────────────────────────────────────────────


@router.put("/profile")
async def update_profile(
    body: UpdateProfileRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """更新当前用户资料

    所有字段可选，仅更新传入的非 None 字段。
    支持：nickname / avatar / phone / real_name / id_card /
          bank_card / bank_name / bank_branch

    需 Bearer Token 鉴权。
    """
    request_id = get_request_id(request)

    try:
        # 解析 Bearer Token
        if not authorization:
            return error_response(code=401, msg="未登录", request_id=request_id)
        token = authorization.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        payload = JwtAuthGuard.verify_token(token)
        if not payload:
            return error_response(code=401, msg="登录已超时，请重新登录", request_id=request_id)
        user_id = int(payload.get("user_id", 0))
        if user_id <= 0:
            return error_response(code=401, msg="未登录", request_id=request_id)

        # 执行更新
        fields = body.model_dump(exclude_unset=True)
        user = await MiniappUserService.update_profile(user_id, fields)
        if user is None:
            return error_response(code=401, msg="用户不存在，请重新登录", request_id=request_id)
        if user.status == 1:
            return error_response(code=403, msg="账号已被禁用", request_id=request_id)

        result = UserProfileResponse(
            user_id=user.user_id,
            nickname=user.nickname,
            avatar=user.avatar,
            expires_in=JwtAuthGuard._expires_in,
            phone=getattr(user, "phone", "") or "",
            real_name=getattr(user, "real_name", "") or "",
            id_card=getattr(user, "id_card", "") or "",
            bank_card=getattr(user, "bank_card", "") or "",
            bank_name=getattr(user, "bank_name", "") or "",
            bank_branch=getattr(user, "bank_branch", "") or "",
        )

        logger.info(
            "[request_id=%s] 用户资料更新成功 user_id=%s fields=%s",
            request_id, user_id, list(fields.keys()),
        )

        return success_response(
            data=result.model_dump(),
            msg="资料更新成功",
            request_id=request_id,
        )
    except Exception as exc:
        logger.error("[request_id=%s] 更新用户资料异常: %s", request_id, str(exc), exc_info=True)
        return handle_service_exception(exc, request_id)


# ─────────────────────────────────────────────────────
# 微信手机号授权（code → 手机号）
# ─────────────────────────────────────────────────────


class PhoneCodeRequest(BaseModel):
    """微信手机号授权 code 请求"""
    code: str = Field(..., min_length=1, description="getPhoneNumber 回调返回的 code")


class PhoneCodeResponse(BaseModel):
    """手机号响应"""
    phone: str
    countryCode: str = ""


@router.post("/phone")
async def get_phone_by_code(
    body: PhoneCodeRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """用微信 getPhoneNumber 授权 code 换取手机号

    小程序端 button open-type="getPhoneNumber" 回调返回 code，
    后端调用微信 getuserphonenumber 接口换取手机号。

    需 Bearer Token 鉴权。
    """
    request_id = get_request_id(request)

    try:
        # 鉴权
        if not authorization:
            return error_response(code=401, msg="未登录", request_id=request_id)
        token = authorization.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        payload = JwtAuthGuard.verify_token(token)
        if not payload:
            return error_response(code=401, msg="登录已超时，请重新登录", request_id=request_id)

        # 调用微信接口换手机号
        phone_data = await MiniappUserService.get_phone_by_code(body.code)
        result = PhoneCodeResponse(
            phone=phone_data.get("phone", ""),
            countryCode=phone_data.get("countryCode", ""),
        )

        logger.info("[request_id=%s] 手机号换取成功 user_id=%s", request_id, payload.get("user_id"))
        return success_response(data=result.model_dump(), request_id=request_id)

    except WxLoginError as exc:
        logger.warning("[request_id=%s] 手机号换取失败: %s", request_id, exc.message)
        return error_response(code=400, msg=exc.message, request_id=request_id)
    except Exception as exc:
        logger.error("[request_id=%s] 手机号换取异常: %s", request_id, str(exc), exc_info=True)
        return handle_service_exception(exc, request_id)
