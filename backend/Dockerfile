# @ai-generated
# ============================================================
# 金角大王CPS返利小程序 - 后端生产镜像
# 基础镜像：python:3.10-slim（项目硬性约束 Python 3.10.x）
# 运行：uvicorn + 4 workers，监听 3003
#
# 优化（S04）：
#   - apt 换华为云 Debian 源，避免 deb.debian.org 国内拉取超慢
#   - 移除 gcc/g++/libffi-dev：bcrypt/cryptography 均有 manylinux 预编译 wheel
#   - pip 换华为云 pypi 源，加速依赖安装
#   - healthcheck 用 python urllib，免装 curl
# ============================================================
FROM python:3.10-slim

# ── apt 换华为云镜像源（兼容 sources.list 与 debian.sources 两种格式）──
RUN sed -i 's|deb.debian.org|mirrors.huaweicloud.com|g; s|security.debian.org|mirrors.huaweicloud.com|g' \
        /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list 2>/dev/null || true

# ── 仅装 tzdata（时区）；curl 不装，healthcheck 用 python 替代 ──
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── 先装依赖（利用 Docker 层缓存）；清华 pypi 源（华为云 pypi 源不可用）──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
        -i https://pypi.tuna.tsinghua.edu.cn/simple

# ── 复制应用代码（src/db/schema.sql 随 src/ 一并复制）──
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY scripts/ ./scripts/

# ── 运行时目录 ──
RUN mkdir -p logs static/uploads tmp

EXPOSE 3003

# ── entrypoint：等 Redis 就绪 → alembic 迁移 → 启动 uvicorn ──
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3003", "--workers", "4"]
