#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王CPS - 生产部署前置校验脚本（S04-9 升级版）
# 校验内容：
#   1. .env.production 文件存在性
#   2. 未填充占位符 {{XXX}} 扫描
#   3. JWT_SECRET 强度（≥64位）
#   4. CORS 生产安全（禁止通配符）
#   5. 端口配置检查（3003）
#   6. 关键业务参数非空
#   7. deploy/.env Redis 密码
#   8. Docker 环境可用性
#   9. 端口 3003/8080 占用检查
#  10. MySQL/Redis 连通性
#  11. 前端 Dockerfile 存在性
#  12. docker-compose 资源限制配置完整性
#  13. 日志目录可写性
#  14. 后端 Dockerfile 存在性
#  15. docker-entrypoint.sh 存在性
#  S04-9 新增：
#  16. 密钥完整性校验（全部必需密钥存在且非占位符）
#  17. Nginx 配置校验（占位符扫描 + nginx -t 语法校验）
#  18. 容器资源参数校验（cpus/memory/健康检查超时重试）
#  19. 数据库初始化数据校验（调用 pre_check_db.py，含31权限码遍历）
#  20. 标准化预检报告输出（文本 + JSON）
#
# 用法：
#   ./scripts/pre_deploy_check.sh              # 本地校验
#   ./scripts/pre_deploy_check.sh --remote     # 在生产服务器上执行（含DB/端口/连通性）
#   ./scripts/pre_deploy_check.sh --with-db    # 本地执行时也做数据库预检
# 退出码：0=全部通过，1=存在阻塞项
# ============================================================
set -u

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$PROJECT_DIR/backend/.env.production"
DEPLOY_ENV="$PROJECT_DIR/deploy/.env"
ADMIN_DIR="$PROJECT_DIR/admin"
BACKEND_DIR="$PROJECT_DIR/backend"
DEPLOY_DIR="$PROJECT_DIR/deploy"
NGINX_CONF="$DEPLOY_DIR/nginx/gaking.conf"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.yml"
REPORT_DIR="$PROJECT_DIR/deploy/precheck-reports"
REPORT_JSON="$REPORT_DIR/precheck-report-$(date +%Y%m%d-%H%M%S).json"

# 防御性初始化（set -u 下避免 unbound）
DB_REPORT=""
PY_BIN="python3"

PASS=0
FAIL=0
WARN=0

# 标准化报告结果数组（每项: name|status|detail）
REPORT_ITEMS=()

