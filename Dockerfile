# lendstack-core — remote MCP server (streamable HTTP) for Claude Marketplace / Connectors.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

# Run as a non-root user.
RUN useradd -m -u 10001 appuser
USER appuser

EXPOSE 8080

# OAuth must be configured at runtime (OAUTH_ISSUER/AUDIENCE/MCP_RESOURCE_URL) or the
# server refuses to start in remote mode. See docs/DEPLOY.md.
CMD ["lendstack-core"]
