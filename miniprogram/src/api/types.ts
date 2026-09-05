// @ai-generated
/**
 * 后端字段类型定义（严格复用后端 Pydantic DTO）
 *
 * 对应后端文件：
 * - src/schemas/cps_goods.py (B01-B02 商品搜索/转链)
 * - src/schemas/cps.py (统一响应体 ApiResponse)
 * - src/api/v1/c_user_auth.py (C端用户认证)
 *
 * 字段名、类型与后端保持一致，禁止擅自更改。
 */

// ══════════════════════════════════════════════════════
// 统一响应体（src/schemas/cps.py: ApiResponse）
// ══════════════════════════════════════════════════════
export interface ApiResponse<T = any> {
  /** 业务状态码：200-成功，400-参数错误，500-服务异常 */
  code: number
  /** 提示消息 */
  msg: string
  /** 业务数据 */
  data: T
  /** 请求ID，用于链路追踪 */
  request_id?: string
}

// ══════════════════════════════════════════════════════
// 商品搜索 DTO（src/schemas/cps_goods.py）
// ══════════════════════════════════════════════════════

/** 渠道标识：myq(喵有券) / orderx(订单侠) / dta(大淘客) */
export type ChannelCode = 'myq' | 'orderx' | 'dta'

/** 商品搜索请求参数（GET /api/public/goods/search Query 参数） */
export interface GoodsSearchRequest {
  /** 搜索关键词，1-64 字符 */
  keyword: string
  /** 页码，从1开始，1-100 */
  page: number
  /** 每页条数，1-100 */
  size: number
  /** 渠道标识 */
  channel_code: ChannelCode
}

/**
 * 商品出参项（src/schemas/cps_goods.py: GoodsItemResponse）
 * 与 B01 GoodsDTO 字段对齐
 */
export interface GoodsItem {
  /** 商品唯一ID */
  goods_id: string
  /** 商品标题 */
  goods_title: string
  /** 商品主图URL */
  goods_img: string
  /** 商品原价(元) */
  original_price: number
  /** 券后售价(元) */
  sale_price: number
  /** 佣金比例(%) */
  commission_rate: number
  /** 预估佣金(元) */
  estimate_commission: number
  /** 类目 */
  category: string
  /** CPS推广链接 */
  promote_url: string
  /** 店铺名称 */
  shop_name: string
  /** 销量 */
  sales_volume: number
  /** 来源渠道标识 */
  source_channel: string
}

/** 商品搜索响应体（src/schemas/cps_goods.py: GoodsSearchResponse） */
export interface GoodsSearchResponse {
  /** 商品列表 */
  items: GoodsItem[]
  /** 总记录数 */
  total: number
  /** 当前页码 */
  page: number
  /** 每页条数 */
  size: number
  /** 是否命中缓存（调试用） */
  cache_hit: boolean
}

// ══════════════════════════════════════════════════════
// 链接转链 DTO（src/schemas/cps_goods.py）
// ══════════════════════════════════════════════════════

/** 链接转链请求体（POST /api/public/goods/convert-link） */
export interface ConvertLinkRequest {
  /** 原始商品链接，1-512 字符 */
  original_url: string
  /** 用户渠道溯源标识(relation_id)，1-64 字符 */
  user_channel_id: string
  /** 渠道标识 */
  channel_code: ChannelCode
}

/** 链接转链响应体（src/schemas/cps_goods.py: ConvertLinkResponse） */
export interface ConvertLinkResponse {
  /** CPS推广短链接 */
  promote_url: string
  /** 渠道PID */
  channel_pid: string
  /** 预估佣金(元) */
  estimate_commission: number
  /** 商品唯一ID */
  goods_id: string
  /** 实际使用的渠道标识 */
  channel_code: string
}

// ══════════════════════════════════════════════════════
// C端用户认证 DTO（src/api/v1/c_user_auth.py）
// ══════════════════════════════════════════════════════

