# syntax=docker/dockerfile:1
# Browser-free image (Talemetry uses curl_cffi, not Playwright) — small + ARM-friendly for the RPi5.

# --- stage 1: build the React frontend ---
FROM node:20-bookworm-slim AS frontend
WORKDIR /ui
COPY webapp/frontend/package*.json ./
RUN npm ci
COPY webapp/frontend/ ./
RUN npm run build          # -> /ui/dist

# --- stage 2: python runtime ---
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 JSA_ROOT=/data PORT=8765
WORKDIR /app

# curated runtime deps (no pandas, no playwright)
RUN pip install --no-cache-dir \
      click pyyaml requests beautifulsoup4 lxml markdownify curl-cffi \
      anthropic python-dateutil fastapi "uvicorn[standard]"

COPY services/ services/
COPY scrapers/ scrapers/
COPY outputs/ outputs/
COPY models/ models/
COPY config/ config/
COPY main.py ./
COPY webapp/backend/ webapp/backend/
COPY --from=frontend /ui/dist webapp/frontend/dist
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8765
ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]
