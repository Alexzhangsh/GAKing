<!-- @ai-generated -->
<!--
  富文本展示页面
  支持类型: user(用户协议与隐私政策), about(关于我们), help(购物流程帮助)
-->
<template>
  <view class="webview-container">
    <scroll-view scroll-y class="content-scroll">
      <view class="rich-content" v-html="htmlContent"></view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

const pageType = ref('user')

onLoad((query) => {
  pageType.value = (query?.type as string) || 'user'
  uni.setNavigationBarTitle({
    title: pageTitle.value
  })
})

const pageTitle = computed(() => {
  const map: Record<string, string> = {
    user: '用户协议与隐私政策',
    about: '关于我们',
    help: '购物流程帮助'
  }
  return map[pageType.value] || '详情'
})

const htmlContent = computed(() => {
  switch (pageType.value) {
    case 'user': return userAgreementHtml
    case 'about': return aboutHtml
    case 'help': return helpHtml
    default: return userAgreementHtml
  }
})

// 用户协议与隐私政策合并内容（与用户协议.md原文一致）
const userAgreementHtml = `
<div style="padding: 20rpx 30rpx; font-size: 28rpx; color: #333; line-height: 1.8;">
  <h2 style="font-size: 36rpx; text-align: center; margin-bottom: 30rpx;">金角大王-CPS优惠推广小程序</h2>
  <h3 style="font-size: 32rpx; margin: 30rpx 0 20rpx;">用户服务协议</h3>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">第一条 协议说明</h4>
  <p>1.1 本《用户服务协议》（下称"本协议"）是您和金角大王平台运营方之间，针对本微信小程序全部服务订立的有效合约。</p>
  <p>1.2 在您勾选同意、进入以及使用小程序各项功能时，即代表您已经完整阅读、理解并且接受本协议全部条款；如不同意协议内容，您无权使用本平台服务。</p>
  <p>1.3 平台有权随时修订用户协议、隐私政策，修改之后会于小程序内进行公示，公示之后继续使用小程序视作接受更新后的条款。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">第二条 服务介绍</h4>
  <p>2.1 本小程序属于商品优惠信息分发工具，主要功能为展示电商平台优惠商品、分享商品链接、查看推广佣金收益、订单记录、提现管理等CPS推广配套服务。</p>
  <p>2.2 平台仅作为第三方商品信息展示、分享中介，所有商品货源、发货、售后、退换货、商品质量问题均归属对应电商商家，平台不实际售卖实物商品。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">第三条 用户账号规则</h4>
  <p>3.1 用户授权微信信息即可登录平台，微信昵称、头像作为账号基础标识；用户应当妥善保管微信账号安全，因微信账号泄露带来的损失由用户自行承担。</p>
  <p>3.2 用户仅限开展合法合规的商品分享推广；禁止利用本小程序从事刷单、虚假下单、恶意薅取佣金、传销引流、发布违规内容、侵权推广等违规行为。</p>
  <p>3.3 如用户出现违规行为，平台有权执行账号警告、功能限制、冻结佣金、封禁账号等处置。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">第四条 佣金与提现约定</h4>
  <p>4.1 推广佣金来源于淘宝等第三方电商商家设置的推广酬劳，上游渠道会进行服务费扣除，小程序展示佣金仅作为预估金额，实际到手佣金以第三方渠道结算数据为准。</p>
  <p>4.2 订单发生退款、部分退款、售后关闭、虚假订单时，对应佣金将会被逆向扣回；已经提现成功的佣金，平台保留追回、从后续佣金抵扣的权利。</p>
  <p>4.3 用户满足平台提现门槛之后可申请余额提现，提现会产生渠道手续费，手续费规则以平台后台配置为准。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">第五条 用户禁止行为</h4>
  <p>1. 禁止篡改、逆向解析、爬虫抓取平台接口、商品数据；</p>
  <p>2. 禁止使用脚本、外挂、模拟器批量刷取订单；</p>
  <p>3. 禁止将平台用于赌博、色情、虚假营销、违法信息传播；</p>
  <p>4. 禁止冒用他人信息进行账号操作。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">第六条 免责声明</h4>
  <p>6.1 商品价格、优惠券、佣金率由电商商家随时改动，平台不对优惠长期有效、预估佣金数额作出担保。</p>
  <p>6.2 用户经由链接跳转至第三方电商产生的所有交易纠纷，请直接和电商商家协商处理，平台仅提供信息展示，不承担商品售后责任。</p>
  <p>6.3 因微信服务器故障、上游接口宕机、运营商网络故障、政策调整等不可抗因素造成服务临时中断，平台无需承担用户收益损失。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">第七条 其他</h4>
  <p>7.1 本协议适用中华人民共和国法律，产生纠纷优先友好协商，协商不成向运营主体所在地人民法院提起诉讼。</p>

  <hr style="margin: 40rpx 0; border: none; border-top: 2rpx solid #e0e0e0;" />

  <h2 style="font-size: 36rpx; text-align: center; margin-bottom: 30rpx;">隐私政策</h2>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">一、总则</h4>
  <p>本隐私政策用于告知各位使用者我们收集、储存、使用、保管您个人信息的全部规则。使用小程序即代表您同意我们按照本政策获取和处理对应信息。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">二、收集哪些用户信息</h4>
  <p><strong>2.1 微信基础授权信息</strong></p>
  <p>登录时获取微信头像、微信昵称、open-id；该信息用来唯一识别账号、展示用户主页，不会主动对外公开用户隐私微信账号。</p>
  <p><strong>2.2 可选授权</strong></p>
  <p>- 相册：仅在您上传头像、截图素材的时候调取相册权限；</p>
  <p>- 剪贴板：读取剪贴板用来识别商品分享口令；</p>
  <p>- 不会强制索取手机通讯录、定位等非必要权限。</p>
  <p><strong>2.3 业务运行自动采集数据</strong></p>
  <p>我们记录您的浏览记录、点击的商品、分享记录、下单回调订单数据、IP地址、设备型号、小程序操作日志，用于统计、风控、排查异常刷单行为、优化商品推荐。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">三、信息的使用用途</h4>
  <p>1. 用于创建、登录、管理您的账号；</p>
  <p>2. 展示商品列表、记录您的推广订单以及佣金流水；</p>
  <p>3. 风控识别恶意用户、虚假订单、作弊行为，保障佣金体系安全；</p>
  <p>4. 推送渠道配置更新、佣金到账、订单状态变动的消息通知；</p>
  <p>5. 统计用户行为，优化商品推荐。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">四、信息共享</h4>
  <p>1. 不会出售、有偿出让您的个人信息；</p>
  <p>2. 订单数据需要和上游CPS渠道做订单回调同步，仅传输订单编号、openid标记，不对外传递隐私资料；</p>
  <p>3. 在公安、市场监管等国家机关依法要求时配合提供必要数据。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">五、数据存储与安全</h4>
  <p>1. 用户数据存放于合规云服务器，配置访问权限、加密存储；</p>
  <p>2. 员工严格管控后台访问权限，杜绝个人信息外泄；</p>
  <p>3. 如发生数据泄露事故，我们会第一时间采取补救并且通知受影响用户。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">六、用户权利</h4>
  <p>1. 用户随时可以拒绝非必要授权；</p>
  <p>2. 用户可以申请注销账号，账号注销之后我们会清理该用户缓存的业务数据；</p>
  <p>3. 你有权联系运营方查询本人储存的用户资料。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">七、Cookie 和缓存</h4>
  <p>小程序会使用本地缓存保存你的登录状态、浏览缓存，你随时可以清除小程序缓存。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">八、政策更新</h4>
  <p>隐私政策更新以后会在登录弹窗、系统消息进行公示，继续使用即代表同意新版隐私政策。</p>
</div>
`

