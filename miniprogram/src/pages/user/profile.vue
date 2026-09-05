<!-- @ai-generated -->
<!--
  个人资料页
  - 微信头像（open-type="chooseAvatar"，微信新规）
  - 昵称（input type="nickname"，微信新规）
  - 提款报税资料：手机号 / 真实姓名 / 身份证号 / 银行卡号 / 发卡银行（BIN自动识别）/ 开户支行
  - 保存到后端 PUT /api/v1/user/auth/profile

  注意：chooseAvatar 返回临时路径，本次会话有效；持久化需后续接入 OBS 上传接口。
-->
<template>
  <view class="profile-page">
    <!-- 顶部导航 -->
    <view class="nav-bar">
      <view class="nav-back" @click="handleBack">
        <text class="nav-back-icon">‹</text>
      </view>
      <text class="nav-title">个人资料</text>
      <view class="nav-placeholder"></view>
    </view>

    <!-- 头像区域 -->
    <view class="avatar-section">
      <button class="avatar-btn" open-type="chooseAvatar" @chooseavatar="onChooseAvatar">
        <image
          class="avatar-img"
          :src="form.avatar || '/static/avatar-default.png'"
          mode="aspectFill"
          @error="onAvatarError"
        />
        <view class="avatar-mask">
          <text class="avatar-mask-text">更换头像</text>
        </view>
      </button>
      <text class="avatar-tip">点击更换微信头像</text>
    </view>

    <!-- 表单卡片 -->
    <view class="form-card">
      <!-- 昵称 -->
      <view class="form-item">
        <text class="form-label">昵称</text>
        <input
          class="form-input"
          type="nickname"
          v-model="form.nickname"
          placeholder="请输入昵称"
          placeholder-class="input-placeholder"
        />
      </view>

      <view class="form-divider"></view>

      <!-- 手机号（微信授权 + 手动输入） -->
      <view class="form-item">
        <text class="form-label">手机号</text>
        <input
          class="form-input"
          type="number"
          v-model="form.phone"
          placeholder="请输入手机号"
          placeholder-class="input-placeholder"
          maxlength="11"
        />
        <button
          class="phone-auth-btn"
          open-type="getPhoneNumber"
          @getphonenumber="onGetPhoneNumber"
        >微信授权</button>
      </view>

      <view class="form-divider"></view>

      <!-- 真实姓名 -->
      <view class="form-item">
        <text class="form-label">真实姓名</text>
        <input
          class="form-input"
          v-model="form.real_name"
          placeholder="请输入真实姓名"
          placeholder-class="input-placeholder"
        />
      </view>

      <view class="form-divider"></view>

      <!-- 身份证号 -->
      <view class="form-item">
        <text class="form-label">身份证号</text>
        <input
          class="form-input"
          v-model="form.id_card"
          placeholder="请输入身份证号"
          placeholder-class="input-placeholder"
          maxlength="18"
        />
      </view>
    </view>

    <!-- 提款信息卡片 -->
    <view class="form-card">
      <view class="card-title">
        <text class="card-title-text">提款信息</text>
        <text class="card-title-desc">用于提现报税，请如实填写</text>
      </view>

      <!-- 银行卡号 -->
      <view class="form-item">
        <text class="form-label">银行卡号</text>
        <input
          class="form-input"
          type="number"
          v-model="form.bank_card"
          placeholder="请输入银行卡号"
          placeholder-class="input-placeholder"
          maxlength="19"
          @input="onBankCardInput"
        />
      </view>

      <view class="form-divider"></view>

      <!-- 发卡银行（BIN自动识别） -->
      <view class="form-item">
        <text class="form-label">发卡银行</text>
        <input
          class="form-input"
          v-model="form.bank_name"
          placeholder="输入卡号后自动识别"
          placeholder-class="input-placeholder"
        />
        <text v-if="bankDetected" class="bank-tag">自动识别</text>
      </view>

      <view class="form-divider"></view>

      <!-- 开户支行 -->
      <view class="form-item">
        <text class="form-label">开户支行</text>
        <input
          class="form-input"
          v-model="form.bank_branch"
          placeholder="如：工行上海张江支行"
          placeholder-class="input-placeholder"
        />
      </view>
    </view>

    <!-- 保存按钮 -->
    <view class="save-section">
      <view
        class="save-btn"
        :class="{ disabled: saving }"
        @click="handleSave"
      >
        <text v-if="saving" class="save-btn-text">保存中...</text>
        <text v-else class="save-btn-text">保存资料</text>
      </view>
    </view>

    <view class="bottom-space"></view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { getProfile, updateProfile, getPhoneByCode } from '@/api/user'
