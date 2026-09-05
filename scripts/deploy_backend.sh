#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王CPS返利小程序 - 后端一键部署脚本
# 支持环境：dev / test / prod
# 功能：env检查 → 依赖安装 → 数据库迁移 → 服务启动 → 回滚机制
#
# 用法：
#   ./deploy_backend.sh prod    # 部署生产环境
#   ./deploy_backend.sh dev     # 部署开发环境
#   ./deploy_backend.sh test    # 部署测试环境
#   ./deploy_backend.sh prod --rollback  # 回滚上次部署
# ============================================================

set -euo pipefail

# ── 颜色定义 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ── 路径常量 ──
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_DIR="$BACKEND_DIR/logs"
PID_FILE="$LOG_DIR/backend.pid"
BACKUP_DIR="$BACKEND_DIR/.deploy_backup"

# ── 参数解析 ──
ENV="${1:-dev}"
ROLLBACK=false
if [[ "${2:-}" == "--rollback" ]]; then
    ROLLBACK=true
fi

# ── 环境映射 ──
case "$ENV" in
    dev)
        ENV_FILE=".env.development"
        START_SCRIPT="start_dev.sh"
        ;;
    test)
        ENV_FILE=".env.test"
        START_SCRIPT="start_test.sh"
        ;;
    prod)
        ENV_FILE=".env.production"
        START_SCRIPT="start_prod.sh"
        ;;
    *)
        echo -e "${RED}✗ 未知环境: $ENV（支持: dev / test / prod）${NC}"
        exit 1
        ;;
esac

ENV_PATH="$BACKEND_DIR/$ENV_FILE"

# ── 工具函数 ──
log_info()  { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓ $1${NC}"; }
log_warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠ $1${NC}"; }
log_error() { echo -e "${RED}[$(date '+%H:%M:%S')] ✗ $1${NC}"; }
log_step()  { echo -e "${BLUE}[$(date '+%H:%M:%S')] ▶ $1${NC}"; }

# ════════════════════════════════════════════════════
# 回滚流程
# ════════════════════════════════════════════════════
if $ROLLBACK; then
    log_step "开始回滚部署..."
    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "无备份目录，无法回滚: $BACKUP_DIR"
        exit 1
    fi

    # 停止当前服务
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        kill "$OLD_PID" 2>/dev/null || true
        log_info "已停止旧服务 (PID: $OLD_PID)"
    fi

    # 恢复备份的 .env
    if [ -f "$BACKUP_DIR/.env.last" ]; then
        cp "$BACKUP_DIR/.env.last" "$ENV_PATH"
        log_info "已恢复 .env 配置"
    fi

    # 数据库迁移回滚（回退一个版本）
    cd "$BACKEND_DIR"
    export DOTENV_PATH="$ENV_FILE"
    export ENVIRONMENT="$ENV"
    alembic downgrade -1 2>/dev/null && log_info "数据库迁移已回退一个版本" || log_warn "数据库回退跳过（可能已是初始版本）"

    # 重启服务
    mkdir -p "$LOG_DIR"
    nohup bash "$START_SCRIPT" > "$LOG_DIR/backend.log" 2>&1 &
    NEW_PID=$!
    echo "$NEW_PID" > "$PID_FILE"
    log_info "回滚完成，服务已重启 (PID: $NEW_PID)"
    exit 0
fi

# ════════════════════════════════════════════════════
# 正常部署流程
# ════════════════════════════════════════════════════
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}金角大王后端部署 [环境: $ENV]${NC}"
echo -e "${BLUE}================================================${NC}"

# ── 步骤1: 环境文件检查 ──
log_step "步骤1/7: 检查环境配置文件..."
if [ ! -f "$ENV_PATH" ]; then
    log_error "环境配置文件不存在: $ENV_PATH"
    log_error "请从 .env.example 复制并填写: cp $BACKEND_DIR/.env.example $ENV_PATH"
    exit 1
fi
log_info "环境配置文件: $ENV_PATH"

