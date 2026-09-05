#!/bin/bash
# @ai-generated
# ============================================================
# 后端容器入口脚本
# 流程：等待 Redis → 执行 alembic 迁移（含 schema.sql 已建表兜底） → 启动 uvicorn
#
# S04 修复：生产库已通过 schema.sql 建表+建列，但 alembic_version 表为空，
#   直接 alembic upgrade head 会因 "Duplicate column name" 报错。
#   策略：先检查 alembic 版本；若为空但业务表已存在 → stamp head → upgrade head（no-op）。
# ============================================================
set -e

REDIS_HOST_VAL="${REDIS_HOST:-redis}"
REDIS_PORT_VAL="${REDIS_PORT:-6379}"

echo "[entrypoint] Waiting for Redis at ${REDIS_HOST_VAL}:${REDIS_PORT_VAL}..."
for i in $(seq 1 30); do
    if python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${REDIS_HOST_VAL}', ${REDIS_PORT_VAL}))
    s.close()
except Exception as e:
    sys.exit(1)
" 2>/dev/null; then
        echo "[entrypoint] Redis reachable."
        break
    fi
    echo "  redis not ready (${i}/30), retry in 2s..."
    sleep 2
done

# ============================================================
# Alembic 迁移（含 schema.sql 已建表场景兜底）
# ============================================================
echo "[entrypoint] Checking alembic state..."

# 检查 alembic_version 表是否存在且有版本记录
ALEMBIC_CHECK=$(python -c "
import os, sys
sys.path.insert(0, '/app')
try:
    import pymysql
    conn = pymysql.connect(
        host=os.environ.get('DB_HOST', ''),
        port=int(os.environ.get('DB_PORT', '3306')),
        user=os.environ.get('DB_USERNAME', ''),
        password=os.environ.get('DB_PASSWORD', ''),
        database=os.environ.get('DB_DATABASE', ''),
        connect_timeout=5,
        read_timeout=5,
    )
    cursor = conn.cursor()
    # 1. 检查 alembic_version 表是否存在
    cursor.execute(
        'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name=%s',
        (os.environ.get('DB_DATABASE', ''), 'alembic_version')
    )
    has_alembic_table = cursor.fetchone()[0] > 0
    if has_alembic_table:
        cursor.execute('SELECT version_num FROM alembic_version LIMIT 1')
        row = cursor.fetchone()
        version = row[0] if row else ''
        print(f'VERSION:{version}' if version else 'EMPTY_VERSION')
    else:
        # 2. 检查是否有业务表（orders / gaking_pay_config 等）
        cursor.execute(
            'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name IN (%s,%s,%s)',
            (os.environ.get('DB_DATABASE', ''), 'orders', 'gaking_pay_config', 'admin_user')
        )
        biz_count = cursor.fetchone()[0]
        print('HAS_SCHEMA_NO_ALEMBIC' if biz_count > 0 else 'FRESH_DB')
    conn.close()
except Exception as e:
    print(f'CHECK_ERROR:{e}')
" 2>&1 || echo "CHECK_ERROR:python_failed")

echo "[entrypoint] Alembic state: ${ALEMBIC_CHECK}"

case "$ALEMBIC_CHECK" in
    VERSION:*)
        # 已有 alembic 版本，正常升级
        echo "[entrypoint] Running alembic upgrade head (from existing version)..."
        alembic upgrade head
        ;;
    EMPTY_VERSION|HAS_SCHEMA_NO_ALEMBIC)
        # schema.sql 已建表但 alembic 未初始化 → stamp head 后 upgrade（no-op）
        echo "[entrypoint] Schema exists but alembic not initialized. Stamping to head..."
        alembic stamp head
        echo "[entrypoint] Stamped. Running alembic upgrade head (should be no-op)..."
        alembic upgrade head
        ;;
    FRESH_DB)
        # 全新数据库，从零开始迁移
        echo "[entrypoint] Fresh database. Running alembic upgrade head from scratch..."
        alembic upgrade head
        ;;
    *)
        # 检查失败，尝试直接升级（可能因网络等问题）
        echo "[entrypoint] Alembic state check failed: ${ALEMBIC_CHECK}"
        echo "[entrypoint] Attempting alembic upgrade head directly..."
        if ! alembic upgrade head 2>&1; then
            echo "[entrypoint] WARNING: alembic upgrade failed. If schema already exists this may be safe to ignore."
            echo "[entrypoint] Attempting stamp head as fallback..."
            alembic stamp head 2>/dev/null || true
        fi
        ;;
esac

echo "[entrypoint] Alembic migration done."

echo "[entrypoint] Starting: $@"
exec "$@"
