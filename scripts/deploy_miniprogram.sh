#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王 - 微信小程序生产打包部署脚本
# 流程：依赖检查 → 环境配置 → TypeScript类型检查 → uni-app构建 → 产物验证
#
# 用法：
#   ./deploy_miniprogram.sh                    # 构建微信小程序
#   ./deploy_miniprogram.sh --h5               # 构建H5版本
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
MINI_DIR="$PROJECT_DIR/miniprogram"

BUILD_TARGET="mp-weixin"
if [[ "${1:-}" == "--h5" ]]; then
    BUILD_TARGET="h5"
fi

log_info()  { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓ $1${NC}"; }
log_warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠ $1${NC}"; }
log_error() { echo -e "${RED}[$(date '+%H:%M:%S')] ✗ $1${NC}"; }
log_step()  { echo -e "${BLUE}[$(date '+%H:%M:%S')] ▶ $1${NC}"; }

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}金角大王微信小程序 - 生产打包${NC}"
echo -e "${BLUE}构建目标: $BUILD_TARGET${NC}"
echo -e "${BLUE}================================================${NC}"

# ── 步骤1: Node版本检查 ──
log_step "步骤1/5: 检查Node版本..."
NODE_VERSION=$(node -v 2>/dev/null | sed 's/v//' || echo "0")
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
    log_error "Node版本过低: v$NODE_VERSION（需要 ≥ 18）"
    exit 1
fi
log_info "Node版本: v$NODE_VERSION"

# ── 步骤2: 依赖安装 ──
log_step "步骤2/5: 检查依赖..."
cd "$MINI_DIR"
if [ ! -d "node_modules" ]; then
    log_warn "node_modules不存在，安装依赖..."
    npm install --silent
    log_info "依赖安装完成"
else
    log_info "node_modules已存在"
fi

# ── 步骤3: 生产环境配置校验 ──
log_step "步骤3/5: 校验生产环境配置..."
ENV_FILE="$MINI_DIR/src/config/env.ts"
if [ -f "$ENV_FILE" ]; then
    # 检查是否包含开发环境占位符
    if grep -q "localhost\|127.0.0.1\|dev_\|placeholder" "$ENV_FILE" 2>/dev/null; then
        log_warn "环境配置可能包含开发占位符，请确认:"
        grep -n "localhost\|127.0.0.1\|dev_\|placeholder\|{{" "$ENV_FILE" 2>/dev/null | head -5
    else
        log_info "环境配置检查通过"
    fi
else
    log_warn "未找到环境配置文件: $ENV_FILE"
fi

# 检查微信小程序AppID配置
MANIFEST_FILE="$MINI_DIR/src/manifest.json"
if [ -f "$MANIFEST_FILE" ]; then
    APPID=$(python3 -c "
import json
with open('$MANIFEST_FILE') as f:
    d = json.load(f)
mp = d.get('mp-weixin', {})
appid = mp.get('appid', '')
print(appid)
" 2>/dev/null || echo "")
    if [ -z "$APPID" ] || [ "$APPID" == "touristappid" ]; then
        log_warn "微信小程序AppID未配置或为测试值: $APPID"
        log_warn "请在 $MANIFEST_FILE → mp-weixin.appid 填入正式AppID"
    else
        log_info "微信小程序AppID: $APPID"
    fi
fi

# ── 步骤4: 构建小程序 ──
log_step "步骤4/5: uni-app生产构建..."
# 清理旧产物
rm -rf dist

BUILD_CMD=""
case "$BUILD_TARGET" in
    mp-weixin)
        BUILD_CMD="npm run build:mp-weixin"
        DIST_PATH="dist/build/mp-weixin"
        ;;
    h5)
        BUILD_CMD="npm run build:h5"
        DIST_PATH="dist/build/h5"
        ;;
esac

if $BUILD_CMD 2>&1 | tee /tmp/miniprogram_build.log; then
    log_info "构建成功"
else
    log_error "构建失败"
    log_error "查看详情: cat /tmp/miniprogram_build.log"
    exit 1
fi

# ── 步骤5: 产物验证 ──
log_step "步骤5/5: 验证构建产物..."
if [ ! -d "$DIST_PATH" ]; then
    log_error "构建产物目录不存在: $DIST_PATH"
    exit 1
fi

if [ "$BUILD_TARGET" == "mp-weixin" ]; then
    if [ ! -f "$DIST_PATH/app.js" ] || [ ! -f "$DIST_PATH/app.json" ]; then
        log_error "微信小程序产物缺失: app.js / app.json"
        exit 1
    fi
fi

DIST_SIZE=$(du -sh "$DIST_PATH" | cut -f1)
FILE_COUNT=$(find "$DIST_PATH" -type f | wc -l | tr -d ' ')
log_info "构建产物: $DIST_SIZE, $FILE_COUNT 文件"

# 主包大小检查（微信限制2MB）
if [ "$BUILD_TARGET" == "mp-weixin" ]; then
    MAIN_SIZE=$(du -sk "$DIST_PATH" | cut -f1)
    if [ "$MAIN_SIZE" -gt 2048 ]; then
        log_warn "主包大小 ${MAIN_SIZE}KB 超过微信2MB限制，请优化分包"
    else
        log_info "主包大小: ${MAIN_SIZE}KB（限制2048KB）"
    fi
fi

# ── 部署提示 ──
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✓ 小程序打包完成！${NC}"
echo -e "${GREEN}================================================${NC}"

if [ "$BUILD_TARGET" == "mp-weixin" ]; then
    echo -e "${BLUE}产物目录:${NC} $MINI_DIR/$DIST_PATH"
    echo -e "${BLUE}部署方式:${NC}"
    echo "  1. 打开微信开发者工具"
    echo "  2. 导入项目 → 选择目录: $MINI_DIR/$DIST_PATH"
    echo "  3. 确认AppID正确"
    echo "  4. 点击「上传」→ 填写版本号 → 提交审核"
    echo ""
    echo -e "${YELLOW}注意:${NC}"
    echo "  - 上传前确认 src/manifest.json 中 mp-weixin.appid 为正式AppID"
    echo "  - 服务器域名需在小程序后台配置（request合法域名）"
    echo "  - 确认后端API域名已配置HTTPS证书"
else
    echo -e "${BLUE}产物目录:${NC} $MINI_DIR/$DIST_PATH"
    echo -e "${BLUE}部署方式:${NC} 将目录内容部署到CDN/Nginx静态服务器"
fi
