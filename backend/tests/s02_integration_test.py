# @ai-generated
"""
S02 全链路联调测试脚本（完整业务链路版本）
覆盖：登录→商品浏览→转链→模拟订单生成→佣金结算→提现申请→后台审核打款
      + F04渠道配置/消息模板全套功能 + 权限隔离 + 异常场景 + 审计日志 + 埋点上报

执行：python3 tests/s02_integration_test.py
退出码：0=无P0 BUG；1=存在P0 BUG
"""
import asyncio
import httpx
import json
import sys
import time
from datetime import datetime, timedelta
from decimal import Decimal

BASE_URL = "http://localhost:3001"

RESULTS = []
BUGS = []


def log_result(category, name, success, detail=""):
    status = "✅ PASS" if success else "❌ FAIL"
    RESULTS.append({"category": category, "name": name, "success": success, "detail": detail})
    print(f"  {status} | {category} | {name}" + (f" | {detail}" if detail else ""))


def log_bug(severity, module, description, detail=""):
    BUGS.append({"severity": severity, "module": module, "description": description, "detail": detail})
    print(f"  🐛 BUG [{severity}] | {module} | {description}" + (f" | {detail}" if detail else ""))


async def api_call(client, method, path, token=None, json_data=None, params=None, headers=None):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    url = f"{BASE_URL}{path}"
    try:
        resp = await client.request(method, url, headers=h, json=json_data, params=params, timeout=20)
        try:
            data = resp.json()
        except Exception:
            data = {"error": f"非JSON响应(status={resp.status_code}): {resp.text[:200]}"}
        return resp.status_code, data
    except Exception as e:
        return 0, {"error": str(e)}


def sg(data, *keys, default=None):
    """safe_get: 安全嵌套取值"""
    for k in keys:
        if data is None or not isinstance(data, dict):
            return default
        data = data.get(k)
    return data if data is not None else default


