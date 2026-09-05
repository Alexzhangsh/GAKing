#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王 - Redis缓存清理脚本
# 清理 gaking:prod 前缀的脏数据/过期缓存
#
# 用法：
#   ./clean_redis_cache.sh              # 扫描并预览（dry-run）
#   ./clean_redis_cache.sh --execute    # 实际执行清理
#   ./clean_redis_cache.sh --execute --pattern "gaking:prod:user_account:*"  # 按模式清理
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

# Redis连接配置（从.env读取）
ENV="${REDIS_ENV:-development}"
ENV_FILE="$PROJECT_DIR/backend/.env.${ENV}"

if [ ! -f "$ENV_FILE" ]; then
    ENV_FILE="$PROJECT_DIR/backend/.env.development"
fi

REDIS_HOST=$(grep '^REDIS_HOST=' "$ENV_FILE" | cut -d'=' -f2 || echo "127.0.0.1")
REDIS_PORT=$(grep '^REDIS_PORT=' "$ENV_FILE" | cut -d'=' -f2 || echo "6379")
REDIS_DB=$(grep '^REDIS_DB=' "$ENV_FILE" | cut -d'=' -f2 || echo "0")
REDIS_PASSWORD=$(grep '^REDIS_PASSWORD=' "$ENV_FILE" | cut -d'=' -f2 || echo "")

# Redis CLI 命令前缀
if [ -n "$REDIS_PASSWORD" ]; then
    REDIS_CMD="redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD -n $REDIS_DB"
else
    REDIS_CMD="redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB"
fi

# 参数解析
EXECUTE=false
PATTERN="gaking:prod:*"
for arg in "$@"; do
    case "$arg" in
        --execute) EXECUTE=true ;;
        --pattern=*) PATTERN="${arg#*=}" ;;
        --pattern) shift; PATTERN="${1:-gaking:prod:*}" ;;
    esac
done

log_info()  { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓ $1${NC}"; }
log_warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠ $1${NC}"; }
log_error() { echo -e "${RED}[$(date '+%H:%M:%S')] ✗ $1${NC}"; }
log_step()  { echo -e "${BLUE}[$(date '+%H:%M:%S')] ▶ $1${NC}"; }

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}金角大王Redis缓存清理${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Redis:${NC} $REDIS_HOST:$REDIS_PORT (DB=$REDIS_DB)"
echo -e "${BLUE}匹配模式:${NC} $PATTERN"
echo -e "${BLUE}执行模式:${NC} $([ "$EXECUTE" == "true" ] && echo '执行清理' || echo '预览（dry-run）')"
echo ""

# ── 步骤1: 测试Redis连接 ──
log_step "步骤1/3: 测试Redis连接..."
if ! $REDIS_CMD ping > /dev/null 2>&1; then
    log_error "Redis连接失败: $REDIS_HOST:$REDIS_PORT"
    exit 1
fi
log_info "Redis连接成功"

# ── 步骤2: 扫描匹配的key ──
log_step "步骤2/3: 扫描匹配的key..."

# 使用SCAN避免阻塞（不用KEYS *)
KEYS=$($REDIS_CMD --scan --pattern "$PATTERN" 2>/dev/null || echo "")
KEY_COUNT=$(echo "$KEYS" | grep -c . 2>/dev/null || echo "0")

if [ -z "$KEYS" ] || [ "$KEY_COUNT" -eq 0 ]; then
    log_info "未找到匹配的key: $PATTERN"
    exit 0
fi

log_info "找到 $KEY_COUNT 个匹配的key"

# 分类统计
echo ""
echo "  按类型统计:"
echo "$KEYS" | sed 's/gaking:prod:\([^:]*\).*/\1/' | sort | uniq -c | sort -rn | while read -r count prefix; do
    echo "    $prefix: $count 个"
done

# 预览前20个key
echo ""
echo "  预览（前20个）:"
echo "$KEYS" | head -20 | while read -r key; do
    TTL=$($REDIS_CMD ttl "$key" 2>/dev/null || echo "-1")
    if [ "$TTL" == "-1" ]; then
        TTL_STR="永不过期"
    elif [ "$TTL" == "-2" ]; then
        TTL_STR="已过期"
    else
        TTL_STR="${TTL}s"
    fi
    echo "    $key (TTL: $TTL_STR)"
done

if [ "$KEY_COUNT" -gt 20 ]; then
    echo "    ... 还有 $((KEY_COUNT - 20)) 个"
fi

# ── 步骤3: 执行清理 ──
echo ""
log_step "步骤3/3: 执行清理..."

if ! $EXECUTE; then
    log_warn "当前为预览模式（dry-run），未实际删除"
    log_warn "如需执行清理，请运行: ./clean_redis_cache.sh --execute"
    exit 0
fi

# 生产环境二次确认
if [ "$ENV" == "production" ]; then
    log_error "⚠️ 生产环境缓存清理！"
    read -p "确认清理 $KEY_COUNT 个key？输入 YES 继续: " CONFIRM
    if [ "$CONFIRM" != "YES" ]; then
        log_warn "已取消"
        exit 0
    fi
fi

# 批量删除（每100个一批）
DELETED=0
echo "$KEYS" | while read -r key; do
    $REDIS_CMD del "$key" > /dev/null 2>&1
    DELETED=$((DELETED+1))
    if [ $((DELETED % 100)) -eq 0 ]; then
        log_info "已删除 $DELETED / $KEY_COUNT..."
    fi
done

log_info "清理完成，共删除 $KEY_COUNT 个key"

# 验证
REMAINING=$($REDIS_CMD --scan --pattern "$PATTERN" 2>/dev/null | grep -c . || echo "0")
log_info "剩余匹配key: $REMAINING 个"
