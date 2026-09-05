<!-- @ai-generated -->
<script setup lang="ts">
import { onLaunch, onShow, onHide } from '@dcloudio/uni-app'
import auth from '@/utils/auth'
import tracker from '@/utils/tracker'
import errorReporter from '@/utils/errorReporter'

onLaunch(() => {
  console.log('[App] Launch 金角大王CPS返利小程序')

  // 初始化错误捕获系统（JS异常 + Promise拒绝 + 接口报错）
  errorReporter.init()

  // 初始化行为埋点系统（防抖合并 + 本地缓存 + 断网重传）
  tracker.init()

  // 同步 sessionId，确保行为事件和错误事件属于同一会话
  errorReporter.setSessionId(tracker.getSessionId())

  // 启动时校验本地登录态：token 有效则启动定时检测，过期则清除
  auth.verifyTokenOnStartup().then((valid) => {
    if (valid) {
      console.log('[App] 登录态有效，已启动 token 过期检测')
    } else {
      console.log('[App] 未登录或登录态已过期')
    }
  }).catch((err) => {
    console.warn('[App] 启动登录态校验异常:', err)
  })
})

onShow(() => {
  console.log('[App] Show')
})

onHide(() => {
  console.log('[App] Hide')
  // App 进入后台时 flush 一次埋点，确保数据不丢失
  tracker.destroy()
  errorReporter.destroy()
})
</script>

<style lang="scss">
@import './styles/global.scss';
</style>