/** Mock登录请求体（POST /api/v1/user/auth/mock-login） */
export interface MockLoginRequest {
  /** 用户ID（测试用，1-9999） */
  user_id: number
  /** 用户昵称 */
  nickname?: string
  /** 头像URL */
  avatar?: string
}

/**
 * 微信登录请求体（POST /api/v1/user/auth/wx-login）
 * 对应后端 WxLoginRequest
 */
export interface WxLoginRequest {
  /** wx.login() 返回的临时登录凭证（5分钟有效） */
  code: string
  /** 用户昵称（可选，默认"微信用户"） */
  nickname?: string
  /** 头像URL（可选） */
  avatar?: string
}

/**
 * 登录成功响应（对应后端 LoginResponse）
 * wx-login / mock-login 共用
 */
export interface LoginResponse {
  /** 平台用户ID */
  user_id: number
  /** 用户昵称 */
  nickname: string
  /** 头像URL */
  avatar: string
  /** JWT Token */
  token: string
  /** Token 过期时间(秒) */
  expires_in: number
  /** 是否首次注册（wx-login 专用，mock-login 固定为 false） */
  is_new_user: boolean
}

/**
 * Token 校验请求体（POST /api/v1/user/auth/verify）
 * 对应后端 VerifyTokenRequest
 */
export interface VerifyTokenRequest {
  /** JWT Token（与 Authorization 头二选一） */
  token?: string
}

/**
 * Token 校验响应（对应后端 VerifyResponse）
 */
export interface VerifyTokenResponse {
  /** Token 是否有效 */
  valid: boolean
  /** 用户ID（valid=false 时为 0） */
  user_id: number
  /** 用户昵称 */
  nickname: string
  /** 头像URL */
  avatar: string
  /** Token 过期时间(秒) */
  expires_in: number
}

/** 用户信息响应（src/api/v1/c_user_auth.py: UserProfileResponse） */
export interface UserProfileResponse {
  /** 用户ID */
  user_id: number
  /** 用户昵称 */
  nickname: string
  /** 头像URL */
  avatar: string
  /** JWT Token（仅登录接口返回，profile 接口为空） */
  token: string
  /** Token 过期时间(秒) */
  expires_in: number
  /** 手机号 */
  phone: string
  /** 真实姓名 */
  real_name: string
  /** 身份证号 */
  id_card: string
  /** 银行卡号 */
  bank_card: string
  /** 发卡银行（BIN自动识别） */
  bank_name: string
  /** 开户支行（用户手动输入） */
  bank_branch: string
}

/** 更新用户资料请求（所有字段可选，仅更新传入的字段） */
export interface UpdateProfileRequest {
  nickname?: string
  avatar?: string
  phone?: string
  real_name?: string
  id_card?: string
  bank_card?: string
  bank_name?: string
  bank_branch?: string
}

/** 微信手机号授权 code 换手机号响应 */
export interface PhoneCodeResponse {
  /** 手机号 */
  phone: string
  /** 区号（如 +86） */
  countryCode?: string
}

// ══════════════════════════════════════════════════════
// 本地收藏夹快照（前端本地缓存，基于 GoodsItem 扩展）
// ══════════════════════════════════════════════════════

/**
 * 收藏商品快照
 * 在后端商品基础上增加本地收藏元数据，商品下架后仍可展示一次
 */
export interface FavoriteItem extends GoodsItem {
  /** 收藏时间戳(ms) */
  favorite_time: number
  /** 是否已失效（商品下架/无法转链） */
  invalid?: boolean
}

// ══════════════════════════════════════════════════════
// CPS 订单 DTO（src/models/business/order_model.py + src/api/v1/cps_order.py）
// ══════════════════════════════════════════════════════