# 生产环境红线校验：禁止占位符
if [ "$ENV" == "prod" ]; then
    log_step "生产环境红线校验..."
    PLACEHOLDERS=$(grep -E '\{\{.*\}\}' "$ENV_PATH" || true)
    if [ -n "$PLACEHOLDERS" ]; then
        log_error "生产环境 .env 包含未替换的占位符:"
        echo "$PLACEHOLDERS"
        log_error "请替换所有 {{xxx}} 占位符后再部署"
        exit 1
    fi

    # JWT_SECRET 长度校验（≥64位）
    JWT_SECRET_VAL=$(grep '^JWT_SECRET=' "$ENV_PATH" | cut -d'=' -f2-)
    if [ ${#JWT_SECRET_VAL} -lt 64 ]; then
        log_error "生产环境 JWT_SECRET 长度不足64位（当前: ${#JWT_SECRET_VAL}位）"
        exit 1
    fi

    # CORS 禁止通配符
    CORS_VAL=$(grep '^CORS_ORIGINS=' "$ENV_PATH" | cut -d'=' -f2-)
    if [ "$CORS_VAL" == "*" ]; then
        log_error "生产环境 CORS_ORIGINS 禁止使用通配符 *"
        exit 1
    fi
    log_info "生产红线校验通过（JWT≥64位 / CORS非通配 / 无占位符）"
fi

# ── 步骤2: 备份当前配置（回滚用） ──
log_step "步骤2/7: 备份当前配置..."
mkdir -p "$BACKUP_DIR"
if [ -f "$ENV_PATH" ]; then
    cp "$ENV_PATH" "$BACKUP_DIR/.env.last"
    log_info "已备份 .env → $BACKUP_DIR/.env.last"
fi
# 记录当前 alembic 版本（回滚用）
cd "$BACKEND_DIR"
export DOTENV_PATH="$ENV_FILE"
export ENVIRONMENT="$ENV"
CURRENT_REV=$(alembic current 2>/dev/null | awk '{print $1}' || echo "unknown")
echo "$CURRENT_REV" > "$BACKUP_DIR/alembic_rev.last"
log_info "已记录当前迁移版本: $CURRENT_REV"

# ── 步骤3: Python 依赖安装 ──
log_step "步骤3/7: 检查Python依赖..."
cd "$BACKEND_DIR"
if [ ! -d ".venv" ]; then
    log_warn "虚拟环境不存在，创建中..."
    python3.10 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
log_info "Python依赖已安装"

# ── 步骤4: 数据库迁移 ──
log_step "步骤4/7: 执行数据库迁移..."
export DOTENV_PATH="$ENV_FILE"
export ENVIRONMENT="$ENV"

# 迁移前备份当前版本
PRE_REV=$(alembic current 2>/dev/null | awk '{print $1}' || echo "unknown")
log_info "迁移前版本: $PRE_REV"

alembic upgrade head
POST_REV=$(alembic current 2>/dev/null | awk '{print $1}' || echo "unknown")
log_info "迁移后版本: $POST_REV"

if [ "$PRE_REV" == "$POST_REV" ] && [ "$PRE_REV" != "unknown" ]; then
    log_warn "迁移版本无变化（可能已是最新）"
else
    log_info "数据库迁移完成: $PRE_REV → $POST_REV"
fi

# ── 步骤5: 停止旧服务 ──
log_step "步骤5/7: 停止旧服务..."
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID"
        # 优雅等待5秒
        for i in $(seq 1 5); do
            if ! kill -0 "$OLD_PID" 2>/dev/null; then break; fi
            sleep 1
        done
        # 强制终止
        if kill -0 "$OLD_PID" 2>/dev/null; then
            kill -9 "$OLD_PID"
            log_warn "旧服务被强制终止 (PID: $OLD_PID)"
        else
            log_info "旧服务已优雅停止 (PID: $OLD_PID)"
        fi
    else
        log_warn "PID文件存在但进程已退出: $OLD_PID"
    fi
    rm -f "$PID_FILE"
else
    log_warn "无PID文件，跳过停止步骤"
fi

# ── 步骤6: 启动新服务 ──
log_step "步骤6/7: 启动新服务..."
mkdir -p "$LOG_DIR"
nohup bash "$START_SCRIPT" > "$LOG_DIR/backend.log" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
log_info "后端服务已启动 (PID: $NEW_PID)"

# ── 步骤7: 健康检查 ──
log_step "步骤7/7: 健康检查..."
PORT=$(grep '^PORT=' "$ENV_PATH" | cut -d'=' -f2 || echo "3001")
HEALTH_OK=false
for i in $(seq 1 10); do
    sleep 2
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/healthz" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" == "200" ]; then
        HEALTH_OK=true
        break
    fi
    log_warn "等待服务就绪... ($i/10, HTTP=$HTTP_CODE)"
done

if $HEALTH_OK; then
    log_info "健康检查通过 (HTTP 200)"
    # 深度健康检查（MySQL/Redis/OBS）
    READY_resp=$(curl -s "http://localhost:$PORT/readyz" 2>/dev/null || echo "{}")
    READY_STATUS=$(echo "$READY_resp" | python3 -c "import sys,json;print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
    if [ "$READY_STATUS" == "ok" ]; then
        log_info "就绪检查通过 (MySQL/Redis/OBS 全部连通)"
    else
        log_warn "就绪检查异常 (status=$READY_STATUS)，请检查 /readyz 接口"
    fi
else
    log_error "健康检查失败，服务未能在20秒内就绪"
    log_error "查看日志: tail -50 $LOG_DIR/backend.log"
    exit 1
fi

# ── 部署完成 ──
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✓ 后端部署完成！${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "${BLUE}环境:${NC} $ENV"
echo -e "${BLUE}端口:${NC} $PORT"
echo -e "${BLUE}PID:${NC} $NEW_PID"
echo -e "${BLUE}日志:${NC} $LOG_DIR/backend.log"
echo -e "${BLUE}健康检查:${NC} http://localhost:$PORT/healthz"
echo -e "${BLUE}就绪检查:${NC} http://localhost:$PORT/readyz"
echo ""
echo -e "${YELLOW}回滚命令:${NC} ./deploy_backend.sh $ENV --rollback"
