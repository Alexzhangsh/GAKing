#!/bin/bash
export ENVIRONMENT=test
export DOTENV_PATH=.env.test

echo "Starting test server..."
python -m uvicorn src.main:app --host 0.0.0.0 --port 3001