/**
 * 订单状态枚举（src/config/constants.py: OrderStatus）
 * PENDING=10 待付款 / FROZEN=20 冻结 / SETTLABLE=30 已付款待结算 /
 * SETTLED=40 已结算 / INVALID=50 失效 / REFUNDED=60 已退款
 */
export enum OrderStatus {
  PENDING = 10,
  FROZEN = 20,
  SETTLABLE = 30,
  SETTLED = 40,
  INVALID = 50,
  REFUNDED = 60
}

/** 订单状态中文映射 */
export const ORDER_STATUS_TEXT: Record<number, string> = {
  [OrderStatus.PENDING]: '待付款',
  [OrderStatus.FROZEN]: '冻结中',
  [OrderStatus.SETTLABLE]: '待结算',
  [OrderStatus.SETTLED]: '已结算',
  [OrderStatus.INVALID]: '已失效',
  [OrderStatus.REFUNDED]: '已退款'
}

/**
 * 订单出参（Order.to_dict()）
 * 字段与后端 src/models/business/order_model.py 完全对齐
 */
export interface OrderItem {
  /** 订单ID */
  id: number
  /** 用户ID */
  user_id: number
  /** 渠道订单号 */
  out_order_no: string
  /** 平台内部订单号 */
  internal_order_no: string
  /** 商品标题 */
  goods_title: string
  /** 商品主图URL */
  goods_img: string
  /** 支付金额(元) */
  pay_amount: number
  /** 总佣金(元) */
  total_commission: number
  /** 用户佣金(元) */
  user_commission: number
  /** 平台佣金(元) */
  platform_commission: number
  /** 渠道标识：myq/orderx */
  channel_code: string
  /** 订单状态：10/20/30/40/50/60 */
  order_status: number
  /** 支付时间 */
  pay_time: string | null
  /** 结算时间 */
  settle_time: string | null
  /** 微信转账批次ID */
  wx_batch_id: string
  /** 转账状态：PENDING/PROCESSING/SUCCESS/FAILED */
  transfer_status: string
  /** 是否删除 */
  is_delete: boolean
  /** 创建时间 */
  create_time: string
  /** 更新时间 */
  update_time: string
}

/** 订单列表响应（OrderService.list_orders） */
export interface OrderListResponse {
  /** 订单列表 */
  list: OrderItem[]
  /** 总记录数 */
  total: number
  /** 当前页码 */
  page: number
  /** 每页条数 */
  page_size: number
}

/**
 * 佣金流水出参（CommissionFlow.to_dict()）
 * 字段与后端 src/models/business/commission_flow_model.py 完全对齐
 */
export interface CommissionFlow {
  /** 流水ID */
  id: number
  /** 关联订单ID */
  order_id: number
  /** 用户ID */
  user_id: number
  /** 流水类型：ORDER-订单佣金/SUPPLEMENT-补发/DEDUCT-扣减 */
  flow_type: string
  /** 流水金额(元) */
  amount: number
  /** 变更前余额(元) */
  before_balance: number
  /** 变更后余额(元) */
  after_balance: number
  /** 微信转账批次ID */
  transfer_batch_id: string
  /** 转账状态：PENDING/PROCESSING/SUCCESS/FAILED */
  transfer_status: string
  /** 备注说明 */
  remark: string
  /** 是否删除 */
  is_delete: boolean
  /** 创建时间 */
  create_time: string
  /** 更新时间 */
  update_time: string
}

/** 订单详情响应（含佣金流水，OrderService.get_order_detail） */
export interface OrderDetailResponse extends OrderItem {
  /** 关联佣金流水列表 */
  commission_flows: CommissionFlow[]
}

/** 订单佣金汇总响应（CommissionService.summarize_order_commission） */
export interface CommissionSummary {
  /** 订单ID */
  order_id: number
  /** 总佣金金额(元) */
  total_amount: number
  /** 流水条数 */
  flow_count: number
}

// ══════════════════════════════════════════════════════
// 用户佣金账户 DTO（src/models/business/user_commission_account_model.py）
// ══════════════════════════════════════════════════════

