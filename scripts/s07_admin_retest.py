#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S07 一期线上全量自检复测 - 后台管理 API 全模块
覆盖：认证/RBAC/大盘/审计/渠道/商品/订单/结算/提现/用户/对账/逆向/配置/消息/异常订单/定时任务
用法: python3 s07_admin_retest.py <admin_token> <user_token>
"""
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

import os
BASE = os.environ.get("BASE_URL", "https://api.dftsh.top")

ADMIN_TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
USER_TOKEN = sys.argv[2] if len(sys.argv) > 2 else ""

PASS = 0
FAIL = 0
FAILED_ITEMS = []
results = []


def ok(name, detail=""):
    global PASS
    PASS += 1
    results.append(("PASS", name, detail))
    print(f"  [PASS] {name}  {detail}")


def fail(name, detail=""):
    global FAIL
    FAIL += 1
    FAILED_ITEMS.append((name, detail))
    results.append(("FAIL", name, detail))
    print(f"  [FAIL] {name}  {detail}")


def section(title):
    print(f"\n{'='*64}")
    print(f"  {title}")
    print(f"{'='*64}")


def api(method, path, token=None, body=None, headers=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
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


def is_ok(resp):
    return isinstance(resp, dict) and resp.get("code") == 200


def check(name, method, path, expect_http=200, expect_code=200, token=None, body=None, headers=None):
    """通用检查：HTTP 状态 + 业务码"""
    http, resp = api(method, path, token=token, body=body, headers=headers)
    biz = resp.get("code") if isinstance(resp, dict) else None
    detail = f"HTTP={http} code={biz}"
    if http == expect_http and (expect_code is None or biz == expect_code):
        ok(name, detail)
    else:
        fail(name, f"{detail} 期望 HTTP={expect_http} code={expect_code} resp={str(resp)[:200]}")
    time.sleep(1.2)  # 限流规避
    return http, resp


def main():
    print(f"金角大王 CPS V2.0 一期 S07 后台管理全模块复测")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"BASE: {BASE}")

    # ═══ 1. 认证与管理员 ═══
    section("1. 认证与管理员")
    check("管理员信息", "GET", "/api/v1/admin/auth/me", token=ADMIN_TOKEN)
    # 修改密码-错误原密码（边界）
    http, resp = api("PUT", "/api/v1/admin/auth/password", token=ADMIN_TOKEN,
                     body={"old_password": "wrong_old_pwd_xyz", "new_password": "NewPass@123"})
    if http == 400 or (isinstance(resp, dict) and resp.get("code") in (400, 401)):
        ok("改密-错误原密码被拦截", f"HTTP={http} code={resp.get('code')}")
    else:
        fail("改密-错误原密码被拦截", f"HTTP={http} resp={str(resp)[:150]}")
    # 未带token访问（鉴权链路）
    http, resp = api("GET", "/api/v1/admin/auth/me")
    if http in (401, 403):
        ok("未带token访问被拦截", f"HTTP={http}")
    else:
        fail("未带token访问被拦截", f"HTTP={http}")

    # ═══ 2. RBAC 权限链路 ═══
    section("2. RBAC 权限链路")
    check("RBAC角色列表", "GET", "/api/v1/admin/rbac/roles", token=ADMIN_TOKEN)
    check("RBAC菜单树", "GET", "/api/v1/admin/rbac/menus/tree", token=ADMIN_TOKEN)
    check("RBAC权限码", "GET", "/api/v1/admin/rbac/permissions", token=ADMIN_TOKEN)
    check("RBAC管理员列表", "GET", "/api/v1/admin/rbac/users", token=ADMIN_TOKEN)
    # 权限隔离：普通用户token访问后台接口应被拦截
    http, resp = api("GET", "/api/v1/admin/rbac/roles", token=USER_TOKEN)
    if http in (401, 403):
        ok("权限隔离-普通用户访问RBAC被拦截", f"HTTP={http}")
    else:
        fail("权限隔离-普通用户访问RBAC被拦截", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 3. 数据大盘 ═══
    section("3. 数据大盘")
    check("大盘卡片", "GET", "/api/v1/admin/dashboard/cards", token=ADMIN_TOKEN)
    check("订单趋势", "GET", "/api/v1/admin/dashboard/order-trend?start_date=2026-08-01&end_date=2026-08-15", token=ADMIN_TOKEN)
    check("提现趋势", "GET", "/api/v1/admin/dashboard/withdraw-trend?start_date=2026-08-01&end_date=2026-08-15", token=ADMIN_TOKEN)
    check("佣金统计", "GET", "/api/v1/admin/dashboard/commission-stats?group_by=date&start_date=2026-08-01&end_date=2026-08-15", token=ADMIN_TOKEN)
    # 边界：日期参数非法
    http, resp = api("GET", "/api/v1/admin/dashboard/order-trend?start_date=bad-date&end_date=2026-08-15", token=ADMIN_TOKEN)
    if http in (400, 422):
        ok("大盘-非法日期被拦截", f"HTTP={http}")
    else:
        fail("大盘-非法日期被拦截", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 4. 审计日志 ═══
    section("4. 审计日志")
    check("审计日志列表", "GET", "/api/v1/admin/audit/logs?page=1&page_size=5", token=ADMIN_TOKEN)
    check("审计统计", "GET", "/api/v1/admin/audit/stats", token=ADMIN_TOKEN)

    # ═══ 5. 渠道配置 ═══
    section("5. 渠道配置")
    check("渠道列表", "GET", "/api/v1/admin/channel/list", token=ADMIN_TOKEN)
    check("渠道详情myq", "GET", "/api/v1/admin/channel/myq", token=ADMIN_TOKEN)
    check("渠道密钥测试-生产拦截", "POST", "/api/v1/admin/channel/test-key", expect_code=400, token=ADMIN_TOKEN,
         body={"channel_code": "myq", "api_token": "test"})
    # 渠道B06
    check("B06渠道列表", "GET", "/api/v1/admin/b06-channel/list", token=ADMIN_TOKEN)
    check("B06渠道详情", "GET", "/api/v1/admin/b06-channel/myq", token=ADMIN_TOKEN)
    check("B06渠道大盘汇总", "GET", "/api/v1/admin/b06-channel/dashboard/summary", token=ADMIN_TOKEN)
    check("B06渠道趋势", "GET", "/api/v1/admin/b06-channel/dashboard/trend?start_date=2026-08-01&end_date=2026-08-15", token=ADMIN_TOKEN)
    # B11渠道黑名单
    check("B11黑名单列表", "GET", "/api/v1/admin/b11/channel/blacklist/list", token=ADMIN_TOKEN)
    check("B11渠道配置日志", "GET", "/api/v1/admin/b11/channel/config-log/list", token=ADMIN_TOKEN)
    check("B11渠道日统计", "GET", "/api/v1/admin/b11/channel/stat/daily?start_date=2026-08-01&end_date=2026-08-15", token=ADMIN_TOKEN)
    check("B11渠道汇总", "GET", "/api/v1/admin/b11/channel/stat/summary?start_date=2026-08-01&end_date=2026-08-15", token=ADMIN_TOKEN)

    # ═══ 6. 商品管理 ═══
    section("6. 商品管理")
    check("商品列表", "GET", "/api/v1/admin/goods?page=1&page_size=5", token=ADMIN_TOKEN)
    check("商品同步", "POST", "/api/v1/admin/goods/sync", token=ADMIN_TOKEN, body={"source_channel": "myq", "keyword": "手机", "page": 1, "page_size": 5})
    # 边界：不存在的商品
    http, resp = api("GET", "/api/v1/admin/goods/99999999?source_channel=myq", token=ADMIN_TOKEN)
    if http == 404 or (isinstance(resp, dict) and resp.get("code") == 404):
        ok("商品-不存在ID返回404", f"HTTP={http}")
    else:
        fail("商品-不存在ID返回404", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 7. 订单管理 ═══
    section("7. 订单管理")
    check("订单列表", "GET", "/api/v1/admin/b13/orders?page=1&page_size=5", token=ADMIN_TOKEN)
    check("订单状态机规则", "GET", "/api/v1/admin/b12/order-state/rules", token=ADMIN_TOKEN)
    check("订单状态机巡检", "POST", "/api/v1/admin/b12/order-state/patrol", token=ADMIN_TOKEN, body={})
    check("异常订单列表", "GET", "/api/v1/admin/abnormal-orders/list?page=1&page_size=5", token=ADMIN_TOKEN)
    check("异常订单统计", "GET", "/api/v1/admin/abnormal-orders/stats", token=ADMIN_TOKEN)
    check("结算订单列表", "GET", "/api/v1/admin/commission-settlement/orders?page=1&page_size=5", token=ADMIN_TOKEN)
    check("结算流水", "GET", "/api/v1/admin/commission-settlement/flows?page=1&page_size=5", token=ADMIN_TOKEN)
    check("结算记录", "GET", "/api/v1/admin/settlement/settlements?page=1&page_size=5", token=ADMIN_TOKEN)
    check("结算操作日志", "GET", "/api/v1/admin/settlement/operation-logs?page=1&page_size=5", token=ADMIN_TOKEN)
    check("结算逾期列表", "GET", "/api/v1/admin/settlement/settlements/overdue", token=ADMIN_TOKEN)

    # ═══ 8. 提现管理 ═══
    section("8. 提现管理")
    check("提现申请列表", "GET", "/api/v1/admin/withdraw/applies?page=1&page_size=5", token=ADMIN_TOKEN)
    check("B13提现列表", "GET", "/api/v1/admin/b13/withdraws?page=1&page_size=5", token=ADMIN_TOKEN)

    # ═══ 9. 用户管理 ═══
    section("9. 用户管理")
    check("用户列表", "GET", "/api/v1/admin/users-manage?page=1&page_size=5", token=ADMIN_TOKEN)
    check("用户详情", "GET", "/api/v1/admin/users-manage/3", token=ADMIN_TOKEN)
    # 边界：不存在的用户
    http, resp = api("GET", "/api/v1/admin/users-manage/999999", token=ADMIN_TOKEN)
    if http == 404 or (isinstance(resp, dict) and resp.get("code") == 404):
        ok("用户-不存在ID返回404", f"HTTP={http}")
    else:
        fail("用户-不存在ID返回404", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 10. 佣金账户与资金 ═══
    section("10. 佣金账户与资金")
    check("B08账户列表", "GET", "/api/v1/admin/b08/accounts?page=1&page_size=5", token=ADMIN_TOKEN)
    check("B08账户详情", "GET", "/api/v1/admin/b08/accounts/3", token=ADMIN_TOKEN)
    check("B08资金流水", "GET", "/api/v1/admin/b08/fund-flows?page=1&page_size=5", token=ADMIN_TOKEN)
    check("B08统计", "GET", "/api/v1/admin/b08/statistics", token=ADMIN_TOKEN)

    # ═══ 11. 逆向冲减 ═══
    section("11. 逆向冲减")
    check("逆向冲减记录", "GET", "/api/v1/admin/b07/reverse-commission/records?page=1&page_size=5", token=ADMIN_TOKEN)
    check("逆向冲减统计", "GET", "/api/v1/admin/b07/reverse-commission/statistics", token=ADMIN_TOKEN)
    check("逆向冲减识别", "POST", "/api/v1/admin/b07/reverse-commission/identify", token=ADMIN_TOKEN, body={})
    check("退款扣减日志", "GET", "/api/v1/admin/refund-deduction/logs?page=1&page_size=5", token=ADMIN_TOKEN)

    # ═══ 12. 对账 ═══
    section("12. 对账")
    check("对账差异列表", "GET", "/api/v1/admin/reconciliation/diffs?page=1&page_size=5", token=ADMIN_TOKEN)
    check("对账记录", "GET", "/api/v1/admin/reconciliation/records?page=1&page_size=5", token=ADMIN_TOKEN)
    check("对账看板", "GET", "/api/v1/admin/reconciliation/dashboard", token=ADMIN_TOKEN)
    check("对账告警", "GET", "/api/v1/admin/reconciliation/alerts", token=ADMIN_TOKEN)
    check("对账汇总", "GET", "/api/v1/admin/b06-2/reconciliation/summary", token=ADMIN_TOKEN)
    check("对账明细", "GET", "/api/v1/admin/b06-2/reconciliation/detail", token=ADMIN_TOKEN)

    # ═══ 13. 系统配置 ═══
    section("13. 系统配置")
    check("配置列表", "GET", "/api/v1/admin/config/", token=ADMIN_TOKEN)
    check("配置注册表", "GET", "/api/v1/admin/config/registry", token=ADMIN_TOKEN)
    check("配置校验", "POST", "/api/v1/admin/config/validate", token=ADMIN_TOKEN, body={"config_key": "test_key", "config_value": "test_value"})

    # ═══ 14. 营销消息 ═══
    section("14. 营销消息")
    check("消息模板列表", "GET", "/api/v1/admin/message/templates?page=1&page_size=5", token=ADMIN_TOKEN)
    check("推送记录列表", "GET", "/api/v1/admin/message/push-records?page=1&page_size=5", token=ADMIN_TOKEN)
    check("订阅绑定列表", "GET", "/api/v1/admin/message/subscriptions?page=1&page_size=5", token=ADMIN_TOKEN)
    check("消息列表", "GET", "/api/v1/admin/message/list?page=1&page_size=5", token=ADMIN_TOKEN)

    # ═══ 15. 订单同步与定时任务 ═══
    section("15. 订单同步与定时任务")
    check("同步状态", "GET", "/api/v1/admin/order-sync/status", token=ADMIN_TOKEN)
    check("定时任务日志", "GET", "/api/v1/admin/scheduled-task-run-logs?page=1&page_size=5", token=ADMIN_TOKEN)

    # ═══ 16. 佣金流水校验 ═══
    section("16. 佣金流水校验")
    check("流水校验日志", "GET", "/api/v1/admin/commission-flow-validation/logs?page=1&page_size=5", token=ADMIN_TOKEN)

    # ═══ 17. 导出（Excel）═══
    section("17. 导出")
    check("导出订单", "POST", "/api/v1/admin/b06-2/export/order", token=ADMIN_TOKEN, body={"start_time": "2026-08-01 00:00:00", "end_time": "2026-08-15 23:59:59"})
    check("导出佣金账单", "POST", "/api/v1/admin/b06-2/export/commission-bill", token=ADMIN_TOKEN, body={"start_time": "2026-08-01 00:00:00", "end_time": "2026-08-15 23:59:59"})
    check("导出任务日志", "GET", "/api/v1/admin/b06-2/export/task-logs", token=ADMIN_TOKEN)
    check("导出结算记录", "GET", "/api/v1/admin/settlement/settlements/export", token=ADMIN_TOKEN)

    # ═══ 18. 权限隔离（用户token访问后台）═══
    section("18. 权限隔离")
    for name, method, path in [
        ("用户访问大盘", "GET", "/api/v1/admin/dashboard/cards"),
        ("用户访问订单", "GET", "/api/v1/admin/b13/orders?page=1&page_size=5"),
        ("用户访问提现审核", "GET", "/api/v1/admin/withdraw/applies?page=1&page_size=5"),
        ("用户访问用户管理", "GET", "/api/v1/admin/users-manage?page=1&page_size=5"),
        ("用户访问商品管理", "GET", "/api/v1/admin/goods?page=1&page_size=5"),
        ("用户访问渠道配置", "GET", "/api/v1/admin/channel/list"),
        ("用户访问审计日志", "GET", "/api/v1/admin/audit/logs?page=1&page_size=5"),
        ("用户访问对账", "GET", "/api/v1/admin/reconciliation/diffs?page=1&page_size=5"),
        ("用户访问系统配置", "GET", "/api/v1/admin/config/"),
        ("用户访问定时任务日志", "GET", "/api/v1/admin/scheduled-task-run-logs?page=1&page_size=5"),
    ]:
        http, resp = api(method, path, token=USER_TOKEN)
        if http in (401, 403):
            ok(f"权限隔离-{name}被拦截", f"HTTP={http}")
        else:
            fail(f"权限隔离-{name}被拦截", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 汇总 ═══
    print(f"\n{'='*64}")
    print(f"后台管理全模块复测完成")
    print(f"通过: {PASS}  失败: {FAIL}")
    if FAIL > 0:
        print("失败明细:")
        for name, detail in FAILED_ITEMS:
            print(f"  ❌ {name}: {detail}")
    print(f"{'='*64}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
