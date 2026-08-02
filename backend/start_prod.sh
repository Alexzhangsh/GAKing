#!/bin/bash
export ENVIRONMENT=production
export DOTENV_PATH=.env.production

echo "Starting production server..."
python -m uvicorn src.main:app --host 0.0.0.0 --port 3001 --workers 4