import auth from '@/utils/auth'

/* ── BIN 映射表（银行卡号前6位 → 发卡银行） ── */
const BIN_MAP: Record<string, string> = {
  // 工商银行
  '622202': '中国工商银行', '622208': '中国工商银行', '621226': '中国工商银行',
  '621227': '中国工商银行', '621722': '中国工商银行', '621723': '中国工商银行',
  '620058': '中国工商银行',
  // 建设银行
  '621700': '中国建设银行', '622700': '中国建设银行', '621081': '中国建设银行',
  '621080': '中国建设银行', '436742': '中国建设银行', '622280': '中国建设银行',
  // 农业银行
  '622848': '中国农业银行', '622843': '中国农业银行', '621336': '中国农业银行',
  '623018': '中国农业银行', '622845': '中国农业银行', '622846': '中国农业银行',
  // 中国银行
  '621661': '中国银行', '621660': '中国银行', '621785': '中国银行',
  '621786': '中国银行', '456351': '中国银行', '621283': '中国银行',
  '621662': '中国银行', '621663': '中国银行',
  // 交通银行
  '622260': '交通银行', '622261': '交通银行', '621286': '交通银行',
  '405512': '交通银行', '622262': '交通银行', '622263': '交通银行',
  // 招商银行
  '622588': '招商银行', '621483': '招商银行', '622609': '招商银行',
  '621485': '招商银行', '621486': '招商银行', '356885': '招商银行',
  // 浦发银行
  '622516': '上海浦东发展银行', '622517': '上海浦东发展银行', '621352': '上海浦东发展银行',
  '622518': '上海浦东发展银行', '622519': '上海浦东发展银行',
  // 中信银行
  '622690': '中信银行', '622691': '中信银行', '621768': '中信银行',
  '622692': '中信银行', '621771': '中信银行', '622696': '中信银行',
  // 兴业银行
  '622908': '兴业银行', '622909': '兴业银行', '621280': '兴业银行',
  '438589': '兴业银行', '622901': '兴业银行',
  // 民生银行
  '622622': '中国民生银行', '622615': '中国民生银行', '621691': '中国民生银行',
  '622618': '中国民生银行', '622619': '中国民生银行',
  // 光大银行
  '622660': '中国光大银行', '622662': '中国光大银行', '621492': '中国光大银行',
  '622663': '中国光大银行', '622664': '中国光大银行', '622665': '中国光大银行',
  // 华夏银行
  '622630': '华夏银行', '622631': '华夏银行', '621222': '华夏银行',
  '622632': '华夏银行', '622633': '华夏银行',
  // 平安银行
  '622155': '平安银行', '622156': '平安银行', '621626': '平安银行',
  '622157': '平安银行', '622158': '平安银行', '622159': '平安银行',
  // 邮储银行
  '621799': '中国邮政储蓄银行', '621798': '中国邮政储蓄银行', '621098': '中国邮政储蓄银行',
  '620062': '中国邮政储蓄银行', '622188': '中国邮政储蓄银行', '622150': '中国邮政储蓄银行',
  // 广发银行
  '622568': '广发银行', '621787': '广发银行', '622556': '广发银行',
  '622557': '广发银行', '622558': '广发银行',
  // 北京银行
  '621030': '北京银行', '622163': '北京银行', '622850': '北京银行',
  // 上海银行
  '622892': '上海银行', '621788': '上海银行', '622468': '上海银行',
  // 宁波银行
  '621281': '宁波银行', '622316': '宁波银行', '622318': '宁波银行',
  // 江苏银行
  '621519': '江苏银行', '622172': '江苏银行', '622873': '江苏银行',
  // 南京银行
  '621259': '南京银行', '622303': '南京银行', '622304': '南京银行',
  // 杭州银行
  '621319': '杭州银行', '622353': '杭州银行', '622354': '杭州银行',
}

