// @ai-generated
import http from './request'

interface LoginResponse {
  token: string
  user_id: number
  nickname: string
  avatar: string
}

interface UserInfo {
  user_id: number
  nickname: string
  avatar: string
}

const auth = {
  async login(): Promise<LoginResponse> {
    return new Promise((resolve, reject) => {
      uni.login({
        provider: 'weixin',
        success: async (loginRes) => {
          try {
            const res = await http.post<LoginResponse>('/api/auth/login', {
              code: loginRes.code
            })
            
            if (res.data) {
              uni.setStorageSync('token', res.data.token)
              uni.setStorageSync('userInfo', JSON.stringify({
                user_id: res.data.user_id,
                nickname: res.data.nickname,
                avatar: res.data.avatar
              }))
              resolve(res.data)
            } else {
              reject(new Error('登录失败'))
            }
          } catch (error) {
            reject(error)
          }
        },
        fail: (error) => {
          reject(error)
        }
      })
    })
  },

  async getUserInfo(): Promise<UserInfo> {
    return new Promise((resolve, reject) => {
      uni.getUserProfile({
        desc: '用于完善会员资料',
        success: async (infoRes) => {
          try {
            const res = await http.post<UserInfo>('/api/auth/update-info', {
              nickname: infoRes.userInfo.nickName,
              avatar: infoRes.userInfo.avatarUrl
            })
            
            if (res.data) {
              uni.setStorageSync('userInfo', JSON.stringify(res.data))
              resolve(res.data)
            } else {
              reject(new Error('获取用户信息失败'))
            }
          } catch (error) {
            reject(error)
          }
        },
        fail: (error) => {
          reject(error)
        }
      })
    })
  },

  logout(): void {
    uni.removeStorageSync('token')
    uni.removeStorageSync('userInfo')
    uni.reLaunch({
      url: '/pages/index/index'
    })
  },

  isLoggedIn(): boolean {
    const token = uni.getStorageSync('token')
    return !!token
  },

  getToken(): string {
    return uni.getStorageSync('token') || ''
  },

  getStoredUserInfo(): UserInfo | null {
    const userInfoStr = uni.getStorageSync('userInfo')
    if (!userInfoStr) return null
    try {
      return JSON.parse(userInfoStr)
    } catch {
      return null
    }
  },

  async checkLogin(): Promise<boolean> {
    if (!this.isLoggedIn()) {
      return false
    }

    try {
      await http.get('/api/auth/verify')
      return true
    } catch {
      uni.removeStorageSync('token')
      uni.removeStorageSync('userInfo')
      return false
    }
  }
}

export default auth
export type { UserInfo }