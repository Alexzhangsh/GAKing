# M07-1 Sentry 全链路监控 - 自测记录

> 任务ID：M07-1 ｜ 优先级：P2 ｜ 自测时间：2026-08-14
> 覆盖：后端服务 / 后台管理前端 / 微信小程序 三层 Sentry 埋点

## 一、自测结论

| 项目 | 结果 |
|------|------|
| 后端 Sentry 单元测试 | ✅ 22/22 通过 |
| 后端全量测试回归 | ✅ 无 Sentry 相关回归（31 个失败均为既有问题） |
| 后台管理前端构建 | ✅ vue-tsc 类型检查 + vite build 通过 |
| 小程序 H5 构建 | ✅ 通过 |
| 小程序微信端构建 | ✅ 通过 |
| 后端服务运行 | ✅ 健康检查正常，Sentry 初始化无异常 |
| **整体结论** | ✅ **自测通过，可交付验收** |

## 二、后端自测明细

### 2.1 单元测试（tests/test_m07_sentry.py，22 用例）

| 测试类 | 覆盖点 | 结果 |
|--------|--------|------|
| `TestEnvConfigSentry` | DSN 默认空、采样率默认值、配置类型 | ✅ 3/3 |
| `TestSentryUtilDegrade` | DSN 为空时 8 个函数静默降级不抛异常 | ✅ 8/8 |
| `TestBeforeSendFilter` | 健康检查/healthz/readyz 过滤、渠道关闭过滤、锁冲突过滤、正常事件放行 | ✅ 9/9 |
| `TestSchedulerCaptureContext` | 定时任务异常捕获上下文（task_name/retry_count） | ✅ 2/2 |

### 2.2 功能验证

| 验证项 | 方法 | 结果 |
|--------|------|------|
| sentry_sdk 安装 | venv 导入验证 | ✅ 可导入 |
| init_sentry 空 DSN 降级 | 直接调用 | ✅ 静默跳过 |
| 上下文绑定函数 | set_user_context / set_channel_tag / capture_exception | ✅ 正常执行 |
| 服务启动 | uvicorn --reload 热重载 | ✅ 无 Sentry 相关报错 |
| 健康检查 | GET /healthz | ✅ `{"status":"ok"}` |

### 2.3 全量测试回归

```
31 failed, 1403 passed
```

31 个失败用例全部为**既有问题**，与 Sentry 改动无关，分布如下：
- `test_redis_client.py`（4 个）：Redis mock 连接问题
- `test_goods_cache.py`（11 个）：商品缓存 Redis 依赖
- `test_cps_goods_api.py` / `test_cps_integration.py`（11 个）：CPS 适配器/熔断
- `test_b13_withdraw_admin.py`（5 个）：提现管理列表

## 三、后台管理前端自测明细

### 3.1 构建验证

```
npm run build（vue-tsc && vite build）
✓ built in 4.58s
```

vue-tsc 类型检查通过，无 TypeScript 错误。

### 3.2 接入点验证

| 接入点 | 文件 | 验证方式 | 结果 |
|--------|------|----------|------|
| Sentry 初始化 | `src/main.ts` | 代码审查 + 构建 | ✅ |
| 接口异常上报 | `src/utils/request.ts` | 5xx/网络错误分支 | ✅ |
| 管理员上下文绑定 | `src/store/user.ts` | login/fetchUserInfo/clearAuthState | ✅ |
| 环境判定 | `src/utils/sentry.ts` | VITE_APP_ENV/MODE 逻辑 | ✅ |

## 四、小程序自测明细

### 4.1 构建验证

| 构建目标 | 命令 | 结果 |
|----------|------|------|
| H5 | `npm run build:h5` | ✅ DONE Build complete |
| 微信小程序 | `npm run build:mp-weixin` | ✅ DONE Build complete |

### 4.2 接入点验证

| 接入点 | 文件 | 验证方式 | 结果 |
|--------|------|----------|------|
| Sentry 初始化（App() 前） | `src/main.ts` | 代码审查 + 双端构建 | ✅ |
| Vue errorHandler 转交 | `src/main.ts` | 组件错误捕获 | ✅ |
| 接口异常上报 | `src/utils/request.ts` | 5xx/网络错误分支 | ✅ |
| 用户上下文绑定 | `src/utils/auth.ts` | _persistToken/verifyTokenOnStartup/_clearAuthStorage | ✅ |
| 双端条件编译 | `src/utils/sentry.ts` | H5→@sentry/browser，MP-WEIXIN→sentry-miniapp | ✅ |

## 五、环境与交付物

### 5.1 本地服务环境

| 服务 | 端口 | 状态 |
|------|------|------|
| 后端服务 | 3001 | ✅ 运行中（--reload） |
| 后台管理前端 | 8080 | ✅ 运行中 |

### 5.2 交付物清单

| 交付物 | 路径 |
|--------|------|
| 后端 Sentry 工具模块 | `backend/src/common/sentry_util.py` |
| 后端配置 | `backend/src/config/env_config.py` + 4 个 .env 文件 |
| 后端接入点 | `main.py` / `b14_exception_handlers.py` / `response_util.py` / `tasks.py` / `scheduler_jobs.py` / `b15_rbac_middleware.py` / `auth_util.py` |
| 后端单元测试 | `backend/tests/test_m07_sentry.py` |
| 后台管理 Sentry 模块 | `admin/src/utils/sentry.ts` |
| 后台管理接入点 | `admin/src/main.ts` / `request.ts` / `store/user.ts` |
| 后台管理配置 | `admin/.env.development` / `.env.production` / `.env.example` |
| 小程序 Sentry 模块 | `miniprogram/src/utils/sentry.ts` |
| 小程序接入点 | `miniprogram/src/main.ts` / `request.ts` / `auth.ts` |
| 小程序配置 | `miniprogram/.env.development` / `.env.production` / `.env.example` |
| 接入文档 | `docs/M07-1-Sentry全链路监控-接入文档.md` |

## 六、待验收事项

1. **真实 DSN 联调**：当前 DSN 为空（禁用态），需在 Sentry 控制台创建项目后填入真实 DSN 验证事件到达。
2. **小程序合法域名**：上线前需在微信小程序后台将 Sentry 上报域名加入 request 合法域名。
3. **Source Map 上传**（可选）：生产构建后上传 Source Map 还原压缩堆栈。
4. **告警规则**：建议在 Sentry 控制台按 `error.category` / `source` 标签配置告警规则。
