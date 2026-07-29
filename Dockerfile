# syntax=docker/dockerfile:1
# Browser-free image (Talemetry uses curl_cffi, not Playwright) — small + ARM-friendly for the RPi5.

# --- stage 1: build the React frontend ---
FROM node:26-bookworm-slim AS frontend
WORKDIR /ui
COPY webapp/frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY webapp/frontend/ ./
RUN npm run build          # -> /ui/dist

# --- stage 2: python runtime ---
FROM python:3.14-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 JSA_ROOT=/data PORT=8765
WORKDIR /app

# runtime deps come from requirements.txt so image and CI can never drift on
# versions (an unpinned copy here once shipped mcp 2.0 while CI tested <2);
# web-server extras (fastapi/uvicorn/tzdata) are image-only, same as CI's list
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt fastapi "uvicorn[standard]" tzdata

COPY services/ services/
COPY scrapers/ scrapers/
COPY outputs/ outputs/
COPY models/ models/
COPY config/ config/
COPY scripts/ scripts/
COPY main.py ./
COPY webapp/backend/ webapp/backend/
COPY --from=frontend /ui/dist webapp/frontend/dist
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8765
ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]
