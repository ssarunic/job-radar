#!/usr/bin/env sh
set -e
: "${JSA_ROOT:=/data}"
# seed default config into the data volume on first run (user edits it there after).
# companies.csv is user-owned and never shipped: it is created on the first follow.
if [ ! -f "$JSA_ROOT/config/settings.yaml" ]; then
  mkdir -p "$JSA_ROOT/config"
  cp /app/config/search_profile.yaml /app/config/settings.yaml "$JSA_ROOT/config/" 2>/dev/null || true
  [ -d /app/config/overrides ] && cp -r /app/config/overrides "$JSA_ROOT/config/" 2>/dev/null || true
fi
case "${1:-web}" in
  web)      exec python -m uvicorn app:app --app-dir webapp/backend --host 0.0.0.0 --port "${PORT:-8765}" ;;
  seek)     shift; exec python main.py seek "$@" ;;
  enrich)   shift; exec python main.py enrich "$@" ;;
  schedule) exec python scripts/scheduler.py ;;   # daily seek at SEEK_AT (default 08:00 Europe/London)
  *)        exec "$@" ;;
esac
