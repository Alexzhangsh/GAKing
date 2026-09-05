# @ai-generated
# ============================================================
# 金角大王CPS返利小程序 - 管理后台前端生产镜像
# 多阶段构建：
#   Stage 1: Node 18 构建 Vue3 生产产物
#   Stage 2: Nginx Alpine 提供静态文件服务
#
# 使用方式：docker compose 自动构建，无需手动操作
# 访问端口：容器内 80，由 docker-compose 映射到宿主机
# ============================================================

# ── Stage 1: 构建阶段 ──
FROM node:18-alpine AS builder

WORKDIR /app

# 先复制依赖文件，利用 Docker 层缓存
COPY package.json package-lock.json ./
RUN npm ci --silent --only=production=false

# 复制源码并构建
COPY . .
RUN npm run build

# ── Stage 2: 运行阶段 ──
FROM nginx:1.25-alpine

# 时区设置
RUN apk add --no-cache tzdata \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && apk del tzdata

# 从构建阶段复制产物
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx 配置（由 docker-compose 挂载或构建时复制）
# 若需要自定义 nginx.conf，在 docker-compose 中 volumes 挂载
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]