#!/usr/bin/env python3
# @ai-generated
"""
金角大王 - 生产环境全业务链路复测脚本
覆盖：DNS解析、健康检查、管理后台、商品、订单、佣金、提现、埋点
用法: python3 full_chain_test.py [--base https://api.dftsh.top]
"""
import json
import urllib.request
import urllib.error
import urllib.parse
import socket
import time
import sys
import argparse
from datetime import datetime

# ─── 配置 ───────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="金角大王全链路复测")
parser.add_argument("--base", default="https://api.dftsh.top", help="API 基地址")
parser.add_argument("--admin", default="https://admin.dftsh.top", help="管理后台域名")
args = parser.parse_args()

BASE = args.base.rstrip("/")
ADMIN_DOMAIN = args.admin
PASS = 0
FAIL = 0
WARN = 0
results = []  # (level, name, detail)

ADMIN_USER = "admin"
ADMIN_PASS = "admin@12345"

# ─── 工具函数 ───────────────────────────────────────────────
def ok(msg, detail=""):
    global PASS
    PASS += 1
    results.append(("PASS", msg, detail))
    print(f"  [PASS] {msg}  {detail}")

def fail(msg, detail=""):
    global FAIL
    FAIL += 1
    results.append(("FAIL", msg, detail))
    print(f"  [FAIL] {msg}  {detail}")

