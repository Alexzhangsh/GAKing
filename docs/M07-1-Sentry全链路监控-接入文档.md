# M07-1 Sentry 全链路监控接入文档

> 任务ID：M07-1 ｜ 优先级：P2 ｜ 前置依赖：F04-2
> 覆盖范围：后端服务（FastAPI）＋ 后台管理前端（Vue3）＋ 微信小程序（uni-app）
> 交付时间：2026-08-14

## 一、接入总览

| 层级 | 技术栈 | SDK | 入口文件 | 环境变量 |
|------|--------|-----|----------|----------|
| 后端服务 | FastAPI + Python | `sentry-sdk>=2.0.0` | `src/common/sentry_util.py` | `SENTRY_DSN` |
| 后台管理 | Vue3 + Vite + Element Plus | `@sentry/vue@10.70.0` | `admin/src/utils/sentry.ts` | `VITE_SENTRY_DSN` |
| 微信小程序 | uni-app + Vue3 | `sentry-miniapp@1.18.1`（MP-WEIXIN）/ `@sentry/browser@10.70.0`（H5） | `miniprogram/src/utils/sentry.ts` | `VITE_SENTRY_DSN` |

> **DSN 为空即禁用**：三层均以 DSN 是否配置作为开关。未配置 DSN 时所有 Sentry 调用静默返回，不影响业务启动与运行。

## 二、后端接入（FastAPI）

### 2.1 依赖与配置

`requirements.txt` 新增：

```
sentry-sdk>=2.0.0
```

`src/config/env_config.py` 新增配置项（`_get_float` 解析浮点环境变量）：

```python
SENTRY_DSN: str = ""                 # DSN 为空则禁用
SENTRY_TRACES_SAMPLE_RATE: float = 0.1   # 性能采样率
SENTRY_ERROR_SAMPLE_RATE: float = 1.0    # 异常采样率
```

各环境文件（`.env.development` / `.env.test` / `.env.production` / `.env.example`）新增：

```
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ERROR_SAMPLE_RATE=1.0
```

### 2.2 核心工具模块 `src/common/sentry_util.py`

| 函数 | 作用 |
|------|------|
| `init_sentry()` | 初始化 SDK，绑定环境标签、采样率、httpx/logging 集成 |
| `before_send_handler()` | 事件发送前过滤：健康检查路径、渠道关闭跳过、锁冲突 |
| `before_send_transaction_handler()` | 事务过滤：`/healthz` `/readyz` `/health` 不产生 traces |
| `set_user_context()` | 绑定用户上下文（user_id / username / role_id） |
| `set_request_context()` | 绑定请求上下文（request_id / path / method） |
| `set_channel_tag()` | 绑定渠道标签（channel_code） |
| `capture_exception()` | 手动捕获被 try/except 吞掉的异常（定时任务） |
| `capture_message()` | 手动上报业务消息 |
| `clear_user_context()` | 清除用户上下文 |

### 2.3 接入点清单

| 文件 | 接入点 | 说明 |
|------|--------|------|
| `src/main.py` | lifespan 启动时 `init_sentry()` | 优先于中间件/路由注册 |
| `src/main.py` | HTTP 中间件 `set_request_context()` | 绑定 request_id/path/method |
| `src/main.py` | 中间件 except 分支 `capture_exception()` | 未捕获异常上报 |
| `src/main.py` | 全局异常处理器 `capture_exception()` | 兜底 500 上报 |
| `src/common/b14_exception_handlers.py` | HTTPException 5xx `capture_exception()` | 仅上报 5xx，4xx 为预期业务/鉴权错误 |
| `src/api/v1/response_util.py` | 服务层 500 `capture_exception()` | 非 HTTP/ValueError 异常上报 |
| `src/scheduler/tasks.py` | 重试循环 except `capture_exception()` | 定时任务异常（含 task_name/retry_count） |
| `src/scheduler/scheduler_jobs.py` | `_run_with_lock` except `capture_exception()` | 定时任务异常（含 task_name） |
| `src/common/b15_rbac_middleware.py` | 认证通过后 `set_user_context()` | 管理员上下文 |
| `src/common/auth_util.py` | `get_current_user` 依赖 `set_user_context()` | C 端用户上下文 |

