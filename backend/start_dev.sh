#!/bin/bash
export ENVIRONMENT=development
export DOTENV_PATH=.env.development

echo "Starting development server..."
python -m uvicorn src.main:app --host 0.0.0.0 --port 3001 --reload