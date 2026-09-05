#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王 - 数据库迁移管理脚本
# 支持：upgrade / downgrade / current / history / reset
#
# 用法：
#   ./migrate_db.sh prod upgrade       # 升级到最新
#   ./migrate_db.sh prod upgrade 0008  # 升级到指定版本
#   ./migrate_db.sh prod downgrade     # 回退一个版本
#   ./migrate_db.sh prod downgrade 3   # 回退N个版本
#   ./migrate_db.sh prod current       # 查看当前版本
#   ./migrate_db.sh prod history       # 查看迁移历史
#   ./migrate_db.sh prod reset         # 重置到初始状态（危险！）
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
BACKEND_DIR="$PROJECT_DIR/backend"

ENV="${1:-dev}"
ACTION="${2:-current}"
ARG="${3:-}"

# 环境映射
case "$ENV" in
    dev)  ENV_FILE=".env.development" ;;
    test) ENV_FILE=".env.test" ;;
    prod) ENV_FILE=".env.production" ;;
    *)
        echo -e "${RED}✗ 未知环境: $ENV（支持: dev / test / prod）${NC}"
        exit 1
        ;;
esac

ENV_PATH="$BACKEND_DIR/$ENV_FILE"

# 检查环境文件
if [ ! -f "$ENV_PATH" ]; then
    echo -e "${RED}✗ 环境配置文件不存在: $ENV_PATH${NC}"
    exit 1
fi

cd "$BACKEND_DIR"
export DOTENV_PATH="$ENV_FILE"
export ENVIRONMENT="$ENV"

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

log_info()  { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓ $1${NC}"; }
log_warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠ $1${NC}"; }
log_error() { echo -e "${RED}[$(date '+%H:%M:%S')] ✗ $1${NC}"; }
log_step()  { echo -e "${BLUE}[$(date '+%H:%M:%S')] ▶ $1${NC}"; }

log_step "数据库迁移 [环境: $ENV] [操作: $ACTION]"

case "$ACTION" in
    upgrade)
        if [ -n "$ARG" ]; then
            log_info "升级到指定版本: $ARG"
            alembic upgrade "$ARG"
        else
            log_info "升级到最新版本"
            alembic upgrade head
        fi
        log_info "迁移完成，当前版本: $(alembic current 2>/dev/null | awk '{print $1}')"
        ;;
    downgrade)
        if [ -n "$ARG" ]; then
            # 回退N个版本
            log_warn "回退 $ARG 个版本"
            for i in $(seq 1 "$ARG"); do
                alembic downgrade -1
                CUR=$(alembic current 2>/dev/null | awk '{print $1}')
                log_info "已回退到: $CUR ($i/$ARG)"
            done
        else
            log_warn "回退一个版本"
            alembic downgrade -1
        fi
        log_info "回退完成，当前版本: $(alembic current 2>/dev/null | awk '{print $1}')"
        ;;
    current)
        log_info "当前迁移版本:"
        alembic current
        ;;
    history)
        log_info "迁移历史:"
        alembic history --verbose 2>/dev/null | head -30
        ;;
    reset)
        log_error "⚠️ 危险操作：将重置数据库到初始状态！"
        log_error "环境: $ENV"
        if [ "$ENV" == "prod" ]; then
            log_error "生产环境禁止执行 reset 操作！"
            exit 1
        fi
        read -p "确认重置？输入 YES 继续: " CONFIRM
        if [ "$CONFIRM" != "YES" ]; then
            log_warn "已取消"
            exit 0
        fi
        log_warn "执行数据库重置..."
        alembic downgrade base
        alembic upgrade head
        log_info "数据库已重置到最新版本"
        ;;
    *)
        echo -e "${RED}✗ 未知操作: $ACTION${NC}"
        echo "可用操作: upgrade [version] | downgrade [N] | current | history | reset"
        exit 1
        ;;
esac
