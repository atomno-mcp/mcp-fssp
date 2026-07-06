FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /data && chmod 777 /data

VOLUME ["/data"]

ENV MCP_FSSP_AUDIT_DB=/data/audit.sqlite \
    MCP_FSSP_LOG_LEVEL=INFO

ENTRYPOINT ["atomno-mcp-fssp"]
