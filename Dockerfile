# ── SimAPI production image ──────────────────────────────────────────────────────
# Multi-stage build: dependencies are resolved once, then copied into a slim,
# non-root runtime layer.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ── Dependencies ──────────────────────────────────────────────────────────────────
FROM base AS deps
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ── Runtime ───────────────────────────────────────────────────────────────────────
FROM base AS runtime
COPY --from=deps /install /usr/local
COPY . .

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 simapi && chown -R simapi /app
USER simapi

EXPOSE 8000

# Container-level liveness check hitting the app's health endpoint.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/v1/health').status==200 else 1)"

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
