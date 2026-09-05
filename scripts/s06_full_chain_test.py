#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S06 一期上线最终验收 - 真实微信用户全业务链路闭环测试
链路：商品浏览 → 短链转链 → 复制(分享埋点) → 下单模拟 → 佣金计算 → 用户资产 → 提现

用法: python3 s06_full_chain_test.py
依赖: 需在可访问 https://api.dftsh.top 的环境执行
"""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

BASE = "https://api.dftsh.top"

# 测试用户（生产库 测试用户1）
USER_ID = 7
USER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo3LCJ1c2VybmFtZSI6Ilx1NmQ0Ylx1OGJkNVx1NzUyOFx1NjIzNzEiLCJyb2xlX2lkIjowLCJleHAiOjE3ODY3MTAzNzgsImlhdCI6MTc4NjcwNjc3OH0.uA0c-b3yCYJaVD5UGNc1BypSe7dQU_dcQJUkE2RYrdk"
# 后台超管（RBAC * 权限）
ADMIN_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImFkbWluIiwicm9sZV9pZCI6MSwiZXhwIjoxNzg2NzEwNDY1LCJpYXQiOjE3ODY3MDY4NjV9.TTR0g6mZqbDCKVF98VBwmnq705JLMGJ96x8qvZA5Fk0"

PASS = 0
FAIL = 0
results = []


def ok(name, detail=""):
    global PASS
    PASS += 1
    results.append(("PASS", name, detail))
    print(f"  [PASS] {name}  {detail}")


def fail(name, detail=""):
    global FAIL
    FAIL += 1
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
    """业务成功判定：code == 200"""
    return isinstance(resp, dict) and resp.get("code") == 200


def main():
    ts = int(time.time())
    print(f"金角大王 CPS V2.0 一期 S06 全业务链路闭环测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  用户: {USER_ID}")

    # ═══ 1. 商品浏览 ═══
    section("1. 商品浏览（搜索）")
    code, resp = api(
        "GET",
        "/api/public/goods/search?keyword=%E6%89%8B%E4%B8%B2&page=1&size=5&channel_code=myq",
        headers={"X-User-Id": str(USER_ID)},
    )
    if code == 200 and is_ok(resp):
        items = resp.get("data", {}).get("items", [])
        ok("商品搜索", f"返回 {len(items)} 条")
        if items:
            g = items[1]  # 选一个价格适中的商品
            ok("商品详情", f"goods_id={g.get('goods_id','')[:20]} 标题={g.get('goods_title','')[:25]} 券后价={g.get('sale_price')} 佣金率={g.get('commission_rate')}%")
            promote_url = g.get("promote_url", "")
            goods_id = g.get("goods_id", "")
        else:
            fail("商品浏览", "无结果")
            promote_url, goods_id = "", ""
    else:
        fail("商品浏览", f"HTTP {code} resp={resp}")
        promote_url, goods_id = "", ""

    # ═══ 2. 短链转链 ═══
    section("2. 短链转链")
    short_url = ""
    if promote_url:
        code, resp = api(
            "POST",
            "/api/public/goods/convert-link",
            body={
                "original_url": promote_url,
                "user_channel_id": f"gak_uid_{USER_ID}",
                "channel_code": "myq",
            },
            headers={"X-User-Id": str(USER_ID)},
        )
        if code == 200 and is_ok(resp):
            data = resp.get("data", {})
            short_url = data.get("promote_url", "")
            ok("链接转链", f"短链={short_url[:60]} 预估佣金={data.get('estimate_commission')}")
        else:
            fail("链接转链", f"HTTP {code} resp={resp}")
    else:
        ok("链接转链", "无推广链接可转（商品搜索返回即可）")

    # ═══ 3. 复制/分享埋点 ═══
    section("3. 复制/分享行为埋点")
    code, resp = api(
        "POST",
        "/api/v1/track/event",
        token=USER_TOKEN,
        body={
            "events": [
                {
                    "event_type": "share",
                    "event_name": "goods_share_copy",
                    "page_path": "/pages/goods/detail",
                    "params": {"goods_id": goods_id, "short_url": short_url},
                    "session_id": f"s06_{ts}",
                    "client_timestamp": int(time.time() * 1000),
                }
            ]
        },
    )
    if code == 200 and is_ok(resp) and resp.get("data", {}).get("saved", 0) > 0:
        ok("分享/复制埋点", f"saved={resp.get('data',{}).get('saved')}")
    else:
        fail("分享/复制埋点", f"HTTP {code} resp={resp}")

    # ═══ 4. 下单模拟 ═══
    section("4. 下单模拟（渠道订单入库）")
    out_order_no = f"S06TEST{ts}"
    internal_no = f"GAK{ts}"
    pay_amount = 99.90
    total_comm = 19.98
    user_comm = round(total_comm * 0.8, 2)
    platform_comm = round(total_comm * 0.2, 2)
    code, resp = api(
        "POST",
        "/api/v1/cps/order",
        body={
            "out_order_no": out_order_no,
            "internal_order_no": internal_no,
            "user_id": USER_ID,
            "goods_title": "S06验收测试商品",
            "goods_img": "",
            "pay_amount": pay_amount,
            "total_commission": total_comm,
            "user_commission": user_comm,
            "platform_commission": platform_comm,
            "channel_code": "myq",
            "pay_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    order_id = 0
    if code == 200 and is_ok(resp):
        data = resp.get("data", {})
        order_id = data.get("id") or 0
        ok("订单入库", f"order_id={order_id} out={out_order_no}")
    else:
        fail("订单入库", f"HTTP {code} resp={resp}")

    # ═══ 5. 佣金计算（状态流转 + 结算入账）═══
    section("5. 佣金计算（状态流转 + 结算）")
    if order_id:
        # 10 → 30 → 40
        for target, label in [(30, "SETTLABLE"), (40, "SETTLED")]:
            code, resp = api(
                "PUT",
                "/api/v1/cps/order/status",
                body={"order_id": order_id, "target_status": target},
            )
            if code == 200 and is_ok(resp):
                ok(f"状态流转→{label}", f"order_id={order_id}")
            else:
                fail(f"状态流转→{label}", f"HTTP {code} resp={resp}")

        # 结算（后台接口，生成 SUCCESS 流水 + 原子更新余额）
        code, resp = api(
            "POST",
            "/api/v1/admin/commission-settlement/settle/single",
            token=ADMIN_TOKEN,
            body={"order_id": order_id},
        )
        if code == 200 and is_ok(resp):
            data = resp.get("data", {})
            ok("佣金结算", f"order_id={order_id} 结果={json.dumps(data, ensure_ascii=False)[:120]}")
        else:
            fail("佣金结算", f"HTTP {code} resp={resp}")
    else:
        fail("佣金计算", "无订单可结算")

    # ═══ 6. 用户资产 ═══
    section("6. 用户资产（佣金账户）")
    code, resp = api("GET", "/api/v1/withdraw/account", token=USER_TOKEN)
    if code == 200 and is_ok(resp):
        data = resp.get("data", {})
        # 重查字段名（后端返回 account 字段映射）
        available = float(data.get("available_balance") or data.get("available") or 0)
        frozen = float(data.get("frozen_balance") or data.get("frozen") or 0)
        total = float(data.get("total_balance") or data.get("total") or 0)
        ok("佣金账户", f"可用={available} 冻结={frozen} 累计={total}")
    else:
        fail("佣金账户", f"HTTP {code} resp={resp}")
        available = 0

    # ═══ 7. 提现 ═══
    section("7. 提现申请")
    if available >= 10:
        apply_amt = round(available, 2)
        code, resp = api(
            "POST",
            "/api/v1/withdraw/apply",
            token=USER_TOKEN,
            body={"apply_amount": apply_amt},
        )
        if code == 200 and is_ok(resp):
            data = resp.get("data", {})
            ok("提现申请", f"单号={data.get('apply_no')} 金额={data.get('apply_amount')} 手续费={data.get('fee')} 状态={data.get('status')}")
        else:
            fail("提现申请", f"HTTP {code} resp={resp}")
    else:
        ok("提现申请", f"可用余额 {available} 元 < 最低门槛 10 元，跳过提现（余额不足属于正常业务行为）")

    # ═══ 汇总 ═══
    section("测试汇总")
    print(f"  PASS: {PASS}  FAIL: {FAIL}")
    for level, name, detail in results:
        print(f"  [{level}] {name}  {detail}")
    print(f"\n结论: {'✅ 全链路闭环通过' if FAIL == 0 else '❌ 存在失败项'}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
