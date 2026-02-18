# ---- Stage 1: Build Next.js ----
FROM node:22-alpine AS web-builder
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ .
RUN npm run build

# ---- Stage 2: Final image (Python + Node runtime) ----
FROM python:3.12-slim

# Node.js runtime for Next.js standalone server
COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node

# uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Python agent dependencies
WORKDIR /app/agent
COPY agent/pyproject.toml agent/uv.lock ./
RUN uv sync --frozen --no-dev
COPY agent/agent.py agent/db.py agent/wisprflow_stt.py ./

# Next.js standalone build
COPY --from=web-builder /app/.next/standalone /app/web
COPY --from=web-builder /app/.next/static /app/web/.next/static

# Startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

WORKDIR /app
ENV HOSTNAME="0.0.0.0"
CMD ["/app/start.sh"]