### 2.4 后端过滤规则（before_send）

| 规则 | 说明 |
|------|------|
| URL 含 `/health` | 健康检查不产生事件（含 `/healthz` `/readyz`） |
| 异常含「渠道开关关闭，跳过执行」 | 定时任务正常跳过状态 |
| 异常含「未获取到分布式锁」 | 定时任务锁冲突正常状态 |

## 三、后台管理前端接入（Vue3）

### 3.1 依赖与配置

```
npm install @sentry/vue
```

`admin/.env.development` / `.env.production` / `.env.example` 新增：

```
VITE_SENTRY_DSN=
VITE_SENTRY_ERROR_SAMPLE_RATE=1.0
VITE_SENTRY_TRACES_SAMPLE_RATE=0.1
VITE_APP_ENV=development|production
VITE_APP_VERSION=1.0.0
```

### 3.2 核心工具模块 `admin/src/utils/sentry.ts`

| 函数 | 作用 |
|------|------|
| `getEnv()` | 环境判定：`VITE_APP_ENV` 优先，其次 `MODE` |
| `initSentry(app)` | 初始化 `@sentry/vue`，绑定 app.layer=admin、采样率 |
| `beforeSendHandler()` | 过滤登录失效、权限不足等预期告警 |
| `setAdminUserContext()` | 绑定管理员上下文（user_id/username/role_id/role_name/real_name） |
| `clearUserContext()` | 登出清除 |
| `captureException()` / `captureMessage()` | 手动上报 |
| `reportApiError()` | 接口异常上报（仅 5xx/网络错误，4xx 过滤） |

### 3.3 接入点清单

| 文件 | 接入点 | 说明 |
|------|--------|------|
| `admin/src/main.ts` | `initSentry(app)` | app 创建后立即初始化 |
| `admin/src/utils/request.ts` | 响应拦截器 `reportApiError()` | 5xx 服务端异常 + 网络错误上报 |
| `admin/src/store/user.ts` | login/fetchUserInfo `setAdminUserContext()` | 登录/刷新绑定管理员上下文 |
| `admin/src/store/user.ts` | clearAuthState `clearUserContext()` | 登出清除上下文 |

### 3.4 前端自动捕获能力（SDK 内置）

- Vue 组件错误（render / 生命周期 / watch / 事件处理器）
- 全局 JS 运行时异常（window.onerror）
- 未处理的 Promise 拒绝（unhandledrejection）
- 资源加载失败

## 四、微信小程序接入（uni-app）

### 4.1 依赖与配置

```
npm install sentry-miniapp @sentry/browser
```

> `sentry-miniapp` 为社区维护 SDK（基于 `@sentry/core`），已被 Sentry 官方文档收录为 community-supported SDK。官方 `@sentry/wx` 已从 npm 下架。

`miniprogram/.env.development` / `.env.production` / `.env.example` 新增：

```
VITE_SENTRY_DSN=
VITE_SENTRY_ERROR_SAMPLE_RATE=1.0
VITE_SENTRY_TRACES_SAMPLE_RATE=0.1
VITE_APP_VERSION=1.0.0
```

### 4.2 核心工具模块 `miniprogram/src/utils/sentry.ts`

双端条件编译适配：

```ts
// #ifdef H5
import * as Sentry from '@sentry/browser'
// #endif
// #ifdef MP-WEIXIN
import * as Sentry from 'sentry-miniapp'
// #endif
```

| 函数 | 作用 |
|------|------|
| `getEnv()` | 环境判定：`process.env.NODE_ENV` |
| `initSentry()` | 初始化 SDK，绑定 app.layer=miniapp、采样率 |
| `beforeSendHandler()` | 过滤登录失效、权限不足、用户取消授权 |
| `setUserContext()` | 绑定用户上下文（user_id/nickname） |
| `clearUserContext()` | 退出登录清除 |
| `captureException()` / `captureMessage()` | 手动上报 |
| `reportApiError()` | 接口异常上报（仅 5xx/网络错误） |

