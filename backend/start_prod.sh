#!/bin/bash
export ENVIRONMENT=production
export DOTENV_PATH=.env.production

# 从 .env.production 读取端口配置，避免硬编码
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env.production"
PORT=$(grep -E '^PORT=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- || echo "3001")

echo "Starting production server on port ${PORT}..."
python -m uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --workers 4