ok()   { echo -e "${GREEN}[PASS]${NC} $1"; PASS=$((PASS+1)); REPORT_ITEMS+=("$1|PASS|$2"); }
fail() { echo -e "${RED}[FAIL]${NC} $1"; FAIL=$((FAIL+1)); REPORT_ITEMS+=("$1|FAIL|$2"); }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; WARN=$((WARN+1)); REPORT_ITEMS+=("$1|WARN|$2"); }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE} 金角大王CPS - 生产部署前置校验（S04-9）${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# ── 1. .env.production 文件存在 ──
if [[ -f "$ENV_FILE" ]]; then
    ok ".env.production 存在" "文件存在: $ENV_FILE"
else
    fail ".env.production 存在" "文件缺失: $ENV_FILE"
    exit 1
fi

# ── 2. 扫描未填充占位符 {{XXX}} ──
info "扫描 .env.production 未填充占位符..."
PLACEHOLDERS=$(grep -oE '\{\{[A-Z_]+\}\}' "$ENV_FILE" | sort -u)
if [[ -z "$PLACEHOLDERS" ]]; then
    ok "占位符扫描" ".env.production 无 {{XXX}} 占位符"
else
    echo -e "${RED}[FAIL]${NC} 以下占位符未填充（需在服务器上填入真实值）："
    echo "$PLACEHOLDERS" | sed 's/^/      - /'
    fail "占位符扫描" "存在未填充占位符: $(echo "$PLACEHOLDERS" | tr '\n' ' ')"
fi

# ── 3. JWT_SECRET 强度校验 ──
JWT_SECRET=$(grep -E '^JWT_SECRET=' "$ENV_FILE" | cut -d'=' -f2-)
JWT_LEN=${#JWT_SECRET}
if [[ $JWT_LEN -ge 64 ]]; then
    ok "JWT_SECRET 强度" "长度 ${JWT_LEN} ≥ 64"
else
    fail "JWT_SECRET 强度" "长度 ${JWT_LEN} < 64（红线：必须≥64位）"
fi

# ── 4. CORS 禁止通配符 ──
CORS=$(grep -E '^CORS_ORIGINS=' "$ENV_FILE" | cut -d'=' -f2-)
if [[ "$CORS" == *"*"* ]]; then
    fail "CORS_ORIGINS 安全" "含通配符 *（红线：生产环境禁止）"
elif [[ -z "$CORS" || "$CORS" == *"{{"* ]]; then
    warn "CORS_ORIGINS 安全" "未配置或仍为占位符"
else
    ok "CORS_ORIGINS 安全" "无通配符: $CORS"
fi

# ── 5. 端口 3003 配置 ──
PORT=$(grep -E '^PORT=' "$ENV_FILE" | cut -d'=' -f2)
if [[ "$PORT" == "3003" ]]; then
    ok "端口配置" "PORT=3003（避开 3001 占用）"
else
    warn "端口配置" "PORT=${PORT}（预期 3003，3001 被现有项目占用）"
fi

# ── 6. 关键业务参数非空 ──
for key in DB_HOST DB_USERNAME DB_PASSWORD DB_DATABASE MIAO_QUAN_TOKEN WX_MINI_APPID WX_MINI_SECRET; do
    val=$(grep -E "^${key}=" "$ENV_FILE" | cut -d'=' -f2-)
    if [[ -z "$val" || "$val" == *"{{"* ]]; then
        fail "密钥[${key}]" "未配置或为占位符"
    else
        ok "密钥[${key}]" "已配置"
    fi
done

# ── 7. deploy/.env（Redis 容器密码）──
if [[ -f "$DEPLOY_ENV" ]]; then
    REDIS_PWD=$(grep -E '^REDIS_PASSWORD=' "$DEPLOY_ENV" | cut -d'=' -f2-)
    if [[ -z "$REDIS_PWD" || "$REDIS_PWD" == "CHANGE_ME_TO_STRONG_PASSWORD" ]]; then
        fail "deploy/.env REDIS_PASSWORD" "仍为默认值，需修改"
    else
        ok "deploy/.env REDIS_PASSWORD" "已设置"
    fi
else
    warn "deploy/.env" "不存在（需 cp deploy/.env.example deploy/.env 并填入 REDIS_PASSWORD）"
fi

# ── 8. Docker 环境（仅在 --remote 或服务器上检查）──
if [[ "${1:-}" == "--remote" ]] || command -v docker &>/dev/null; then
    if command -v docker &>/dev/null; then
        ok "Docker 环境" "已安装: $(docker --version)"
        if docker compose version &>/dev/null; then
            ok "Docker Compose" "插件可用"
        elif command -v docker-compose &>/dev/null; then
            ok "Docker Compose" "已安装: $(docker-compose --version)"
        else
            fail "Docker Compose" "不可用（需安装 docker compose 插件或 docker-compose）"
        fi
    else
        fail "Docker 环境" "未安装"
    fi
fi

# ── 9. 端口 3003/8080 占用检查（服务器侧）──
if [[ "${1:-}" == "--remote" ]]; then
    if ss -tlnp 2>/dev/null | grep -q ':3003 '; then
        warn "端口 3003" "已被占用（可能 backend 已在运行）"
    else
        ok "端口 3003" "空闲"
    fi
    if ss -tlnp 2>/dev/null | grep -q ':8080 '; then
        warn "端口 8080" "已被占用（可能 admin 前端已在运行）"
    else
        ok "端口 8080" "空闲"
    fi
fi

# ── 10. MySQL 连通性（服务器侧）──
if [[ "${1:-}" == "--remote" ]]; then
    DB_HOST_VAL=$(grep -E '^DB_HOST=' "$ENV_FILE" | cut -d'=' -f2)
    if timeout 5 bash -c "echo > /dev/tcp/${DB_HOST_VAL}/3306" 2>/dev/null; then
        ok "MySQL 连通性" "${DB_HOST_VAL}:3306 可达"
    else
        fail "MySQL 连通性" "${DB_HOST_VAL}:3306 不可达"
    fi
fi

# ── 11. 前端 Dockerfile 存在性 ──
if [[ -f "$ADMIN_DIR/Dockerfile" ]]; then
    ok "前端 Dockerfile" "存在: $ADMIN_DIR/Dockerfile"
else
    fail "前端 Dockerfile" "不存在: $ADMIN_DIR/Dockerfile"
fi

# ── 12. docker-compose 文件存在性 ──
if [[ -f "$COMPOSE_FILE" ]]; then
    ok "docker-compose.yml" "存在"
    # 检查资源限制配置
    if grep -q "cpus:" "$COMPOSE_FILE" && grep -q "memory:" "$COMPOSE_FILE"; then
        ok "docker-compose 资源限制" "cpus/memory 已配置"
    else
        warn "docker-compose 资源限制" "未配置（cpus/memory）"
    fi
else
    fail "docker-compose.yml" "不存在: $COMPOSE_FILE"
fi

# ── 13. 日志目录可写性 ──
LOG_DIR="$BACKEND_DIR/logs"
if [[ -d "$LOG_DIR" ]]; then
    if [[ -w "$LOG_DIR" ]]; then
        ok "日志目录" "可写: $LOG_DIR"
    else
        fail "日志目录" "不可写: $LOG_DIR"
    fi
else
    if mkdir -p "$LOG_DIR" 2>/dev/null; then
        ok "日志目录" "已创建: $LOG_DIR"
    else
        fail "日志目录" "创建失败: $LOG_DIR"
    fi
fi

# ── 14. 后端 Dockerfile 存在性 ──
if [[ -f "$BACKEND_DIR/Dockerfile" ]]; then
    ok "后端 Dockerfile" "存在: $BACKEND_DIR/Dockerfile"
else
    fail "后端 Dockerfile" "不存在: $BACKEND_DIR/Dockerfile"
fi

# ── 15. docker-entrypoint.sh 存在性 ──
if [[ -f "$BACKEND_DIR/docker-entrypoint.sh" ]]; then
    ok "docker-entrypoint.sh" "存在"
    if [[ -x "$BACKEND_DIR/docker-entrypoint.sh" ]]; then
        ok "docker-entrypoint.sh" "可执行"
    else
        warn "docker-entrypoint.sh" "不可执行（需 chmod +x）"
    fi
else
    fail "docker-entrypoint.sh" "不存在"
fi

# ════════════════════════════════════════════════════════════
# S04-9 新增校验
# ════════════════════════════════════════════════════════════

# ── 16. 密钥完整性校验（全部必需密钥存在且非占位符）──
info "校验密钥完整性..."
# 必填密钥（生产必须真实值）
REQUIRED_KEYS=(
    "DB_HOST" "DB_PORT" "DB_USERNAME" "DB_PASSWORD" "DB_DATABASE"
    "REDIS_HOST" "REDIS_PORT"
    "JWT_SECRET" "CORS_ORIGINS"
    "CDN_IMG_BASE_URL" "OBS_ACCESS_KEY_ID" "OBS_SECRET_ACCESS_KEY" "OBS_ENDPOINT" "OBS_BUCKET_NAME"
    "MIAO_QUAN_TOKEN" "MIAO_QUAN_TBNAME" "MIAO_QUAN_PID"
    "WX_MINI_APPID" "WX_MINI_SECRET"
    "SCHEDULER_ENABLE"
)
# 可选密钥（渠道停用时可留空，但不得为占位符）
OPTIONAL_KEYS=(
    "DATAOK_APPID" "DATAOK_APPKEY" "ORDERX_TOKEN"
)

MISSING_REQUIRED=()
for key in "${REQUIRED_KEYS[@]}"; do
    val=$(grep -E "^${key}=" "$ENV_FILE" | cut -d'=' -f2-)
    if [[ -z "$val" || "$val" == *"{{"* ]]; then
        MISSING_REQUIRED+=("$key")
    fi
done

if [[ ${#MISSING_REQUIRED[@]} -gt 0 ]]; then
    fail "密钥完整性" "必填密钥缺失/占位: ${MISSING_REQUIRED[*]}"
else
    ok "密钥完整性" "全部 ${#REQUIRED_KEYS[@]} 项必填密钥已配置且非占位符"
fi

# 可选密钥：停用渠道允许留空，但占位符需告警
for key in "${OPTIONAL_KEYS[@]}"; do
    val=$(grep -E "^${key}=" "$ENV_FILE" | cut -d'=' -f2-)
    if [[ "$val" == *"{{"* ]]; then
        warn "密钥[${key}]" "仍为占位符（停用渠道可留空，但不得为 {{}}）"
    fi
done

# ── 17. Nginx 配置校验（占位符扫描 + nginx -t 语法校验）──
info "校验 Nginx 配置..."
if [[ -f "$NGINX_CONF" ]]; then
    # 17a. 占位符扫描
    NGINX_PLACEHOLDERS=$(grep -oE '\{\{[A-Z_]+\}\}' "$NGINX_CONF" | sort -u)
    if [[ -z "$NGINX_PLACEHOLDERS" ]]; then
        ok "Nginx 占位符" "gaking.conf 无 {{XXX}} 占位符"
    else
        warn "Nginx 占位符" "存在待替换占位符: $(echo "$NGINX_PLACEHOLDERS" | tr '\n' ' ')"
    fi

    # 17b. 关键配置项存在性
    NGINX_CRITICAL=("listen 443 ssl" "ssl_certificate" "limit_req_zone" "robots.txt" "proxy_read_timeout")
    NGINX_MISSING=()
    for pat in "${NGINX_CRITICAL[@]}"; do
        if ! grep -qF "$pat" "$NGINX_CONF"; then
            NGINX_MISSING+=("$pat")
        fi
    done
    if [[ ${#NGINX_MISSING[@]} -gt 0 ]]; then
        fail "Nginx 关键配置" "缺失: ${NGINX_MISSING[*]}"
    else
        ok "Nginx 关键配置" "HTTPS/证书/限流/robots/超时均已配置"
    fi

    # 17c. nginx -t 语法校验（仅服务器上有 nginx 时）
    if command -v nginx &>/dev/null; then
        # 用临时文件替换占位符后做语法校验（避免占位符导致 nginx -t 失败）
        TMP_CONF=$(mktemp)
        sed -E 's/\{\{[A-Z_]+\}\}/PLACEHOLDER/g' "$NGINX_CONF" > "$TMP_CONF"
        if nginx -t -c "$TMP_CONF" >/dev/null 2>&1; then
            ok "Nginx 语法" "nginx -t 通过（占位符已临时替换）"
        else
            warn "Nginx 语法" "nginx -t 未通过（占位符替换后仍有语法问题，需人工检查）"
        fi
        rm -f "$TMP_CONF"
    else
        info "本机未安装 nginx，跳过 nginx -t 语法校验（生产服务器上执行 --remote 时校验）"
    fi
else
    fail "Nginx 配置" "gaking.conf 不存在: $NGINX_CONF"
fi

# ── 18. 容器资源参数校验（cpus/memory/健康检查超时重试）──
info "校验容器资源参数..."
if [[ -f "$COMPOSE_FILE" ]]; then
    # 18a. 资源限制
    RESOURCE_OK=1
    for svc in redis backend admin; do
        if ! grep -qE "^  ${svc}:" "$COMPOSE_FILE"; then
            continue
        fi
        # 提取该服务块（状态机：跳过服务头行，到下一个 2 空格缩进键停止）
        BLOCK=$(awk -v svc="$svc" '$0 ~ "^  " svc ":" {in_block=1; next} in_block && $0 ~ "^  [a-z]" {in_block=0} in_block {print}' "$COMPOSE_FILE")
        if ! echo "$BLOCK" | grep -q "cpus:" || ! echo "$BLOCK" | grep -q "memory:"; then
            RESOURCE_OK=0
            warn "容器资源[${svc}]" "未配置 cpus/memory 资源限制"
        fi
    done
    if [[ $RESOURCE_OK -eq 1 ]]; then
        ok "容器资源限制" "redis/backend/admin 均配置 cpus/memory"
    fi

    # 18b. 健康检查参数（backend 启动慢，需合理超时/重试）
    HC_OK=1
    for svc in redis backend admin; do
        BLOCK=$(awk -v svc="$svc" '$0 ~ "^  " svc ":" {in_block=1; next} in_block && $0 ~ "^  [a-z]" {in_block=0} in_block {print}' "$COMPOSE_FILE")
        if ! echo "$BLOCK" | grep -q "healthcheck:"; then
            HC_OK=0
            warn "健康检查[${svc}]" "未配置 healthcheck"
            continue
        fi
        if ! echo "$BLOCK" | grep -q "start_period:"; then
            HC_OK=0
            warn "健康检查[${svc}]" "未配置 start_period（启动宽限期）"
        fi
    done
    if [[ $HC_OK -eq 1 ]]; then
        ok "健康检查参数" "redis/backend/admin 均配置 healthcheck + start_period"
    fi

    # 18c. 日志持久化挂载
    if grep -q "max-size:" "$COMPOSE_FILE" && grep -q "max-file:" "$COMPOSE_FILE"; then
        ok "日志持久化" "容器日志轮转已配置（max-size/max-file）"
    else
        warn "日志持久化" "未配置容器日志轮转"
    fi
else
    fail "容器资源参数" "docker-compose.yml 不存在"
fi

# ── 19. 数据库初始化数据校验（调用 pre_check_db.py）──
# 触发条件：--remote（生产服务器）或 --with-db（本地显式指定）
if [[ "${1:-}" == "--remote" || "${1:-}" == "--with-db" ]]; then
    info "执行数据库初始化数据预检（pre_check_db.py）..."
    PRE_CHECK_PY="$BACKEND_DIR/scripts/pre_check_db.py"
    if [[ -f "$PRE_CHECK_PY" ]]; then
        DB_REPORT="$REPORT_DIR/precheck-db-$(date +%Y%m%d-%H%M%S).json"
        mkdir -p "$REPORT_DIR"
        # 生产 Docker 部署：优先在容器内执行（依赖齐全，避免宿主机 python 环境缺失）
        if command -v docker &>/dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^gaking-backend$'; then
            if docker exec gaking-backend python /app/scripts/pre_check_db.py >/dev/null 2>&1; then
                ok "数据库初始化数据" "pre_check_db.py 通过（容器内执行）"
            else
                fail "数据库初始化数据" "pre_check_db.py 存在失败项（容器内执行）"
            fi
        else
            # 本地/非容器：优先项目虚拟环境，其次系统 python3
            if [[ -x "$BACKEND_DIR/.venv_new/bin/python" ]]; then
                PY_BIN="$BACKEND_DIR/.venv_new/bin/python"
            elif [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
                PY_BIN="$BACKEND_DIR/.venv/bin/python"
            else
                PY_BIN="python3"
            fi
            if (cd "$BACKEND_DIR" && env -u PYTHONHOME -u PYTHONPATH "$PY_BIN" scripts/pre_check_db.py --json "$DB_REPORT"); then
                ok "数据库初始化数据" "pre_check_db.py 通过（详见 ${DB_REPORT}）"
            else
                fail "数据库初始化数据" "pre_check_db.py 存在失败项（详见 ${DB_REPORT}）"
            fi
        fi
    else
        fail "数据库初始化数据" "pre_check_db.py 不存在: $PRE_CHECK_PY"
    fi
else
    info "跳过数据库预检（使用 --remote 或 --with-db 开启）"
fi

# ════════════════════════════════════════════════════════════
# 20. 标准化预检报告输出
# ════════════════════════════════════════════════════════════
mkdir -p "$REPORT_DIR"

# 生成 JSON 报告
{
    echo "{"
    echo "  \"script\": \"pre_deploy_check\","
    echo "  \"version\": \"S04-9\","
    echo "  \"timestamp\": \"$(date '+%Y-%m-%d %H:%M:%S')\","
    echo "  \"mode\": \"${1:-local}\","
    echo "  \"summary\": {\"pass\": $PASS, \"fail\": $FAIL, \"warn\": $WARN},"
    echo "  \"result\": $([ $FAIL -gt 0 ] && echo '"FAIL"' || echo '"PASS"'),"
    echo "  \"checks\": ["
    FIRST=1
    for item in "${REPORT_ITEMS[@]}"; do
        IFS='|' read -r name status detail <<< "$item"
        if [[ $FIRST -eq 0 ]]; then echo ","; fi
        FIRST=0
        # 转义 JSON 特殊字符
        name_esc=$(echo "$name" | sed 's/\\/\\\\/g; s/"/\\"/g')
        detail_esc=$(echo "$detail" | sed 's/\\/\\\\/g; s/"/\\"/g')
        echo -n "    {\"name\": \"$name_esc\", \"status\": \"$status\", \"detail\": \"$detail_esc\"}"
    done
    echo ""
    echo "  ]"
    echo "}"
} > "$REPORT_JSON"

# ── 汇总 ──
echo ""
echo -e "${BLUE}------------------------------------------------------------${NC}"
echo -e " 通过: ${GREEN}${PASS}${NC}  失败: ${RED}${FAIL}${NC}  警告: ${YELLOW}${WARN}${NC}"
echo -e "${BLUE}------------------------------------------------------------${NC}"
echo -e "${BLUE}[INFO]${NC} 预检报告: $REPORT_JSON"

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}✗ 存在 ${FAIL} 个阻塞项，请修复后再进入 S05 线上回归验收${NC}"
    exit 1
else
    echo -e "${GREEN}✓ 前置校验通过（${WARN} 个警告可酌情处理），可进入 S05 线上回归验收${NC}"
    exit 0
fi
