#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王 - 后台管理端生产打包部署脚本
# 流程：依赖检查 → TypeScript类型检查 → Vite生产构建 → 产物验证
#
# 用法：
#   ./deploy_admin.sh              # 默认构建
#   ./deploy_admin.sh --preview    # 构建后本地预览
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
ADMIN_DIR="$PROJECT_DIR/admin"

log_info()  { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓ $1${NC}"; }
log_warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠ $1${NC}"; }
log_error() { echo -e "${RED}[$(date '+%H:%M:%S')] ✗ $1${NC}"; }
log_step()  { echo -e "${BLUE}[$(date '+%H:%M:%S')] ▶ $1${NC}"; }

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}金角大王管理后台 - 生产打包${NC}"
echo -e "${BLUE}================================================${NC}"

# ── 步骤1: Node版本检查 ──
log_step "步骤1/5: 检查Node版本..."
NODE_VERSION=$(node -v 2>/dev/null | sed 's/v//' || echo "0")
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
    log_error "Node版本过低: v$NODE_VERSION（需要 ≥ 18）"
    log_error "请升级Node: nvm install 18 && nvm use 18"
    exit 1
fi
log_info "Node版本: v$NODE_VERSION"

# ── 步骤2: 依赖安装 ──
log_step "步骤2/5: 检查依赖..."
cd "$ADMIN_DIR"
if [ ! -d "node_modules" ]; then
    log_warn "node_modules不存在，安装依赖..."
    npm install --silent
    log_info "依赖安装完成"
else
    log_info "node_modules已存在"
fi

# ── 步骤3: TypeScript类型检查 ──
log_step "步骤3/5: TypeScript类型检查..."
if npx vue-tsc --noEmit 2>&1 | tee /tmp/admin_tsc.log; then
    log_info "类型检查通过（0 errors）"
else
    ERROR_COUNT=$(grep -c "error TS" /tmp/admin_tsc.log || echo "0")
    log_error "类型检查失败（$ERROR_COUNT errors）"
    log_error "查看详情: cat /tmp/admin_tsc.log"
    exit 1
fi

# ── 步骤4: Vite生产构建 ──
log_step "步骤4/5: Vite生产构建..."
# 清理旧产物
rm -rf dist
# 构建
if npm run build 2>&1 | tee /tmp/admin_build.log; then
    log_info "构建成功"
else
    log_error "构建失败"
    log_error "查看详情: cat /tmp/admin_build.log"
    exit 1
fi

# ── 步骤5: 产物验证 ──
log_step "步骤5/5: 验证构建产物..."
if [ ! -f "dist/index.html" ]; then
    log_error "构建产物缺失: dist/index.html"
    exit 1
fi

DIST_SIZE=$(du -sh dist | cut -f1)
FILE_COUNT=$(find dist -type f | wc -l | tr -d ' ')
log_info "构建产物: $DIST_SIZE, $FILE_COUNT 文件"
log_info "index.html: $(du -h dist/index.html | cut -f1)"

# 列出主要产物
echo ""
echo "  产物清单:"
ls -lh dist/ | tail -n +2 | while read -r line; do
    echo "    $line"
done

# ── 部署提示 ──
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✓ 管理后台打包完成！${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "${BLUE}产物目录:${NC} $ADMIN_DIR/dist/"
echo -e "${BLUE}部署方式:${NC} 将 dist/ 目录内容复制到Nginx静态资源目录"
echo -e "${BLUE}Nginx配置参考:${NC}"
echo "  server {"
echo "      listen 80;"
echo "      server_name admin.yourdomain.com;"
echo "      root /path/to/dist;"
echo "      index index.html;"
echo "      location /api/ { proxy_pass http://backend:3001; }"
echo "      location / { try_files \$uri \$uri/ /index.html; }"
echo "  }"
echo ""

# 可选：本地预览
if [[ "${1:-}" == "--preview" ]]; then
    log_step "启动本地预览..."
    npm run preview
fi
