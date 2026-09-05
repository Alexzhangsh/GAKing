#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王 - 生产环境健康检查脚本
# 逐项校验所有API路由可访问性 + MySQL/Redis/OBS连通性
#
# 用法：
#   ./health_check.sh              # 检查本地服务
#   ./health_check.sh prod         # 检查生产环境
#   ./health_check.sh http://api.example.com  # 检查指定地址
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# bash算术返回1时不算失败（PASS++等场景）
safe_increment() { : $(( ${1}++ )); }

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

# 确定目标地址
if [[ "${1:-}" == "prod" ]]; then
    BASE_URL=$(grep -E '^API_BASE_URL|^CDN_IMG_BASE_URL' "$PROJECT_DIR/backend/.env.production" 2>/dev/null | head -1 | cut -d'=' -f2 || echo "http://localhost:3001")
    # 如果是CDN URL，回退到本地
    [[ "$BASE_URL" == http* ]] || BASE_URL="http://localhost:3001"
elif [[ "${1:-}" == http* ]]; then
    BASE_URL="$1"
else
    BASE_URL="http://localhost:3001"
fi

PASS=0
FAIL=0
WARN=0

log_pass() { echo -e "  ${GREEN}✅ PASS${NC} | $1"; PASS=$((PASS+1)); }
log_fail() { echo -e "  ${RED}❌ FAIL${NC} | $1 | $2"; FAIL=$((FAIL+1)); }
log_warn() { echo -e "  ${YELLOW}⚠️  WARN${NC} | $1 | $2"; WARN=$((WARN+1)); }

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}金角大王生产环境健康检查${NC}"
echo -e "${BLUE}目标: $BASE_URL${NC}"
echo -e "${BLUE}时间: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}================================================${NC}"

# ── 1. 基础健康检查 ──
echo ""
echo "▸ 1. 基础健康检查"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/healthz" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" == "200" ]; then
    RESP=$(curl -s "$BASE_URL/healthz" 2>/dev/null)
    log_pass "/healthz → $RESP"
else
    log_fail "/healthz" "HTTP $HTTP_CODE"
fi

# ── 2. 就绪检查（MySQL/Redis/OBS） ──
echo ""
echo "▸ 2. 就绪检查（MySQL/Redis/OBS连通性）"
READY_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/readyz" 2>/dev/null || echo "000")
if [ "$READY_CODE" == "200" ]; then
    READY_RESP=$(curl -s "$BASE_URL/readyz" 2>/dev/null)
    MYSQL_STATUS=$(echo "$READY_RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('checks',{}).get('mysql',{}).get('status','unknown'))" 2>/dev/null || echo "unknown")
    REDIS_STATUS=$(echo "$READY_RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('checks',{}).get('redis',{}).get('status','unknown'))" 2>/dev/null || echo "unknown")
    OBS_STATUS=$(echo "$READY_RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('checks',{}).get('obs',{}).get('status','unknown'))" 2>/dev/null || echo "unknown")

    [ "$MYSQL_STATUS" == "connected" ] && log_pass "MySQL 连通" || log_fail "MySQL 连通" "status=$MYSQL_STATUS"
    [ "$REDIS_STATUS" == "connected" ] && log_pass "Redis 连通" || log_fail "Redis 连通" "status=$REDIS_STATUS"
    [ "$OBS_STATUS" == "connected" ] && log_pass "OBS 连通" || log_warn "OBS 连通" "status=$OBS_STATUS（非阻塞）"
else
    log_fail "/readyz" "HTTP $READY_CODE"
fi

# ── 3. 关键路由可访问性 ──
echo ""
echo "▸ 3. 关键路由可访问性"

check_route() {
    local method="$1"
    local path="$2"
    local desc="$3"
    local actual_code
    actual_code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$BASE_URL$path" 2>/dev/null || echo "000")
    # 401/403/422 都算路由可达（说明路由存在但需要认证/参数）
    if [ "$actual_code" != "000" ] && [ "$actual_code" != "404" ]; then
        log_pass "$desc (HTTP $actual_code)"
    else
        log_fail "$desc" "HTTP $actual_code"
    fi
}

# C端公开接口
check_route "GET"  "/api/public/goods/search?keyword=test&page=1&size=1" "C端-商品搜索"
check_route "POST" "/api/public/goods/convert-link" "C端-链接转链"

# C端认证接口
check_route "POST" "/api/v1/user/auth/mock-login" "C端-用户登录"

# C端业务接口（需Token，预期401）
check_route "GET"  "/api/v1/withdraw/account" "C端-佣金账户"
check_route "POST" "/api/v1/withdraw/apply" "C端-提现申请"
check_route "GET"  "/api/v1/cps/order" "C端-订单列表"

# 埋点接口（匿名）
check_route "POST" "/api/v1/track/event" "埋点-行为上报"
check_route "POST" "/api/v1/track/error" "埋点-错误上报"

# 后台管理接口（需Admin Token，预期401）
check_route "POST" "/api/v1/admin/auth/login" "后台-管理员登录"
check_route "GET"  "/api/v1/admin/dashboard/cards" "后台-数据看板"
check_route "GET"  "/api/v1/admin/audit/logs" "后台-审计日志"
check_route "GET"  "/api/v1/admin/message/templates" "后台-F04消息模板"
check_route "GET"  "/api/v1/admin/channel/list" "后台-F04渠道配置"
check_route "GET"  "/api/v1/admin/withdraw/applies" "后台-提现审核"
check_route "GET"  "/api/v1/admin/commission-settlement/flows" "后台-佣金结算"

# ── 4. 监控指标 ──
echo ""
echo "▸ 4. Prometheus 监控指标"
METRICS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/metrics" 2>/dev/null || echo "000")
if [ "$METRICS_CODE" == "200" ]; then
    METRICS=$(curl -s "$BASE_URL/metrics" 2>/dev/null)
    UPTIME=$(echo "$METRICS" | grep "gaking_uptime_seconds" | awk '{print $2}' || echo "0")
    REQUESTS=$(echo "$METRICS" | grep "gaking_requests_total" | awk '{print $2}' || echo "0")
    ERRORS=$(echo "$METRICS" | grep "gaking_errors_total" | awk '{print $2}' || echo "0")
    log_pass "/metrics → uptime=${UPTIME}s, requests=$REQUESTS, errors=$ERRORS"
else
    log_fail "/metrics" "HTTP $METRICS_CODE"
fi

# ── 5. 管理员登录功能验证 ──
echo ""
echo "▸ 5. 管理员登录功能验证"
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/api/v1/admin/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin@12345"}' 2>/dev/null || echo "{}")
LOGIN_CODE=$(echo "$LOGIN_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('code',0))" 2>/dev/null || echo "0")
if [ "$LOGIN_CODE" == "200" ]; then
    ROLE=$(echo "$LOGIN_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('data',{}).get('role_name',''))" 2>/dev/null || echo "")
    log_pass "管理员登录成功 (role=$ROLE)"
else
    log_fail "管理员登录" "code=$LOGIN_CODE"
fi

# ── 汇总 ──
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}健康检查汇总${NC}"
echo -e "${BLUE}================================================${NC}"
TOTAL=$((PASS + FAIL + WARN))
echo -e "  总检查项: $TOTAL"
echo -e "  ${GREEN}通过: $PASS${NC}"
echo -e "  ${RED}失败: $FAIL${NC}"
echo -e "  ${YELLOW}警告: $WARN${NC}"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}❌ 健康检查未通过，存在 $FAIL 个失败项${NC}"
    exit 1
else
    echo -e "${GREEN}✅ 健康检查全部通过${NC}"
    exit 0
fi