/**
 * 用户佣金账户出参（UserCommissionAccount.to_dict()）
 * 字段与后端 src/models/business/user_commission_account_model.py 对齐
 */
export interface UserAccount {
  /** 账户ID */
  id?: number
  /** 平台用户ID */
  user_id: number
  /** 累计佣金余额(元) */
  total_balance: number
  /** 可用余额(元) - 可提现 */
  available_balance: number
  /** 冻结余额(元) - 提现申请中 */
  frozen_balance: number
  /** 累计已提现(元) */
  cumulative_withdrawn: number
  /** 累计手续费(元) */
  cumulative_fee: number
  /** 最近结算日期 */
  last_settle_date: string | null
  /** 乐观锁版本号 */
  version: number
  /** 是否删除 */
  is_delete?: boolean
  /** 创建时间 */
  create_time?: string
  /** 更新时间 */
  update_time?: string
}

// ══════════════════════════════════════════════════════
// 用户提现 DTO（src/models/business/user_withdraw_apply_model.py + src/schemas/withdraw.py）
// ══════════════════════════════════════════════════════

/**
 * 提现状态枚举（src/config/constants.py: WithdrawStatus）
 * 流转：PENDING → APPROVED → PROCESSING → SUCCESS
 *       任一审核中/通过状态可 → REJECTED
 */
export enum WithdrawStatus {
  PENDING = 'PENDING',
  APPROVED = 'APPROVED',
  PROCESSING = 'PROCESSING',
  SUCCESS = 'SUCCESS',
  REJECTED = 'REJECTED'
}

/** 提现状态中文映射 */
export const WITHDRAW_STATUS_TEXT: Record<string, string> = {
  [WithdrawStatus.PENDING]: '审核中',
  [WithdrawStatus.APPROVED]: '已通过',
  [WithdrawStatus.PROCESSING]: '打款中',
  [WithdrawStatus.SUCCESS]: '已到账',
  [WithdrawStatus.REJECTED]: '已驳回'
}

/** 提现申请请求体（POST /api/v1/withdraw/apply，src/schemas/withdraw.py: WithdrawApplyRequest） */
export interface WithdrawApplyRequest {
  /** 申请提现金额(元)，需 >= 10 元 */
  apply_amount: number
}

/**
 * 提现申请出参（UserWithdrawApply.to_dict()）
 * 字段与后端 src/models/business/user_withdraw_apply_model.py 对齐
 */
export interface WithdrawApplyItem {
  /** 申请ID */
  id: number
  /** 提现单号（GAKW前缀） */
  apply_no: string
  /** 平台用户ID */
  user_id: number
  /** 申请提现金额(元) */
  apply_amount: number
  /** 手续费(元) */
  fee: number
  /** 实际到账金额(元) */
  actual_amount: number
  /** 状态：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED */
  status: string
  /** 审核人ID */
  review_user_id: number | null
  /** 审核备注 */
  review_remark: string
  /** 审核时间 */
  review_time: string | null
  /** 微信转账批次ID */
  transfer_batch_id: string
  /** 打款完成时间 */
  transfer_time: string | null
  /** 驳回原因 */
  reject_reason: string
  /** 备注 */
  remark: string
  /** 是否删除 */
  is_delete: boolean
  /** 创建时间 */
  create_time: string
  /** 更新时间 */
  update_time: string
}

/** 提现记录列表响应（WithdrawService.list_my_applies） */
export interface WithdrawListResponse {
  /** 提现记录列表 */
  list: WithdrawApplyItem[]
  /** 总记录数 */
  total: number
  /** 当前页码 */
  page: number
  /** 每页条数 */
  page_size: number
}

// ══════════════════════════════════════════════════════
// 站内消息 DTO（src/models/business/b10_user_message_model.py + b10_message_service.py）
// ══════════════════════════════════════════════════════

