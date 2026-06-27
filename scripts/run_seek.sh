#!/usr/bin/env bash
# Wrapper for scheduled runs (cron / launchd). Resolves the repo from this
# script's location, runs seek with the project venv, and appends to a log.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/runs
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') seek start ==="
  .venv/bin/python main.py seek
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') seek done ==="
} >> data/runs/cron.log 2>&1
