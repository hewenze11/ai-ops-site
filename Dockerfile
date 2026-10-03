# syntax=docker/dockerfile:1
# AI Ops website + membership backend. Runs as a non-root user; the database
# lives on a mounted volume.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY ai_ops_site ./ai_ops_site
RUN pip install --no-cache-dir . && \
    useradd --system --uid 10001 --create-home appuser && \
    mkdir -p /data && chown -R appuser:appuser /data

# --- test stage (used by CI to run the suite inside an image) ---
FROM base AS test
COPY tests ./tests
RUN pip install --no-cache-dir '.[test]'
USER appuser
ENV AI_OPS_SITE_DB=/tmp/test.db AI_OPS_SITE_ADMIN_TOKEN=ci-token
RUN pytest -q

# --- runtime ---
FROM base AS runtime
USER appuser
ENV AI_OPS_SITE_DB=/data/site.db
VOLUME ["/data"]
EXPOSE 8090
CMD ["ai-ops-site", "--host", "0.0.0.0", "--port", "8090"]