/**
 * 消息类型（src/config/b10_constants.py: MessageType）
 * commission=佣金 / withdraw=提现 / order=订单 / refund=退款
 */
export type MessageType = 'commission' | 'withdraw' | 'order' | 'refund'

/** 消息类型中文映射 */
export const MESSAGE_TYPE_TEXT: Record<string, string> = {
  commission: '佣金',
  withdraw: '提现',
  order: '订单',
  refund: '退款'
}

/**
 * 站内消息出参（UserMessage.to_dict() + route_url 补充）
 * 字段与后端 b10_user_message_model.py 对齐
 */
export interface MessageItem {
  /** 消息ID */
  id: number
  /** 接收用户ID */
  user_id: number
  /** 消息业务类型：commission/withdraw/order/refund */
  message_type: string
  /** 消息标题 */
  title: string
  /** 消息内容摘要 */
  content: string
  /** 关联业务ID（用于前端跳转） */
  biz_id: string
  /** 已读状态：0=未读 1=已读 */
  is_read: number
  /** 已读时间 */
  read_time: string
  /** 推送状态：0=待推送 1=已推送 2=推送失败 */
  push_status: number
  /** 推送失败原因 */
  push_error: string
  /** 前端跳转路由（后端补充） */
  route_url: string
  /** 创建时间 */
  create_time: string
  /** 更新时间 */
  update_time: string
}

/** 消息列表响应（B10MessageService.list_user_messages） */
export interface MessageListResponse {
  /** 消息列表 */
  list: MessageItem[]
  /** 总记录数 */
  total: number
  /** 当前页码 */
  page: number
  /** 每页条数 */
  page_size: number
}

/** 未读消息数响应 */
export interface UnreadCountResponse {
  /** 未读消息数 */
  unread_count: number
}

/** 标记已读请求体（src/schemas/b10_message.py: MarkReadRequest） */
export interface MarkReadRequest {
  /** 消息ID（为空时标记全部已读） */
  message_id?: number
}

// ══════════════════════════════════════════════════════
// 营销消息订阅 DTO（src/schemas/b15_message_user.py + b15_message_user_service.py）
// ══════════════════════════════════════════════════════

/**
 * 可订阅模板项（消息中心订阅弹窗渲染用）
 * 对应后端 SubscribeTemplateItem
 */
export interface SubscribeTemplate {
  /** 模板ID */
  id: number
  /** 模板名称 */
  template_name: string
  /** 微信订阅消息模板ID */
  tmpl_id: string
  /** 消息标题 */
  title: string
  /** 消息内容（支持占位符） */
  content: string
  /** 关键词列表 */
  keywords: string[] | null
}

/**
 * 订阅状态项（按模板返回）
 * 对应后端 SubscribeStatusItem
 */
export interface SubscribeStatusItem {
  /** 模板ID */
  template_id: number
  /** 模板名称 */
  template_name: string
  /** 微信订阅消息模板ID */
  tmpl_id: string
  /** 订阅状态：1=已订阅 0=未订阅/已取消 */
  subscribe_status: number
  /** 订阅时间 */
  subscribe_time: string | null
  /** 过期时间 */
  expire_time: string | null
  /** 是否已过期（一次性模板7天有效期） */
  expired: boolean
}

/**
 * 订阅授权请求体（POST /api/v1/message/subscribe）
 * 对应后端 SubscribeRequest
 */
export interface SubscribeRequest {
  /** 消息模板ID */
  template_id: number
  /** 授权结果：accept=已同意 reject=用户拒绝 expired=授权过期/不可用 */
  action: 'accept' | 'reject' | 'expired'
  /** 微信订阅消息模板ID（冗余存储，可选） */
  tmpl_id?: string
}

/** 取消订阅请求体（POST /api/v1/message/unsubscribe） */
export interface UnsubscribeRequest {
  /** 消息模板ID */
  template_id: number
}

