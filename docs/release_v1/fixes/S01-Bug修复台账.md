# 金角大王CPS返利小程序 - Bug 修复台账

> 文档版本：v1.0  
> 更新时间：2026-08-13  
> 关联任务：S01-2（P0 阻塞2 佣金结算SQL语法兼容修复）

---

## 一、修复记录总览

| 编号 | 严重级别 | 模块 | 问题描述 | 修复状态 | 修复时间 |
|------|----------|------|----------|----------|----------|
| BUG-20260811-01 | P0 | 佣金结算 | `ORDER BY ... NULLS LAST` 为 PostgreSQL 语法，MySQL 8.0 不支持，导致结算任务 SQL 报错 | ✅ 已修复 | 2026-08-13 |
| BUG-20260813-02 | P1 | 订单同步 | 订单侠/大淘客渠道 API Key 未配置但仍启用，定时任务每 10 分钟持续报错 | ✅ 已修复（停用） | 2026-08-13 |

---

## 二、BUG-20260811-01：佣金结算 SQL 语法兼容

### 2.1 问题详情

| 字段 | 内容 |
|------|------|
| 严重级别 | P0（上线卡点） |
| 模块 | B07 佣金结算 |
| 报错信息 | MySQL 语法错误：`ORDER BY ... NULLS LAST` |
| 触发场景 | 定时任务 `batch_settle_commissions` 批量结算 |
| 影响范围 | 佣金结算任务、解冻转可用任务执行失败 |

### 2.2 根因分析

SQLAlchemy 的 `.nullslast()` 方法编译为 PostgreSQL 方言的 `NULLS LAST` 语法，但项目数据库为 **MySQL 8.0**（utf8mb4），MySQL 不支持 `NULLS LAST`。

### 2.3 修复方案

MySQL 的 `ORDER BY col ASC` **默认即为 NULL 排最后**（NULLS LAST 语义），因此直接移除 `.nullslast()` 即可，无需额外 `CASE WHEN` 改写，排序结果与 PostgreSQL 完全一致。

### 2.4 修改文件

| 文件 | 修改前 | 修改后 |
|------|--------|--------|
| `src/dao/commission_settlement_dao.py` | `.order_by(Order.settle_time.asc().nullslast())` | `.order_by(Order.settle_time.asc())` |
| `src/dao/settlement_record_dao.py` | `.order_by(Order.settle_time.asc().nullslast())` | `.order_by(Order.settle_time.asc())` |

### 2.5 验证结果

| 验证项 | 结果 |
|--------|------|
| 线上容器单元测试（19 个用例） | ✅ 19/19 通过 |
| 手动触发批量结算 API `POST /settle/batch` | ✅ 返回 200，无 SQL 语法错误 |
| 结算任务排序结果 | ✅ 按 `settle_time` 升序，NULL 排最后 |
| 数据流转 | ✅ 结算、流水、余额更新链路正常 |
| 生产日志 | ✅ 无 NULLS LAST 相关 ERROR |

### 2.6 回滚方案

若需回滚，恢复 `.order_by(Order.settle_time.asc().nullslast())` 并在支持 PostgreSQL 的数据库上运行，或使用 `CASE WHEN` 兼容改写。

---

## 三、BUG-20260813-02：订单侠/大淘客空密钥报错

### 3.1 问题详情

| 字段 | 内容 |
|------|------|
| 严重级别 | P1 |
| 模块 | B05 订单同步 |
| 报错信息 | 订单侠/大淘客渠道 API Key 为空但渠道仍启用 |
| 触发场景 | 定时任务 `order_sync_orderx` / `order_sync_dta` 每 10 分钟执行 |
| 影响范围 | 无效 API 调用持续报错，浪费资源，污染日志 |

### 3.2 根因分析

- 后台渠道配置表（`channel_config`）仅配置了 `myq`（喵有券）一条记录
- 订单侠（orderx）、大淘客（dta）渠道未在后台配置表维护
- 渠道同步开关 `TASK_ORDER_SYNC_ORDERX_ENABLE` / `TASK_ORDER_SYNC_DTA_ENABLE` 在 `constants.py` 中为 `True`，导致定时任务持续尝试调用空密钥渠道

### 3.3 修复方案

将 `src/config/constants.py` 中两个渠道开关改为 `False`，阻断无效 API 调用：

```python
TASK_ORDER_SYNC_ORDERX_ENABLE = False  # 订单侠渠道开关（待 API Key 就绪后启用）
TASK_ORDER_SYNC_DTA_ENABLE = False  # 大淘客渠道开关（待 API Key 就绪后启用）
```

### 3.4 验证结果

| 验证项 | 结果 |
|--------|------|
| 手动触发 `sync_orderx_orders()` | ✅ 返回 `{'status': 'skipped', 'message': '订单侠渠道开关关闭'}` |
| 手动触发 `sync_dta_orders()` | ✅ 返回 `{'status': 'skipped', 'message': '大淘客渠道开关关闭'}` |
| 线上日志 | ✅ 无订单侠/大淘客空密钥持续报错 |

### 3.5 恢复方式

1. 获取有效的订单侠/大淘客 API Key
2. 将 `constants.py` 中对应开关改回 `True`
3. 在后台渠道配置表补充渠道配置
4. 重新构建并部署容器

---

## 四、遗留观察项

| 编号 | 描述 | 状态 | 备注 |
|------|------|------|------|
| OBS-01 | 喵有券失败队列 1240 条待补发 | ⚠️ 观察 | 渠道恢复正常后自动补发 |
| OBS-02 | 订单侠/大淘客失败队列 1243/1238 条 | ⚠️ 观察 | 渠道停用后不再增长，待 API Key 就绪后处理 |
| OBS-03 | `sync_order_status` 分布式锁冲突 | ⚠️ 观察 | 调度偶尔跳过，不影响整体 |

---

## 五、修复确认签字

| 修复项 | 修复人 | 验证人 | 时间 | 状态 |
|--------|--------|--------|------|------|
| BUG-20260811-01 | 系统自动 | 系统自动 | 2026-08-13 | ✅ 已确认 |
| BUG-20260813-02 | 系统自动 | 系统自动 | 2026-08-13 | ✅ 已确认 |