const form = reactive({
  nickname: '',
  avatar: '',
  phone: '',
  real_name: '',
  id_card: '',
  bank_card: '',
  bank_name: '',
  bank_branch: ''
})

const saving = ref(false)
const bankDetected = ref(false)
let originalAvatar = ''

/** 加载用户资料 */
const loadProfile = async () => {
  if (!auth.isLoginValid()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 800)
    return
  }
  try {
    const res = await getProfile()
    const data = res.data
    if (data) {
      form.nickname = data.nickname || ''
      form.avatar = data.avatar || ''
      form.phone = data.phone || ''
      form.real_name = data.real_name || ''
      form.id_card = data.id_card || ''
      form.bank_card = data.bank_card || ''
      form.bank_name = data.bank_name || ''
      form.bank_branch = data.bank_branch || ''
      originalAvatar = data.avatar || ''
      if (form.bank_card && form.bank_name) {
        bankDetected.value = true
      }
    }
  } catch {
    uni.showToast({ title: '加载资料失败', icon: 'none' })
  }
}

/** 选择微信头像（chooseAvatar 回调） */
const onChooseAvatar = (e: any) => {
  const avatarUrl = e?.detail?.avatarUrl
  if (avatarUrl) {
    form.avatar = avatarUrl
  }
}

/** 头像加载失败 → 显示默认头像 */
const onAvatarError = () => {
  if (form.avatar && form.avatar !== '/static/avatar-default.png') {
    form.avatar = '/static/avatar-default.png'
  }
}

/** 银行卡号输入 → BIN 自动识别发卡银行 */
const onBankCardInput = (e: any) => {
  const cardNo = (e?.detail?.value || '').replace(/\s/g, '')
  form.bank_card = cardNo
  if (cardNo.length >= 6) {
    const bin = cardNo.substring(0, 6)
    const bankName = BIN_MAP[bin]
    if (bankName) {
      form.bank_name = bankName
      bankDetected.value = true
    } else {
      bankDetected.value = false
    }
  } else {
    bankDetected.value = false
  }
}

