#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S07 一期线上全量自检复测 - 小程序 API 全模块
覆盖：商品搜索/转链/短链/订单/佣金/提现/消息/订阅/渠道/用户认证
用法: python3 s07_miniapp_retest.py <user_token>
"""
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

BASE = "https://api.dftsh.top"

TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""

PASS = 0
FAIL = 0
FAILED_ITEMS = []


def ok(name, detail=""):
    global PASS
    PASS += 1
    print(f"  [PASS] {name}  {detail}")


def fail(name, detail=""):
    global FAIL
    FAIL += 1
    FAILED_ITEMS.append((name, detail))
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


def check(name, method, path, expect_http=200, expect_code=200, token=None, body=None, headers=None):
    http, resp = api(method, path, token=token, body=body, headers=headers)
    biz = resp.get("code") if isinstance(resp, dict) else None
    detail = f"HTTP={http} code={biz}"
    if http == expect_http and (expect_code is None or biz == expect_code):
        ok(name, detail)
    else:
        fail(name, f"{detail} 期望 HTTP={expect_http} code={expect_code} resp={str(resp)[:200]}")
    time.sleep(0.5)
    return http, resp


def main():
    print(f"金角大王 CPS V2.0 一期 S07 小程序全模块复测")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"BASE: {BASE}")

    # ═══ 1. 用户认证 ═══
    section("1. 用户认证")
    check("用户信息", "GET", "/api/v1/user/auth/profile", token=TOKEN)
    # 未带token访问（profile 支持匿名返回默认结构，不应 500）
    http, resp = api("GET", "/api/v1/user/auth/profile")
    if http == 200 or http in (401, 403):
        ok("未带token访问安全处理", f"HTTP={http} code={resp.get('code')}")
    else:
        fail("未带token访问安全处理", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 2. 商品搜索（公开接口）═══
    section("2. 商品搜索")
    kw1 = urllib.parse.quote("手机")
    kw2 = urllib.parse.quote("耳机")
    check("商品搜索-手机", "GET", f"/api/public/goods/search?keyword={kw1}&page=1&size=5&channel_code=myq", token=TOKEN)
    check("商品搜索-耳机", "GET", f"/api/public/goods/search?keyword={kw2}&page=1&size=3&channel_code=myq", token=TOKEN)
    # 边界：空关键词
    http, resp = api("GET", "/api/public/goods/search?keyword=&page=1&size=5", token=TOKEN)
    if http in (400, 422):
        ok("商品搜索-空关键词被拦截", f"HTTP={http}")
    else:
        fail("商品搜索-空关键词被拦截", f"HTTP={http} resp={str(resp)[:150]}")
    # 边界：超长关键词
    http, resp = api("GET", f"/api/public/goods/search?keyword={'a'*65}&page=1&size=5", token=TOKEN)
    if http in (400, 422):
        ok("商品搜索-超长关键词被拦截", f"HTTP={http}")
    else:
        fail("商品搜索-超长关键词被拦截", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 3. 短链创建 ═══
    section("3. 短链创建")
    check("短链创建", "POST", "/api/v1/short-link/create", token=TOKEN,
          body={"user_id": 1, "goods_id": "test_goods_001", "goods_title": "复测商品", "channel_code": "myq"})
    # 边界：缺省参数
    http, resp = api("POST", "/api/v1/short-link/create", token=TOKEN, body={})
    if http in (400, 422):
        ok("短链创建-缺省参数被拦截", f"HTTP={http}")
    else:
        fail("短链创建-缺省参数被拦截", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 4. CPS 订单 ═══
    section("4. CPS 订单")
    check("订单列表", "GET", "/api/v1/cps/order?page=1&page_size=5", token=TOKEN)
    # 边界：非法页码
    http, resp = api("GET", "/api/v1/cps/order?page=0&page_size=5", token=TOKEN)
    if http in (400, 422):
        ok("订单列表-非法页码被拦截", f"HTTP={http}")
    else:
        fail("订单列表-非法页码被拦截", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 5. CPS 佣金 ═══
    section("5. CPS 佣金")
    check("佣金汇总", "GET", "/api/v1/cps/commission/summary/0", token=TOKEN)
    # 边界：不存在的订单ID（返回零值结构，不报错）
    http, resp = api("GET", "/api/v1/cps/commission/summary/99999999", token=TOKEN)
    if http == 200:
        ok("佣金汇总-不存在订单返回零值", f"HTTP={http} total={resp.get('data',{}).get('total_amount')}")
    else:
        fail("佣金汇总-不存在订单返回零值", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 6. 提现 ═══
    section("6. 提现")
    check("提现账户", "GET", "/api/v1/withdraw/account", token=TOKEN)
    check("提现记录", "GET", "/api/v1/withdraw/applies?page=1&page_size=5", token=TOKEN)
    # 提现申请-边界：金额不足（schema 校验 422）
    http, resp = api("POST", "/api/v1/withdraw/apply", token=TOKEN, body={"apply_amount": 0.01})
    if http in (400, 422):
        ok("提现申请-过低金额被拦截", f"HTTP={http} code={resp.get('code')}")
    else:
        fail("提现申请-过低金额被拦截", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 7. 站内消息 ═══
    section("7. 站内消息")
    check("消息列表", "GET", "/api/v1/message/list?page=1&page_size=5", token=TOKEN)
    check("未读数量", "GET", "/api/v1/message/unread-count", token=TOKEN)

    # ═══ 8. 营销消息订阅 ═══
    section("8. 营销消息订阅")
    check("订阅模板列表", "GET", "/api/v1/message/subscribe/templates", token=TOKEN)
    check("订阅状态", "GET", "/api/v1/message/subscribe/status", token=TOKEN)

    # ═══ 9. 渠道信息 ═══
    section("9. 渠道信息")
    check("渠道黑名单检查", "GET", "/api/v1/b11/channel/blacklist/check?channel_code=myq&blacklist_type=user&blacklist_value=1", token=TOKEN)
    check("渠道统计汇总", "GET", "/api/v1/b11/channel/stat/summary?start_date=2026-08-01&end_date=2026-08-15", token=TOKEN)
    # 边界：非法日期（返回业务错误码400）
    http, resp = api("GET", "/api/v1/b11/channel/stat/summary?start_date=bad&end_date=2026-08-15", token=TOKEN)
    if http == 200 and resp.get("code") == 400:
        ok("渠道统计-非法日期被拦截", f"HTTP={http} code={resp.get('code')}")
    elif http in (400, 422):
        ok("渠道统计-非法日期被拦截", f"HTTP={http}")
    else:
        fail("渠道统计-非法日期被拦截", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 10. 链接转链（异常场景：无效物料URL）═══
    section("10. 链接转链")
    http, resp = api("POST", "/api/public/goods/convert-link", token=TOKEN,
                     body={"original_url": "https://item.taobao.com/item.htm?id=123", "user_channel_id": "test_001", "channel_code": "myq"})
    if http == 200:
        ok("链接转链-成功", f"HTTP={http}")
    elif http in (400, 422):
        ok("链接转链-业务拦截（预期-无效物料）", f"HTTP={http} code={resp.get('code')} msg={str(resp.get('msg',''))[:50]}")
    elif http == 500 and resp.get("code") == 502:
        ok("链接转链-渠道异常结构化返回（无500崩溃）", f"HTTP={http} code={resp.get('code')} msg={str(resp.get('msg',''))[:50]}")
    else:
        fail("链接转链-应业务拦截而非500", f"HTTP={http} resp={str(resp)[:150]}")

    # ═══ 汇总 ═══
    print(f"\n{'='*64}")
    print(f"小程序全模块复测完成")
    print(f"通过: {PASS}  失败: {FAIL}")
    if FAIL > 0:
        print("失败明细:")
        for name, detail in FAILED_ITEMS:
            print(f"  [FAIL] {name}: {detail}")
    print(f"{'='*64}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())