#!/usr/bin/env python3
# @ai-generated
# S04 生产环境全面验证脚本
import json
import urllib.request
import urllib.parse
import sys

BASE = "http://localhost:3003"
PASS = 0
FAIL = 0
WARN = 0


def ok(msg):
    global PASS
    print("[PASS] " + msg)
    PASS += 1


def fail(msg, detail=""):
    global FAIL
    print("[FAIL] " + msg + ": " + str(detail))
    FAIL += 1


def warn(msg, detail=""):
    global WARN
    print("[WARN] " + msg + ": " + str(detail))
    WARN += 1


def api(method, path, token=None, body=None, headers=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = "Bearer " + token
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


print("=" * 60)
print("S04 生产环境全面验证")
print("=" * 60)

# 1. 基础健康检查
print("\n--- 1. 基础健康检查 ---")
code, data = api("GET", "/healthz")
if code == 200 and data.get("status") == "ok":
    ok("/healthz")
else:
    fail("/healthz", str(data))

code, data = api("GET", "/readyz")
checks = data.get("checks", {})
mysql_ok = checks.get("mysql", {}).get("status") == "connected"
redis_ok = checks.get("redis", {}).get("status") == "connected"
obs_ok = checks.get("obs", {}).get("status") == "connected"
if mysql_ok:
    ok("MySQL 连接正常")
else:
    fail("MySQL 连接", str(checks.get("mysql", {})))
if redis_ok:
    ok("Redis 连接正常")
else:
    fail("Redis 连接", str(checks.get("redis", {})))
if obs_ok:
    ok("OBS 连接正常")
else:
    warn("OBS 连接", str(checks.get("obs", {})))

# 2. 管理员登录与权限
print("\n--- 2. 管理员登录与权限 ---")
code, data = api("POST", "/api/v1/admin/auth/login",
                 body={"username": "admin", "password": "admin@12345"})
TOKEN = data.get("data", {}).get("token", "") if isinstance(data.get("data"), dict) else ""
if TOKEN:
    ok("管理员登录成功")
else:
    fail("管理员登录", str(data))
    sys.exit(1)

code, data = api("GET", "/api/v1/admin/auth/me", token=TOKEN)
me = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
uname = me.get("username", "")
rname = me.get("role_name", "")
perms = me.get("permissions", [])
if uname == "admin":
    ok("Token校验 user=" + uname + " role=" + str(rname))
else:
    fail("Token校验", str(data))

if perms and "*" in perms:
    ok("超级管理员权限完整")
else:
    fail("超级管理员权限", str(perms))

# 3. F04 渠道配置
print("\n--- 3. F04 渠道配置 ---")
code, data = api("GET", "/api/v1/admin/channel/list", token=TOKEN)
ch_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
ch_total = ch_data.get("total", 0)
if ch_total >= 1:
    ok("渠道列表正常 (" + str(ch_total) + "条)")
else:
    fail("渠道列表", "empty")

code, data = api("GET", "/api/v1/admin/channel/myq", token=TOKEN)
ch = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
ch_code = ch.get("channel_code", "")
ch_status = ch.get("status", "")
if ch_code == "myq":
    ok("喵有券参数读取成功 status=" + str(ch_status))
else:
    fail("喵有券渠道", str(data))

# 4. 商品搜索（CPS渠道验证）
print("\n--- 4. 商品搜索（CPS渠道验证）---")
keyword = urllib.parse.quote("手机")
code, data = api("GET",
                 "/api/public/goods/search?keyword=" + keyword + "&page=1&size=5&channel_code=myq",
                 headers={"X-User-Id": "1"})
items = []
resp_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
items = resp_data.get("items", [])
if code == 200:
    ok("商品搜索接口正常 (返回" + str(len(items)) + "条)")
    if len(items) == 0:
        warn("商品搜索返回0条（可能是关键词无结果或渠道限流）")
else:
    fail("商品搜索", "code=" + str(code))

# 5. C端接口可达性
print("\n--- 5. C端接口可达性 ---")
code, data = api("POST", "/api/v1/user/auth/wx-login", body={"code": "test_code"})
if code != 404:
    ok("微信登录接口可达 (HTTP " + str(code) + ")")
else:
    fail("微信登录接口", "404 Not Found")

code, _ = api("GET", "/api/v1/withdraw/account")
if code == 401:
    ok("佣金账户接口正常 (401未授权，预期行为)")
elif code != 404:
    ok("佣金账户接口可达 (HTTP " + str(code) + ")")
else:
    fail("佣金账户接口", "404 Not Found")

code, _ = api("GET", "/api/v1/cps/order?page=1&size=5")
if code == 401:
    ok("订单列表接口正常 (401未授权，预期行为)")
elif code != 404:
    ok("订单列表接口可达 (HTTP " + str(code) + ")")
else:
    fail("订单列表接口", "404 Not Found")

# 6. RBAC 权限隔离
print("\n--- 6. RBAC 权限隔离 ---")
code, _ = api("GET", "/api/v1/admin/channel/list")
if code == 401:
    ok("无Token访问后台接口被拒 (401)")
else:
    fail("RBAC隔离失败", "code=" + str(code))

code, _ = api("GET", "/api/v1/admin/dashboard/cards")
if code == 401:
    ok("仪表盘无Token被拒 (401)")
else:
    fail("仪表盘RBAC", "code=" + str(code))

# 7. 埋点接口
print("\n--- 7. 埋点接口 ---")
code, data = api("POST", "/api/v1/track/event",
                 body={"events": [{"event_type": "page_view", "event_data": {"page": "test"},
                                   "timestamp": 1234567890}]})
if code == 200:
    ok("埋点接口正常")
else:
    fail("埋点接口", "code=" + str(code))

# 8. 管理后台核心功能
print("\n--- 8. 管理后台核心功能 ---")
code, data = api("GET", "/api/v1/admin/dashboard/cards", token=TOKEN)
if code == 200:
    ok("仪表盘数据读取正常")
else:
    fail("仪表盘", "code=" + str(code))

code, data = api("GET", "/api/v1/admin/audit/logs?page=1&page_size=5", token=TOKEN)
audit_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
audit_total = audit_data.get("total", 0)
if code == 200:
    ok("审计日志正常 (" + str(audit_total) + "条)")
else:
    fail("审计日志", "code=" + str(code))

code, data = api("GET", "/api/v1/admin/commission-settlement/orders?page=1&page_size=3", token=TOKEN)
order_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
order_total = order_data.get("total", 0)
if code == 200:
    ok("订单管理正常 (" + str(order_total) + "条)")
else:
    fail("订单管理", "code=" + str(code))

code, data = api("GET", "/api/v1/admin/users-manage?page=1&page_size=3", token=TOKEN)
user_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
user_total = user_data.get("total", 0)
if code == 200:
    ok("用户管理正常 (" + str(user_total) + "条)")
else:
    fail("用户管理", "code=" + str(code))

code, data = api("GET", "/api/v1/admin/withdraw/applies?page=1&page_size=3", token=TOKEN)
if code == 200:
    ok("提现审核接口正常")
else:
    fail("提现审核", "code=" + str(code))

code, data = api("GET", "/api/v1/admin/goods?page=1&page_size=3", token=TOKEN)
if code == 200:
    ok("商品管理接口正常")
else:
    fail("商品管理", "code=" + str(code))

# 9. 监控指标
print("\n--- 9. 监控指标 ---")
code, _ = api("GET", "/metrics")
if code == 200:
    ok("Prometheus 监控指标正常")
else:
    warn("监控指标", "code=" + str(code))

# 汇总
print("\n" + "=" * 60)
print("S04 生产环境验证结果")
print("=" * 60)
print("通过: " + str(PASS))
print("失败: " + str(FAIL))
print("警告: " + str(WARN))
print("=" * 60)

if FAIL == 0:
    print("✅ 全部核心检查通过！生产环境部署验证成功。")
    sys.exit(0)
else:
    print("❌ 存在失败项，请检查后重试。")
    sys.exit(1)