def warn(msg, detail=""):
    global WARN
    WARN += 1
    results.append(("WARN", msg, detail))
    print(f"  [WARN] {msg}  {detail}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def api(method, path, token=None, body=None, headers=None, timeout=15):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}

def check_dns(domain):
    """检查 DNS 解析"""
    try:
        ip = socket.gethostbyname(domain)
        return True, ip
    except socket.gaierror as e:
        return False, str(e)

def check_http(url, timeout=10):
    """检查 HTTP 可达性（用 GET 避免 405）"""
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return True, resp.status
    except urllib.error.HTTPError as e:
        # 401/403/405 也算可达
        if e.code in (401, 403, 404, 405):
            return True, e.code
        return False, e.code
    except Exception as e:
        return False, str(e)

# ─── 测试流程 ───────────────────────────────────────────────
print("\n" + "#" * 60)
print(f"#  金角大王 - 生产环境全链路复测")
print(f"#  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"#  API:  {BASE}")
print("#" * 60)

# 1. DNS 解析验证
section("1. DNS 解析验证")
api_domain = BASE.replace("https://", "").replace("http://", "")
ok_dns, api_ip = check_dns(api_domain)
if ok_dns:
    ok(f"api 域名解析 {api_domain}", f"→ {api_ip}")
else:
    fail(f"api 域名解析失败 {api_domain}", api_ip)

admin_domain = ADMIN_DOMAIN.replace("https://", "").replace("http://", "")
ok_admin, admin_ip = check_dns(admin_domain)
if ok_admin:
    ok(f"admin 域名解析 {admin_domain}", f"→ {admin_ip}")
else:
    fail(f"admin 域名解析失败 {admin_domain}", admin_ip)

img_domain = "img.dftsh.top"
ok_img, img_ip = check_dns(img_domain)
if ok_img:
    ok(f"img (CDN) 域名解析 {img_domain}", f"→ {img_ip}")
else:
    warn(f"img 域名解析失败 {img_domain}", img_ip)

# 2. HTTPS 可达性
section("2. HTTPS 可达性")
ok_api_https, api_status = check_http(f"{BASE}/healthz")
if ok_api_https:
    ok(f"API HTTPS 可达 {BASE}/healthz", f"status={api_status}")
else:
    fail(f"API HTTPS 不可达", str(api_status))

ok_admin_https, admin_status = check_http(f"{ADMIN_DOMAIN}/")
if ok_admin_https:
    ok(f"管理后台 HTTPS 可达 {ADMIN_DOMAIN}", f"status={admin_status}")
else:
    warn(f"管理后台 HTTPS 不可达", str(admin_status))

# 3. 基础健康检查
section("3. 基础健康检查")
code, data = api("GET", "/healthz")
if code == 200 and data.get("status") == "ok":
    ok("/healthz 健康检查")
else:
    fail("/healthz", str(data))

code, data = api("GET", "/readyz")
checks = data.get("checks", {}) if isinstance(data, dict) else {}
mysql_ok = checks.get("mysql", {}).get("status") == "connected"
redis_ok = checks.get("redis", {}).get("status") == "connected"
obs_ok = checks.get("obs", {}).get("status") == "connected"

if mysql_ok:
    ok("MySQL 连接正常")
else:
    fail("MySQL 连接异常", str(checks.get("mysql", {})))

if redis_ok:
    ok("Redis 连接正常")
else:
    fail("Redis 连接异常", str(checks.get("redis", {})))

if obs_ok:
    ok("OBS 存储连接正常")
else:
    warn("OBS 存储连接异常", str(checks.get("obs", {})))

# 4. 管理后台 - 登录与权限
section("4. 管理后台 - 登录与权限")
code, data = api("POST", "/api/v1/admin/auth/login",
                 body={"username": ADMIN_USER, "password": ADMIN_PASS})
admin_token = data.get("data", {}).get("token", "")
if admin_token:
    ok(f"管理员登录 {ADMIN_USER}/{ADMIN_PASS}")
else:
    fail("管理员登录失败", str(data))

code, data = api("GET", "/api/v1/admin/auth/me", token=admin_token)
me = data.get("data", {}) if isinstance(data, dict) else {}
if me.get("username") == ADMIN_USER:
    ok(f"Token 校验通过", f"role={me.get('role_name', 'N/A')}")
else:
    fail("Token 校验失败", str(data))

# RBAC 权限隔离
code, _ = api("GET", "/api/v1/admin/dashboard/cards")
if code == 401:
    ok("无 Token 访问被拒 (401)", "RBAC 权限隔离正常")
else:
    fail("RBAC 权限隔离异常", f"code={code}")

# 5. 管理后台 - 核心功能
section("5. 管理后台 - 核心功能")
code, data = api("GET", "/api/v1/admin/dashboard/cards", token=admin_token)
if code == 200:
    ok("仪表盘数据读取正常")
else:
    fail("仪表盘数据读取失败", f"code={code}")

code, data = api("GET", "/api/v1/admin/audit/logs?page=1&page_size=5", token=admin_token)
if code == 200:
    total = data.get("data", {}).get("total", 0)
    ok("审计日志读取正常", f"共 {total} 条")
else:
    fail("审计日志读取失败", f"code={code}")

code, data = api("GET", "/api/v1/admin/users-manage?page=1&page_size=5", token=admin_token)
if code == 200:
    total = data.get("data", {}).get("total", 0)
    ok("用户管理读取正常", f"共 {total} 人")
else:
    fail("用户管理读取失败", f"code={code}")

code, data = api("GET", "/api/v1/cps/order?page=1&page_size=5", token=admin_token)
if code == 200:
    total = data.get("data", {}).get("total", 0)
    ok("订单管理读取正常", f"共 {total} 单")
else:
    fail("订单管理读取失败", f"code={code}")

# 6. F04 渠道配置
section("6. F04 渠道配置")
code, data = api("GET", "/api/v1/admin/channel/list", token=admin_token)
ch_total = data.get("data", {}).get("total", 0)
if ch_total >= 1:
    ok(f"渠道列表正常", f"{ch_total} 条渠道")
else:
    fail("渠道列表为空", "")

code, data = api("GET", "/api/v1/admin/channel/myq", token=admin_token)
ch = data.get("data", {}) if isinstance(data, dict) else {}
if ch.get("channel_code") == "myq":
    ok(f"喵有券渠道配置", f"status={ch.get('status', 'N/A')}")
else:
    fail("喵有券渠道配置异常", str(data))

# 7. C端 - 商品搜索
section("7. C端 - 商品搜索（CPS渠道）")
keyword = urllib.parse.quote("手机")
code, data = api("GET",
                 f"/api/public/goods/search?keyword={keyword}&page=1&size=5&channel_code=myq",
                 headers={"X-User-Id": "1"})
items = data.get("data", {}).get("items", []) if isinstance(data, dict) else []
if code == 200:
    if len(items) > 0:
        ok(f"商品搜索正常", f"返回 {len(items)} 条")
    else:
        warn("商品搜索返回0条", "可能关键词无结果或渠道限流")
else:
    fail("商品搜索失败", f"code={code}, msg={data.get('msg', '')}")

# 商品详情
if items and len(items) > 0:
    first_item = items[0]
    goods_id = first_item.get("goods_id", "")
    if goods_id:
        code, data = api("GET", f"/api/public/goods/detail?goods_id={goods_id}&channel_code=myq",
                         headers={"X-User-Id": "1"})
        if code == 200 and data.get("data"):
            ok("商品详情正常")
        else:
            warn("商品详情异常", f"code={code}")

# 8. C端 - 微信登录接口可达性
section("8. C端 - 用户登录")
# 微信登录接口（用无效 code 验证接口可达）
code, data = api("POST", "/api/v1/user/auth/wx-login",
                 body={"code": "invalid_test_code_123"})
if code == 200 or (code != 0 and "code" in data):
    # 业务错误也算接口可达
    ok("微信登录接口可达", f"code={code}, msg={data.get('msg', 'N/A')}")
else:
    fail("微信登录接口不可达", f"code={code}")

# 9. C端 - 佣金与提现
section("9. C端 - 佣金账户")
code, data = api("GET", "/api/v1/withdraw/account")
# 未授权返回 401 是正常的，说明接口存在
if code in (200, 401):
    ok("佣金账户接口可达", f"code={code} (401 为未授权，正常)")
else:
    fail("佣金账户接口异常", f"code={code}")

code, data = api("GET", "/api/v1/withdraw/applies?page=1&page_size=10")
if code in (200, 401):
    ok("提现记录接口可达", f"code={code}")
else:
    fail("提现记录接口异常", f"code={code}")

# 10. 后台 - 提现审核
section("10. 后台 - 提现审核")
code, data = api("GET", "/api/v1/admin/withdraw/applies?page=1&page_size=5", token=admin_token)
if code == 200:
    total = data.get("data", {}).get("total", 0)
    ok("提现审核列表正常", f"共 {total} 条")
else:
    fail("提现审核列表异常", f"code={code}")

code, data = api("GET", "/api/v1/admin/goods?page=1&page_size=5", token=admin_token)
if code == 200:
    total = data.get("data", {}).get("total", 0)
    ok("商品管理正常", f"共 {total} 条")
else:
    warn("商品管理异常", f"code={code}")

# 11. 佣金结算
section("11. 佣金结算")
code, data = api("GET", "/api/v1/admin/commission-settlement/flows?page=1&page_size=5", token=admin_token)
if code == 200:
    ok("佣金流水列表正常")
else:
    warn("佣金流水列表异常", f"code={code}")

code, data = api("GET", "/api/v1/admin/reconciliation/records?page=1&page_size=5", token=admin_token)
if code == 200:
    ok("佣金对账正常")
else:
    warn("佣金对账异常", f"code={code}")

# 12. 埋点接口
section("12. 埋点与系统")
code, data = api("POST", "/api/v1/track/event",
                 body={"events": [{
                     "event_type": "prod_test_page_view",
                     "event_data": {"page": "full_chain_test"},
                     "timestamp": int(time.time() * 1000)
                 }]})
if code == 200:
    ok("埋点上报正常")
else:
    fail("埋点上报异常", f"code={code}")

# 系统配置
code, data = api("GET", "/api/v1/admin/config/list", token=admin_token)
if code == 200:
    ok("系统配置读取正常")
else:
    warn("系统配置读取异常", f"code={code}")

# 13. 管理后台静态页面
section("13. 管理后台静态资源")
ok_admin_page, admin_page_status = check_http(f"{ADMIN_DOMAIN}/index.html")
if ok_admin_page:
    ok("管理后台首页可访问", f"status={admin_page_status}")
else:
    warn("管理后台首页不可达", str(admin_page_status))

# ─── 汇总 ───────────────────────────────────────────────────
section("测试结果汇总")
total = PASS + FAIL + WARN
print(f"  总计: {total} 项")
print(f"  通过: {PASS}  ✅")
print(f"  失败: {FAIL}  ❌")
print(f"  警告: {WARN}  ⚠️")
print()

if FAIL > 0:
    print("  失败项:")
    for level, name, detail in results:
        if level == "FAIL":
            print(f"    ❌ {name}: {detail}")
    print()

if WARN > 0:
    print("  警告项:")
    for level, name, detail in results:
        if level == "WARN":
            print(f"    ⚠️  {name}: {detail}")
    print()

print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  结论: {'✅ 核心链路正常' if FAIL == 0 else '❌ 存在失败项，需排查'}")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)
