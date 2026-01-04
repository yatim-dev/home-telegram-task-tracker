#!/bin/sh
set -e

python /app/scripts/init_admin.py || true

exec python /app/main.py
