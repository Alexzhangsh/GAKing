// @ai-generated
import type { UniApp.RequestOptions, UniApp.RequestSuccessCallbackResult } from '@dcloudio/uni-app'

const baseUrl = '/api'

interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

type RequestMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

const request = <T = any>(
  url: string,
  method: RequestMethod = 'GET',
  data?: Record<string, any>,
  options?: Partial<RequestOptions>
): Promise<ApiResponse<T>> => {
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync('token')
    
    uni.request({
      url: baseUrl + url,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
        ...options?.header
      },
      timeout: options?.timeout || 10000,
      success: (res: UniApp.RequestSuccessCallbackResult) => {
        const result = res.data as ApiResponse<T>
        
        if (result.code === 0) {
          resolve(result)
        } else if (result.code === 401) {
          uni.removeStorageSync('token')
          uni.removeStorageSync('userInfo')
          uni.showToast({
            title: '登录已过期',
            icon: 'none'
          })
          setTimeout(() => {
            uni.reLaunch({
              url: '/pages/login/login'
            })
          }, 1500)
          reject(result)
        } else {
          uni.showToast({
            title: result.message || '请求失败',
            icon: 'none'
          })
          reject(result)
        }
      },
      fail: (error) => {
        uni.showToast({
          title: '网络连接失败',
          icon: 'none'
        })
        reject(error)
      }
    })
  })
}

const http = {
  get: <T = any>(url: string, params?: Record<string, any>) => request<T>(url, 'GET', params),
  post: <T = any>(url: string, data?: Record<string, any>) => request<T>(url, 'POST', data),
  put: <T = any>(url: string, data?: Record<string, any>) => request<T>(url, 'PUT', data),
  delete: <T = any>(url: string, params?: Record<string, any>) => request<T>(url, 'DELETE', params)
}

export default http
export type { ApiResponse }