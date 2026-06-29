#!/usr/bin/env sh
set -e
: "${JSA_ROOT:=/data}"
# seed default config into the data volume on first run (user edits it there after)
if [ ! -f "$JSA_ROOT/config/companies.csv" ]; then
  mkdir -p "$JSA_ROOT/config"
  cp /app/config/companies.csv /app/config/search_profile.yaml /app/config/settings.yaml "$JSA_ROOT/config/" 2>/dev/null || true
  [ -d /app/config/overrides ] && cp -r /app/config/overrides "$JSA_ROOT/config/" 2>/dev/null || true
fi
case "${1:-web}" in
  web)    exec python -m uvicorn app:app --app-dir webapp/backend --host 0.0.0.0 --port "${PORT:-8765}" ;;
  seek)   shift; exec python main.py seek "$@" ;;
  enrich) shift; exec python main.py enrich "$@" ;;
  *)      exec "$@" ;;
esac
