# syntax=docker/dockerfile:1.7
# LaunchScout backend image: used by both the API (uvicorn) and the worker (arq).

ARG PYTHON_VERSION=3.12

# ---------- build stage: resolve and install Python deps into a venv ----------
FROM python:${PYTHON_VERSION}-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /src
COPY pyproject.toml .
# Install the runtime dependencies declared in pyproject.toml (the app itself is copied, not installed).
RUN python -c "import tomllib;print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

# ---------- runtime stage ----------
FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    OUTPUTS_DIR=/app/outputs \
    CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false OTEL_SDK_DISABLED=true \
    HOME=/home/app
# WeasyPrint needs Pango/HarfBuzz; fonts for the PDF report; curl for the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
        fonts-dejavu-core fonts-liberation curl procps \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
COPY --chown=app:app docker-entrypoint.sh ./
RUN chmod 0755 docker-entrypoint.sh && mkdir -p /app/outputs && chown app:app /app/outputs
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["api"]
