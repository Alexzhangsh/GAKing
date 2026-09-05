// @ai-generated
/**
 * C端用户认证 API（对接后端 src/api/v1/c_user_auth.py）
 *
 * 接口清单（M03 升级）：
 * 1. POST /api/v1/user/auth/wx-login    微信官方登录（wx.login code → JWT）
 * 2. POST /api/v1/user/auth/verify      Token 校验（前端启动时检测登录态）
 * 3. POST /api/v1/user/auth/mock-login  Mock登录（保留开发测试用，仅开发环境）
 * 4. GET  /api/v1/user/auth/profile     获取当前用户信息
 */
import http from '@/utils/request'
import type {
  ApiResponse,
  LoginResponse,
  MockLoginRequest,
  PhoneCodeResponse,
  UpdateProfileRequest,
  UserProfileResponse,
  VerifyTokenResponse,
  WxLoginRequest
} from './types'

/**
 * 微信官方登录（M03 主入口）
 * @param code wx.login() 返回的临时登录凭证
 * @param nickname 用户昵称（可选）
 * @param avatar 头像URL（可选）
 */
export function wxLogin(
  code: string,
  nickname?: string,
  avatar?: string
): Promise<ApiResponse<LoginResponse>> {
  const body: WxLoginRequest = { code, nickname, avatar }
  return http.post<LoginResponse>('/api/v1/user/auth/wx-login', body, {
    skipAuth: true
  })
}

/**
 * Token 校验（前端启动时检测登录态，token 过期自动重新登录）
 * @param token JWT Token（为空时由后端从 Authorization 头读取）
 */
export function verifyToken(token?: string): Promise<ApiResponse<VerifyTokenResponse>> {
  const body = token ? { token } : {}
  return http.post<VerifyTokenResponse>('/api/v1/user/auth/verify', body, {
    skipAuth: true,
    silent: true
  })
}

/**
 * Mock登录（开发测试用，生产环境后端返回 403）
 * @param user_id 用户ID
 * @param nickname 用户昵称
 * @param avatar 头像URL
 */
export function mockLogin(
  user_id: number,
  nickname?: string,
  avatar?: string
): Promise<ApiResponse<LoginResponse>> {
  const body: MockLoginRequest = { user_id, nickname, avatar }
  return http.post<LoginResponse>('/api/v1/user/auth/mock-login', body, {
    skipAuth: true
  })
}

/**
 * 获取当前用户信息（需携带 Bearer Token）
 */
export function getProfile(): Promise<ApiResponse<UserProfileResponse>> {
  return http.get<UserProfileResponse>('/api/v1/user/auth/profile')
}

/**
 * 更新当前用户资料（PUT /profile，需 Bearer Token）
 * 所有字段可选，仅更新传入的非空字段
 */
export function updateProfile(
  body: UpdateProfileRequest
): Promise<ApiResponse<UserProfileResponse>> {
  return http.put<UserProfileResponse>('/api/v1/user/auth/profile', body)
}

/**
 * 用微信手机号授权 code 换取手机号（需 Bearer Token）
 * 微信 getPhoneNumber 回调返回 code，后端调用微信接口换手机号
 */
export function getPhoneByCode(code: string): Promise<ApiResponse<PhoneCodeResponse>> {
  return http.post<PhoneCodeResponse>('/api/v1/user/auth/phone', { code })
}

export default {
  wxLogin,
  verifyToken,
  mockLogin,
  getProfile,
  updateProfile
}