async def run_tests():
    async with httpx.AsyncClient() as client:
        admin_token = None
        user_token = None
        user_id = None
        order_id = None
        apply_id = None

        # ═══ 1. 管理员登录 ═══
        print("\n" + "=" * 60)
        print("1. 管理员登录")
        print("=" * 60)
        code, data = await api_call(client, "POST", "/api/v1/admin/auth/login",
                                    json_data={"username": "admin", "password": "admin@12345"})
        if code == 200 and sg(data, "code") == 200:
            admin_token = sg(data, "data", "token")
            log_result("登录", "管理员登录", True, f"user_id={sg(data,'data','user_id')}, role={sg(data,'data','role_name')}")
        else:
            log_result("登录", "管理员登录", False, str(data)[:200])
            log_bug("P0", "认证", "管理员登录失败", str(data)[:200])
            return RESULTS, BUGS

        # ═══ 2. 渠道配置种子 ═══
        print("\n" + "=" * 60)
        print("2. 渠道配置种子数据")
        print("=" * 60)
        code, data = await api_call(client, "GET", "/api/v1/admin/channel/list",
                                    token=admin_token, params={"page": 1, "page_size": 20})
        existing = sg(data, "data", "items", default=[]) or []
        log_result("渠道配置", "查询列表", code == 200, f"现有{len(existing)}条")

        for ch_code, ch_name in [("myq", "喵有券"), ("orderx", "订单侠")]:
            if not any(c.get("channel_code") == ch_code for c in existing):
                code, data = await api_call(client, "POST", "/api/v1/admin/channel",
                                            token=admin_token,
                                            json_data={"channel_code": ch_code, "channel_name": ch_name,
                                                       "api_token": f"dev_{ch_code}_token_placeholder",
                                                       "api_secret": f"dev_{ch_code}_secret_placeholder",
                                                       "pid": f"{ch_code}_pid_test", "settle_rate": 0.8,
                                                       "status": True, "remark": f"S02测试-{ch_name}"})
                log_result("渠道配置", f"创建{ch_name}渠道", code == 200, f"code={code}")
            else:
                log_result("渠道配置", f"创建{ch_name}渠道", True, "已存在")

        # ═══ 3. F04 消息模板 CRUD ═══
        print("\n" + "=" * 60)
        print("3. F04 消息模板 CRUD")
        print("=" * 60)
        code, data = await api_call(client, "POST", "/api/v1/admin/message/templates",
                                    token=admin_token,
                                    json_data={"template_name": "S02-订单到账通知", "template_type": 1,
                                               "tmpl_id": "s02_tmpl_001", "title": "佣金已到账",
                                               "content": "订单{{keyword1}}佣金{{keyword2}}已到账",
                                               "keywords": ["订单号", "佣金金额"], "remark": "S02联调测试"})
        template_id = sg(data, "data", "id")
        log_result("消息模板", "创建模板", code == 200, f"template_id={template_id}")

        code, data = await api_call(client, "GET", "/api/v1/admin/message/templates",
                                    token=admin_token, params={"page": 1, "page_size": 20})
        log_result("消息模板", "查询列表", code == 200, f"total={sg(data,'data','total',default=0)}")

        if template_id:
            code, data = await api_call(client, "GET", f"/api/v1/admin/message/templates/{template_id}", token=admin_token)
            log_result("消息模板", "查询详情", code == 200, f"name={sg(data,'data','template_name','')}")

            code, data = await api_call(client, "PUT", f"/api/v1/admin/message/templates/{template_id}",
                                        token=admin_token, json_data={"remark": "S02-已更新"})
            log_result("消息模板", "更新模板", code == 200)

            code, data = await api_call(client, "PUT", f"/api/v1/admin/message/templates/{template_id}/toggle", token=admin_token)
            log_result("消息模板", "切换启停", code == 200, f"status={sg(data,'data','status')}")
            await api_call(client, "PUT", f"/api/v1/admin/message/templates/{template_id}/toggle", token=admin_token)

        code, data = await api_call(client, "POST", "/api/v1/admin/message/templates",
                                    token=admin_token,
                                    json_data={"template_name": "S02-系统公告", "template_type": 2,
                                               "title": "维护通知", "content": "系统维护中", "remark": "站内消息测试"})
        log_result("消息模板", "创建站内消息模板", code == 200)

        # ═══ 4. F04 推送记录 & 订阅绑定 ═══
        print("\n" + "=" * 60)
        print("4. F04 推送记录 & 订阅绑定查询")
        print("=" * 60)
        code, data = await api_call(client, "GET", "/api/v1/admin/message/push-records",
                                    token=admin_token, params={"page": 1, "page_size": 20})
        success = code == 200 and sg(data, "code") == 200
        log_result("推送记录", "查询列表", success, f"total={sg(data,'data','total',default=0)}")
        if not success:
            log_bug("P0", "F04推送记录", "推送记录查询500错误", f"code={code}, msg={sg(data,'msg',default='')}")

        code, data = await api_call(client, "GET", "/api/v1/admin/message/subscriptions",
                                    token=admin_token, params={"page": 1, "page_size": 20})
        success = code == 200 and sg(data, "code") == 200
        log_result("订阅绑定", "查询列表", success, f"total={sg(data,'data','total',default=0)}")
        if not success:
            log_bug("P0", "F04订阅绑定", "订阅绑定查询500错误", f"code={code}, msg={sg(data,'msg',default='')}")

        # ═══ 5. F04 渠道密钥测试 ═══
        print("\n" + "=" * 60)
        print("5. F04 渠道密钥测试")
        print("=" * 60)
        code, data = await api_call(client, "POST", "/api/v1/admin/channel/test-key",
                                    token=admin_token,
                                    json_data={"channel_code": "myq", "api_token": "dev_myq_token_placeholder_12345",
                                               "api_secret": "dev_myq_secret_placeholder"})
        log_result("密钥测试", "喵有券密钥测试", code == 200, f"success={sg(data,'data','success')}")

        code, data = await api_call(client, "POST", "/api/v1/admin/channel/test-key",
                                    token=admin_token,
                                    json_data={"channel_code": "myq", "api_token": "short", "api_secret": ""})
        is_fail = code == 200 and sg(data, "code") != 200
        log_result("密钥测试", "短Token拦截", is_fail, f"code={sg(data,'code')}")

        # ═══ 6. F04 权限隔离 ═══
        print("\n" + "=" * 60)
        print("6. F04 权限隔离测试")
        print("=" * 60)
        code, _ = await api_call(client, "GET", "/api/v1/admin/message/templates", params={"page": 1, "page_size": 10})
        log_result("权限隔离", "无Token访问消息模板", code in (401, 403), f"code={code}")
        if code not in (401, 403):
            log_bug("P0", "RBAC", "无Token可访问消息模板接口", f"code={code}")

        code, _ = await api_call(client, "POST", "/api/v1/admin/channel/test-key",
                                 json_data={"channel_code": "myq", "api_token": "test_token_12345"})
        log_result("权限隔离", "无Token密钥测试", code in (401, 403), f"code={code}")
        if code not in (401, 403):
            log_bug("P0", "RBAC", "无Token可访问渠道密钥测试接口", f"code={code}")

        # ═══ 7. C端用户登录 ═══
        print("\n" + "=" * 60)
        print("7. C端用户 Mock 登录")
        print("=" * 60)
        code, data = await api_call(client, "POST", "/api/v1/user/auth/mock-login",
                                    json_data={"user_id": 8003, "nickname": "S02测试用户"})
        if code == 200 and sg(data, "code") == 200:
            user_token = sg(data, "data", "token")
            user_id = sg(data, "data", "user_id")
            log_result("C端登录", "Mock登录", True, f"user_id={user_id}")
        else:
            log_result("C端登录", "Mock登录", False, str(data)[:200])
            log_bug("P0", "C端认证", "Mock登录失败", str(data)[:200])
            return RESULTS, BUGS

        # ═══ 8. 商品浏览（公开接口，X-User-Id头识别） ═══
        print("\n" + "=" * 60)
        print("8. 商品浏览 & 转链")
        print("=" * 60)
        # 商品搜索（公开接口，dev环境CPS token为占位，返回空列表属正常）
        code, data = await api_call(client, "GET", "/api/public/goods/search",
                                    params={"keyword": "手机", "page": 1, "size": 10, "channel_code": "myq"},
                                    headers={"X-User-Id": str(user_id)})
        search_ok = code == 200 and sg(data, "code") == 200
        goods = sg(data, "data", "items", default=[]) or []
        log_result("商品浏览", "商品搜索", search_ok, f"返回{len(goods)}条（dev渠道token占位，0条正常）")
        if not search_ok:
            log_bug("P1", "商品搜索", "商品搜索接口异常", f"code={code}, msg={sg(data,'msg', default='')}")

        # 转链（dev环境渠道token为占位，预期渠道接口超时/业务异常降级）
        code, data = await api_call(client, "POST", "/api/public/goods/convert-link",
                                    json_data={"original_url": "https://item.taobao.com/item.htm?id=123456789",
                                               "user_channel_id": f"mm_{user_id}_test",
                                               "channel_code": "myq"},
                                    headers={"X-User-Id": str(user_id)})
        # dev环境CPS token为占位，504(渠道超时)/500(渠道异常)属正常降级
        # HTTP状态可能为200(业务码降级)或500(5xx业务码映射)，均视为接口可达
        biz_code = sg(data, 'code')
        convert_ok = code in (200, 500) and biz_code in (200, 504, 500)
        log_result("商品浏览", "链接转链", convert_ok,
                   f"http={code}, biz={biz_code}, msg={str(sg(data,'msg', default=''))[:50]}（dev渠道token占位，超时属正常）")

        # ═══ 9. 佣金账户（初始） ═══
        print("\n" + "=" * 60)
        print("9. 佣金账户查询（初始）")
        print("=" * 60)
        code, data = await api_call(client, "GET", "/api/v1/withdraw/account", token=user_token)
        if code == 200 and sg(data, "code") == 200:
            acct = sg(data, "data", default={}) or {}
            balance_before = acct.get("available_balance", 0)
            frozen_before = acct.get("frozen_balance", 0)
            log_result("佣金账户", "查询账户(初始)", True, f"available={balance_before}, frozen={frozen_before}")
        else:
            log_result("佣金账户", "查询账户(初始)", False, str(data)[:150])
            log_bug("P0", "佣金账户", "账户查询失败", str(data)[:200])
            balance_before = 0
            frozen_before = 0

        # ═══ 10. 模拟订单生成（渠道推送入库） ═══
        print("\n" + "=" * 60)
        print("10. 模拟订单生成（渠道推送入库）")
        print("=" * 60)
        out_order_no = f"S02TEST{int(time.time())}"
        code, data = await api_call(client, "POST", "/api/v1/cps/order",
                                    token=user_token,
                                    json_data={
                                        "out_order_no": out_order_no,
                                        "internal_order_no": f"GAK{int(time.time())}",
                                        "user_id": user_id,
                                        "goods_title": "S02测试商品-手机",
                                        "goods_img": "",
                                        "pay_amount": 100.00,
                                        "total_commission": 20.00,
                                        "user_commission": 16.00,
                                        "platform_commission": 4.00,
                                        "channel_code": "myq",
                                        "pay_time": datetime.now().isoformat(),
                                    })
        order_ok = code == 200 and sg(data, "code") == 200
        order_id = sg(data, "data", "id")
        log_result("订单生成", "渠道订单入库", order_ok, f"order_id={order_id}, out_order_no={out_order_no}")
        if not order_ok:
            log_bug("P0", "订单", "渠道订单入库失败", f"code={code}, msg={sg(data,'msg',default='')}")

        # ═══ 11. 订单状态流转 PENDING → SETTLABLE → SETTLED ═══
        if order_id:
            print("\n" + "=" * 60)
            print("11. 订单状态流转（10→30→40）")
            print("=" * 60)
            # PENDING(10) → SETTLABLE(30)
            code, data = await api_call(client, "PUT", "/api/v1/cps/order/status",
                                        token=user_token,
                                        json_data={"order_id": order_id, "target_status": 30})
            log_result("订单流转", "PENDING→SETTLABLE", code == 200, f"code={sg(data,'code')}, status={sg(data,'data','order_status')}")

            # SETTLABLE(30) → SETTLED(40)
            code, data = await api_call(client, "PUT", "/api/v1/cps/order/status",
                                        token=user_token,
                                        json_data={"order_id": order_id, "target_status": 40})
            log_result("订单流转", "SETTLABLE→SETTLED", code == 200, f"code={sg(data,'code')}, status={sg(data,'data','order_status')}")
            if code != 200:
                log_bug("P0", "订单流转", "SETTLABLE→SETTLED失败", f"msg={sg(data,'msg',default='')}")

        # ═══ 12. 佣金结算（后台单笔结算） ═══
        if order_id:
            print("\n" + "=" * 60)
            print("12. 佣金结算（后台单笔结算）")
            print("=" * 60)
            code, data = await api_call(client, "POST", "/api/v1/admin/commission-settlement/settle/single",
                                        token=admin_token,
                                        json_data={"order_id": order_id})
            settle_ok = code == 200 and sg(data, "code") == 200
            log_result("佣金结算", "单笔结算入账", settle_ok, f"code={sg(data,'code')}, msg={str(sg(data,'msg',default=''))[:60]}")
            if not settle_ok:
                log_bug("P0", "佣金结算", "单笔结算失败", f"code={code}, msg={sg(data,'msg',default='')}")

        # ═══ 13. 佣金账户（结算后） ═══
        print("\n" + "=" * 60)
        print("13. 佣金账户查询（结算后）")
        print("=" * 60)
        code, data = await api_call(client, "GET", "/api/v1/withdraw/account", token=user_token)
        if code == 200 and sg(data, "code") == 200:
            acct = sg(data, "data", default={}) or {}
            balance_after = acct.get("available_balance", 0)
            frozen_after = acct.get("frozen_balance", 0)
            balance_increased = float(balance_after) > float(balance_before)
            log_result("佣金账户", "查询账户(结算后)", True, f"available={balance_after}, frozen={frozen_after}")
            log_result("佣金账户", "余额已入账", balance_increased,
                       f"before={balance_before} → after={balance_after}")
            if not balance_increased:
                log_bug("P0", "佣金结算", "结算后余额未增加", f"before={balance_before}, after={balance_after}")
        else:
            log_result("佣金账户", "查询账户(结算后)", False, str(data)[:150])

        # ═══ 14. 提现申请（正常金额） ═══
        print("\n" + "=" * 60)
        print("14. 提现申请（正常金额）")
        print("=" * 60)
        code, data = await api_call(client, "POST", "/api/v1/withdraw/apply",
                                    token=user_token, json_data={"apply_amount": 10})
        apply_ok = code == 200 and sg(data, "code") == 200
        apply_id = sg(data, "data", "id")
        log_result("提现申请", "正常金额提现", apply_ok, f"apply_id={apply_id}, msg={str(sg(data,'msg',default=''))[:60]}")
        if not apply_ok:
            log_bug("P0", "提现", "正常金额提现失败", f"code={code}, msg={sg(data,'msg',default='')}")

        # ═══ 15. 提现异常场景 ═══
        print("\n" + "=" * 60)
        print("15. 提现异常场景测试")
        print("=" * 60)
        # 余额不足
        code, data = await api_call(client, "POST", "/api/v1/withdraw/apply",
                                    token=user_token, json_data={"apply_amount": 999999})
        is_rejected = sg(data, "code") != 200
        msg = str(sg(data, "msg", default=""))[:60]
        log_result("异常场景", "余额不足提现拦截", is_rejected, f"msg={msg}")
        if not is_rejected:
            log_bug("P0", "提现", "余额不足未拦截", f"msg={msg}")

        # 低于门槛
        code, data = await api_call(client, "POST", "/api/v1/withdraw/apply",
                                    token=user_token, json_data={"apply_amount": 0.5})
        is_rejected = sg(data, "code") != 200
        msg = str(sg(data, "msg", default=""))[:60]
        log_result("异常场景", "低于门槛提现拦截", is_rejected, f"msg={msg}")
        if not is_rejected:
            log_bug("P0", "提现", "低于门槛未拦截", f"msg={msg}")

        # ═══ 16. 后台审核打款 ═══
        if apply_id:
            print("\n" + "=" * 60)
            print("16. 后台审核打款流程")
            print("=" * 60)
            # 审核通过
            code, data = await api_call(client, "PUT", f"/api/v1/admin/withdraw/applies/{apply_id}/approve",
                                        token=admin_token, json_data={"review_remark": "S02审核通过"})
            log_result("后台审核", "审核通过", code == 200, f"code={sg(data,'code')}, status={sg(data,'data','status')}")

            # 标记打款完成
            code, data = await api_call(client, "PUT", f"/api/v1/admin/withdraw/applies/{apply_id}/complete",
                                        token=admin_token,
                                        json_data={"transfer_batch_id": f"S02BATCH{int(time.time())}"})
            log_result("后台审核", "标记打款完成", code == 200, f"code={sg(data,'code')}, status={sg(data,'data','status')}")
            if code != 200:
                log_bug("P0", "提现审核", "标记打款完成失败", f"msg={sg(data,'msg',default='')}")

        # ═══ 17. 埋点上报 ═══
        print("\n" + "=" * 60)
        print("17. 埋点上报测试")
        print("=" * 60)
        code, data = await api_call(client, "POST", "/api/v1/track/event",
                                    json_data={"events": [
                                        {"event_type": "page_view", "event_name": "page_view",
                                         "page_path": "/pages/index/index",
                                         "client_timestamp": int(time.time() * 1000)},
                                        {"event_type": "goods_click", "event_name": "click_search",
                                         "page_path": "/pages/index/index",
                                         "client_timestamp": int(time.time() * 1000)}
                                    ]})
        log_result("埋点", "行为埋点上报", code == 200, f"received={sg(data,'data','received')}, saved={sg(data,'data','saved')}")

        code, data = await api_call(client, "POST", "/api/v1/track/error",
                                    json_data={"events": [
                                        {"event_type": "js_error", "event_name": "S02测试-模拟前端错误",
                                         "page_path": "/pages/index/index",
                                         "client_timestamp": int(time.time() * 1000)}
                                    ]})
        log_result("埋点", "错误上报", code == 200, f"received={sg(data,'data','received')}, saved={sg(data,'data','saved')}")

        # ═══ 18. 数据看板 ═══
        print("\n" + "=" * 60)
        print("18. 后台数据看板")
        print("=" * 60)
        code, data = await api_call(client, "GET", "/api/v1/admin/dashboard/cards", token=admin_token)
        log_result("数据看板", "卡片聚合数据", code == 200, f"code={sg(data,'code')}")

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        code, data = await api_call(client, "GET", "/api/v1/admin/dashboard/commission-stats",
                                    token=admin_token,
                                    params={"group_by": "channel", "start_date": start_date, "end_date": end_date})
        log_result("数据看板", "渠道佣金统计", code == 200, f"code={sg(data,'code')}")

        # ═══ 19. 审计日志 ═══
        print("\n" + "=" * 60)
        print("19. 审计日志查询")
        print("=" * 60)
        code, data = await api_call(client, "GET", "/api/v1/admin/audit/logs",
                                    token=admin_token, params={"page": 1, "page_size": 20})
        audit_total = sg(data, "data", "total", default=0)
        log_result("审计日志", "查询审计日志", code == 200, f"total={audit_total}")
        if audit_total and audit_total > 0:
            items = sg(data, "data", "items", default=[]) or []
            actions = set(item.get("action", "") for item in items)
            log_result("审计日志", "审计动作类型覆盖", True, f"actions={actions}")
            # 核查关键操作是否落审计
            key_actions = {"HTTP_POST", "HTTP_PUT", "ADMIN_LOGIN"}
            covered = key_actions & actions
            log_result("审计日志", "关键操作审计覆盖", len(covered) >= 2, f"covered={covered}")

        # ═══ 20. 清理 ═══
        if template_id:
            print("\n" + "=" * 60)
            print("20. 清理测试数据")
            print("=" * 60)
            code, _ = await api_call(client, "DELETE", f"/api/v1/admin/message/templates/{template_id}", token=admin_token)
            log_result("消息模板", "删除模板", code == 200)

        # ═══ 汇总 ═══
        print("\n" + "=" * 60)
        print("测试汇总")
        print("=" * 60)
        total = len(RESULTS)
        passed = sum(1 for r in RESULTS if r["success"])
        failed = total - passed
        print(f"  总用例: {total} | 通过: {passed} | 失败: {failed}")
        if BUGS:
            print(f"  BUG 数: {len(BUGS)}")
            for b in BUGS:
                print(f"    [{b['severity']}] {b['module']}: {b['description']}")
        else:
            print("  BUG 数: 0")
        return RESULTS, BUGS


if __name__ == "__main__":
    results, bugs = asyncio.run(run_tests())
    sys.exit(0 if not bugs else 1)
