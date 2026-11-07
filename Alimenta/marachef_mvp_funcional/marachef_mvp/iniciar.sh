#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python manage.py init-db
python -m uvicorn app:app --host 127.0.0.1 --port 8000