### 4.3 接入点清单

| 文件 | 接入点 | 说明 |
|------|--------|------|
| `miniprogram/src/main.ts` | `initSentry()` + `app.config.errorHandler` | 尽早初始化 + Vue 组件错误转交 Sentry |
| `miniprogram/src/utils/request.ts` | `reportApiError()` | 接口异常同步上报 Sentry |
| `miniprogram/src/utils/auth.ts` | `_persistToken`/`verifyTokenOnStartup` `setUserContext()` | 登录/启动校验绑定用户上下文 |
| `miniprogram/src/utils/auth.ts` | `_clearAuthStorage` `clearUserContext()` | 退出登录清除 |

### 4.4 小程序自动捕获能力（SDK 内置）

- 全局 JS 运行时异常（wx.onError）
- 未处理的 Promise 拒绝（wx.onUnhandledRejection）
- 页面异常、内存告警
- 网络请求面包屑（url/method/状态码/耗时）

## 五、错误分类标签规范

| 标签 | 取值 | 说明 |
|------|------|------|
| `environment` | development / test / production | 环境标签（SDK 自动） |
| `app.layer` | backend / admin / miniapp | 应用层级 |
| `app.framework` | fastapi / vue3 / uni-app | 技术栈 |
| `source` | middleware / global_handler / http_exception / service / scheduler | 异常来源 |
| `task_name` | 定时任务名 | 定时任务上下文 |
| `retry_count` | 重试次数 | 定时任务重试上下文 |
| `channel_code` | myq / orderx 等 | 渠道标签 |
| `request_id` | req_xxx | 链路追踪 |
| `api.url` / `api.method` / `api.status` | 接口信息 | 前端接口异常 |
| `error.category` | api_server_error / api_network_error | 错误分类 |

## 六、采样率与降噪配置

| 环境 | 异常采样率 | 性能采样率 | 说明 |
|------|-----------|-----------|------|
| 开发 | 1.0 | 0.1 | 全量捕获便于调试 |
| 测试 | 1.0 | 0.1 | 全量捕获 |
| 生产 | 1.0 | 0.1 | 异常全量，性能抽样 |

已知无害告警过滤（before_send）：
- 后端：健康检查、渠道关闭跳过、分布式锁冲突
- 后台管理：登录失效、权限不足
- 小程序：登录失效、权限不足、用户取消授权

## 七、上线前配置步骤

1. **创建 Sentry 项目**：在 Sentry 控制台创建 3 个项目（backend / admin / miniapp），复制各项目 DSN。
2. **后端**：将 DSN 填入 `.env.production` 的 `SENTRY_DSN`，重启服务。
3. **后台管理**：将 DSN 填入 `admin/.env.production` 的 `VITE_SENTRY_DSN`，重新构建部署。
4. **小程序**：将 DSN 填入 `miniprogram/.env.production` 的 `VITE_SENTRY_DSN`，重新构建；**在微信小程序后台将 Sentry 上报域名加入 request 合法域名**。
5. **验证**：调用 `Sentry.captureException(new Error('test'))` 或后端 `capture_exception` 主动发一条测试事件，在 Sentry Issues 确认到达。
6. **Source Map**（可选）：小程序/前端构建后上传 Source Map，还原压缩代码堆栈。

## 八、注意事项

- 所有 Sentry 调用均有 DSN 空值保护，未配置 DSN 时零开销、零异常。
- 后端 `send_default_pii=False`，用户信息通过 `set_user_context` 显式绑定，避免自动采集敏感数据。
- 前端 `sendDefaultPii: false`，仅绑定业务所需的 user_id/username/role_id。
- 小程序 `sentry-miniapp` 需在 `App()` 之前初始化（main.ts 顶部），否则启动阶段异常无法捕获。
- 上报失败时 `sentry-miniapp` 自动进入本地离线队列，网络恢复后重试。
