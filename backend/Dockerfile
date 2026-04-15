# syntax=docker/dockerfile:1.7

# ============================================================================
# AgenticFlow backend — multistage image (builder → runtime)
# ============================================================================
# - builder: installs deps into an isolated virtualenv; no build tools in the
#   runtime layer.
# - runtime: python:3.12-slim + the prebuilt venv, a non-root user, tini for
#   proper signal handling, and a HEALTHCHECK against /health.
#
# Expected build context: the repository root (compose `context: ./backend`).
# ============================================================================

# --- builder stage --------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# gcc / headers only needed during install (compiled wheels not published
# for all of our deps on slim).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Dependency layer — copy only what affects install so code changes don't
# invalidate the (expensive) pip install cache.
COPY requirements.txt ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.txt


# --- runtime stage --------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    LOG_DIR=/var/log/agenticflow \
    DATABASE_URL=sqlite:////data/agenticflow.db

# tini for PID 1 signal handling; libxml2/libxslt runtime for zeep;
# ca-certificates for outbound TLS (Anthropic / Gemini / Ticimax).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    tini \
    libxml2 \
    libxslt1.1 \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Non-root user + writable mounts
RUN groupadd --system --gid 1000 app \
 && useradd --system --uid 1000 --gid app --home /home/app --create-home app \
 && mkdir -p /app /data /var/log/agenticflow /app/exports \
 && chown -R app:app /app /data /var/log/agenticflow

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app app ./app
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app pyproject.toml ./pyproject.toml

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; \
urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2); sys.exit(0)" \
    || exit 1

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