/** 微信手机号授权回调 */
const onGetPhoneNumber = async (e: any) => {
  // 旧版基础库直接返回明文手机号
  if (e?.detail?.phoneNumber) {
    form.phone = e.detail.phoneNumber
    uni.showToast({ title: '手机号已填入', icon: 'success' })
    return
  }
  // 新版基础库返回 code，需后端调用微信接口换手机号
  const code = e?.detail?.code
  if (!code) {
    uni.showToast({ title: '授权失败，请手动输入', icon: 'none' })
    return
  }
  try {
    uni.showLoading({ title: '获取手机号...' })
    const res = await getPhoneByCode(code)
    if (res.data?.phone) {
      form.phone = res.data.phone
      uni.showToast({ title: '手机号已填入', icon: 'success' })
    } else {
      uni.showToast({ title: '获取失败，请手动输入', icon: 'none' })
    }
  } catch {
    uni.showToast({ title: '获取失败，请手动输入', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

/** 保存资料 */
const handleSave = async () => {
  if (saving.value) return

  // 基础校验
  if (!form.nickname.trim()) {
    uni.showToast({ title: '请输入昵称', icon: 'none' })
    return
  }
  if (form.phone && !/^1[3-9]\d{9}$/.test(form.phone)) {
    uni.showToast({ title: '手机号格式不正确', icon: 'none' })
    return
  }
  if (form.id_card && !/^\d{17}[\dXx]$/.test(form.id_card)) {
    uni.showToast({ title: '身份证号格式不正确', icon: 'none' })
    return
  }

  saving.value = true
  try {
    const body: Record<string, string> = {
      nickname: form.nickname.trim(),
      phone: form.phone.trim(),
      real_name: form.real_name.trim(),
      id_card: form.id_card.trim(),
      bank_card: form.bank_card.trim(),
      bank_name: form.bank_name.trim(),
      bank_branch: form.bank_branch.trim()
    }
    // 头像变更时才传（临时路径）
    if (form.avatar && form.avatar !== originalAvatar) {
      body.avatar = form.avatar
    }

    const res = await updateProfile(body)
    if (res.data) {
      // 更新本地缓存的用户信息
      const stored = auth.getStoredUserInfo()
      if (stored) {
        stored.nickname = form.nickname.trim()
        if (form.avatar) stored.avatar = form.avatar
        uni.setStorageSync('userInfo', JSON.stringify(stored))
      }
      uni.showToast({ title: '保存成功', icon: 'success' })
      setTimeout(() => uni.navigateBack(), 800)
    }
  } catch {
    uni.showToast({ title: '保存失败，请重试', icon: 'none' })
  } finally {
    saving.value = false
  }
}

/** 返回 */
const handleBack = () => {
  uni.navigateBack()
}

onMounted(() => {
  loadProfile()
})
</script>

<style lang="scss" scoped>
.profile-page {
  min-height: 100vh;
  background: #f2f3f5;
}

/* ── 顶部导航 ── */
.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 88rpx;
  padding: 0 24rpx;
  background: #ffd400;
}

.nav-back {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-back-icon {
  font-size: 48rpx;
  color: #1a1a1a;
  font-weight: 300;
  line-height: 1;
}

.nav-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #1a1a1a;
}

.nav-placeholder {
  width: 64rpx;
}

/* ── 头像区域 ── */
.avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48rpx 0 36rpx;
  background: #ffd400;
}

.avatar-btn {
  position: relative;
  width: 160rpx;
  height: 160rpx;
  padding: 0;
  margin: 0;
  border: none;
  background: transparent;
  border-radius: 50%;
  overflow: hidden;
  line-height: normal;
}

.avatar-btn::after {
  border: none;
}

.avatar-img {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  background: #fff;
  border: 4rpx solid #1a1a1a;
  box-sizing: border-box;
}

.avatar-mask {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 48rpx;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-mask-text {
  font-size: 20rpx;
  color: #fff;
}

.avatar-tip {
  margin-top: 16rpx;
  font-size: 24rpx;
  color: rgba(26, 26, 26, 0.6);
}

/* ── 表单卡片 ── */
.form-card {
  margin: 24rpx 28rpx 0;
  background: #fff;
  border-radius: 24rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.04);
}

.card-title {
  display: flex;
  align-items: baseline;
  gap: 16rpx;
  padding: 28rpx 30rpx 0;
}

.card-title-text {
  font-size: 30rpx;
  font-weight: 600;
  color: #1a1a1a;
}

.card-title-desc {
  font-size: 22rpx;
  color: #999;
}

.form-item {
  display: flex;
  align-items: center;
  padding: 28rpx 30rpx;
  min-height: 88rpx;
}

.form-label {
  width: 160rpx;
  font-size: 28rpx;
  color: #1a1a1a;
  flex-shrink: 0;
}

.form-input {
  flex: 1;
  font-size: 28rpx;
  color: #1a1a1a;
  text-align: right;
}

.input-placeholder {
  color: #bbb;
  font-size: 28rpx;
}

.form-divider {
  height: 1rpx;
  background: #f4f4f4;
  margin-left: 30rpx;
}

.bank-tag {
  margin-left: 12rpx;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: #fff0b0;
  color: #1a1a1a;
  font-size: 20rpx;
  flex-shrink: 0;
}

.phone-auth-btn {
  margin-left: 16rpx;
  padding: 0 20rpx;
  height: 52rpx;
  line-height: 52rpx;
  border-radius: 999rpx;
  background: #1a1a1a;
  color: #ffd400;
  font-size: 22rpx;
  flex-shrink: 0;
}

.phone-auth-btn::after {
  border: none;
}

/* ── 保存按钮 ── */
.save-section {
  margin: 48rpx 28rpx 0;
}

.save-btn {
  height: 88rpx;
  border-radius: 999rpx;
  background: #1a1a1a;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6rpx 16rpx rgba(0, 0, 0, 0.14);

  &.disabled {
    opacity: 0.6;
  }

  &:active {
    opacity: 0.85;
  }
}

.save-btn-text {
  font-size: 30rpx;
  color: #ffd400;
  font-weight: 600;
}

.bottom-space {
  height: 60rpx;
}
</style>