// 关于我们内容
const aboutHtml = `
<div style="padding: 30rpx; font-size: 28rpx; color: #333; line-height: 1.8;">
  <h2 style="font-size: 36rpx; text-align: center; margin-bottom: 30rpx;">关于我们</h2>
  <p style="text-indent: 2em;">金角大王是一款专注于CPS优惠推广的微信小程序，致力于为用户提供便捷的电商商品搜索、优惠分享、佣金返利等服务。</p>
  <p style="text-indent: 2em;">我们与淘宝等主流电商平台合作，通过商品推广链接，让用户在购物的同时获得推广佣金返利。</p>
  <p style="margin-top: 20rpx;"><strong>当前版本：</strong>v1.0.0</p>
  <p><strong>联系邮箱：</strong>（待配置）</p>
  <p><strong>客服微信：</strong>（待配置）</p>
</div>
`

// 帮助内容
const helpHtml = `
<div style="padding: 30rpx; font-size: 28rpx; color: #333; line-height: 1.8;">
  <h2 style="font-size: 36rpx; text-align: center; margin-bottom: 30rpx;">购物流程帮助</h2>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">1. 如何获取优惠商品？</h4>
  <p>打开小程序首页，即可浏览热门推荐商品。您也可以使用顶部搜索框搜索想要购买的商品。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">2. 如何获得佣金返利？</h4>
  <p>点击商品进入详情页，通过"复制口令"或"去购买"按钮跳转至淘宝等电商平台下单，订单确认收货后，佣金会自动结算到您的账户。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">3. 如何查看佣金和订单？</h4>
  <p>在"我的"页面可以查看累计返利、可提现金额、我的订单等信息。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">4. 如何提现？</h4>
  <p>满足最低提现门槛后，在"我的"页面进入佣金管理，点击提现按钮即可申请提现。</p>

  <h4 style="font-size: 30rpx; margin: 20rpx 0 10rpx;">5. 佣金多久到账？</h4>
  <p>订单确认收货后，佣金会进入"待确认"状态，经过平台结算周期后变为"可提现"状态，具体以实际结算时间为准。</p>
</div>
`
</script>

<style lang="scss" scoped>
.webview-container {
  min-height: 100vh;
  background: #fff;
}

.content-scroll {
  height: 100vh;
  padding: 20rpx 0 60rpx;
}
</style>