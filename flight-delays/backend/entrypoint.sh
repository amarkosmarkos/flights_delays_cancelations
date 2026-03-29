#!/bin/sh
set -e

echo "==> Training ML models against database..."
python -m scripts.train_models || echo "WARNING: Model training failed (DB might be empty). API will start but predictions won't work."

echo "==> Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
