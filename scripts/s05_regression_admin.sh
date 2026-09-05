#!/bin/bash
# @ai-generated
# S05 线上回归测试 - 后台管理 API 全量验证（修正版）
# 用法: bash s05_regression_admin.sh <token>
set -uo pipefail

BASE="http://localhost:3001"
TOKEN="$1"
AUTH="Authorization: Bearer $TOKEN"
PASS=0; FAIL=0; FAILED_ITEMS=""

check() {
  local name="$1" method="$2" path="$3" expect="$4" data="${5:-}"
  local code
  if [ -n "$data" ]; then
    code=$(curl -s -o /tmp/s05_resp.json -w "%{http_code}" -X "$method" "$BASE$path" -H "$AUTH" -H "Content-Type: application/json" -d "$data")
  else
    code=$(curl -s -o /tmp/s05_resp.json -w "%{http_code}" -X "$method" "$BASE$path" -H "$AUTH")
  fi
  if [ "$code" == "$expect" ]; then
    PASS=$((PASS+1)); echo "  ✅ PASS | $name | HTTP $code"
  else
    FAIL=$((FAIL+1)); FAILED_ITEMS="$FAILED_ITEMS\n    ❌ $name | HTTP $code (期望 $expect) | $(head -c 150 /tmp/s05_resp.json)"
    echo "  ❌ FAIL | $name | HTTP $code (期望 $expect)"
  fi
}

echo "=================================================="
echo "S05 后台管理 API 回归测试（修正版）"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

echo ""
echo "▸ 1. 认证与管理员"
check "管理员信息" GET "/api/v1/admin/auth/me" "200"
check "RBAC角色列表" GET "/api/v1/admin/rbac/roles" "200"
check "RBAC菜单树" GET "/api/v1/admin/rbac/menus/tree" "200"
check "RBAC权限码" GET "/api/v1/admin/rbac/permissions" "200"
check "管理员列表" GET "/api/v1/admin/rbac/users" "200"

echo ""
echo "▸ 2. 数据大盘"
check "大盘卡片" GET "/api/v1/admin/dashboard/cards" "200"
check "订单趋势" GET "/api/v1/admin/dashboard/order-trend?start_date=2026-08-01&end_date=2026-08-15" "200"
check "提现趋势" GET "/api/v1/admin/dashboard/withdraw-trend?start_date=2026-08-01&end_date=2026-08-15" "200"
check "佣金统计" GET "/api/v1/admin/dashboard/commission-stats?group_by=date&start_date=2026-08-01&end_date=2026-08-15" "200"

echo ""
echo "▸ 3. 审计日志"
check "审计日志列表" GET "/api/v1/admin/audit/logs?page=1&page_size=5" "200"

echo ""
echo "▸ 4. 渠道配置(F04)"
check "渠道列表" GET "/api/v1/admin/channel/list" "200"
check "渠道详情" GET "/api/v1/admin/channel/detail?channel_code=myq" "200"
check "渠道密钥测试" POST "/api/v1/admin/channel/test-key" "200" '{"channel_code":"myq","api_token":"test"}'

echo ""
echo "▸ 5. 营销消息(F04)"
check "消息模板列表" GET "/api/v1/admin/message/templates?page=1&page_size=5" "200"
check "推送记录列表" GET "/api/v1/admin/message/push-records?page=1&page_size=5" "200"
check "订阅绑定列表" GET "/api/v1/admin/message/subscriptions?page=1&page_size=5" "200"

echo ""
echo "▸ 6. 商品管理(F01)"
check "商品列表" GET "/api/v1/admin/goods?page=1&page_size=5" "200"

echo ""
echo "▸ 7. 订单管理(F02)"
check "订单列表" GET "/api/v1/admin/b13/orders?page=1&page_size=5" "200"
check "异常订单列表" GET "/api/v1/admin/abnormal-orders/list?page=1&page_size=5" "200"
check "结算订单列表" GET "/api/v1/admin/commission-settlement/orders?page=1&page_size=5" "200"

echo ""
echo "▸ 8. 提现管理(F02)"
check "提现申请列表" GET "/api/v1/admin/withdraw/applies?page=1&page_size=5" "200"

echo ""
echo "▸ 9. 用户管理(F02)"
check "用户列表" GET "/api/v1/admin/users-manage?page=1&page_size=5" "200"

echo ""
echo "▸ 10. 佣金结算"
check "结算流水" GET "/api/v1/admin/commission-settlement/flows?page=1&page_size=5" "200"
check "结算记录" GET "/api/v1/admin/settlement/settlements?page=1&page_size=5" "200"
check "结算操作日志" GET "/api/v1/admin/settlement/operation-logs?page=1&page_size=5" "200"

echo ""
echo "▸ 11. 订单同步管理(B05)"
check "同步状态" GET "/api/v1/admin/order-sync/status" "200"
check "定时任务日志" GET "/api/v1/admin/scheduled-task-run-logs?page=1&page_size=5" "200"

echo ""
echo "▸ 12. 系统配置"
check "系统配置列表" GET "/api/v1/admin/config/list" "200"
check "配置注册表" GET "/api/v1/admin/config/registry" "200"

echo ""
echo "▸ 13. 对账与状态机"
check "对账差异列表" GET "/api/v1/admin/reconciliation/diffs?page=1&page_size=5" "200"
check "对账记录" GET "/api/v1/admin/reconciliation/records?page=1&page_size=5" "200"

echo ""
echo "▸ 14. 逆向冲减与资产"
check "逆向冲减记录" GET "/api/v1/admin/b07/reverse-commission/records?page=1&page_size=5" "200"
check "资金流水" GET "/api/v1/admin/b08/fund-flows?page=1&page_size=5" "200"

echo ""
echo "=================================================="
echo "通过: $PASS  失败: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "失败明细:$FAILED_ITEMS"
fi
echo "=================================================="
