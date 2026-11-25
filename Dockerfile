FROM node:20-alpine AS frontend-builder
WORKDIR /ui
COPY apps/command-center/package.json ./
RUN npm install
COPY apps/command-center ./
RUN npm run build

FROM node:20-slim AS wa-bridge-builder
WORKDIR /wa
COPY apps/wa-bridge/package.json ./
COPY apps/wa-bridge/patches ./patches
RUN npm install --omit=dev --no-audit --no-fund
COPY apps/wa-bridge/server.js ./

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY Dockerfile render.yaml /app/
COPY packages /app/packages
COPY apps/api-gateway /app/apps/api-gateway
COPY --from=frontend-builder /ui/dist /app/apps/command-center/dist
COPY --from=wa-bridge-builder /wa /app/apps/wa-bridge

RUN mkdir -p /app/deployments /app/.wa_auth
EXPOSE 10000
CMD ["sh", "-c", "WA_INTERNAL_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))'); export WA_INTERNAL_SECRET; if [ \"$WA_BRIDGE_ENABLED\" = \"true\" ]; then PORT=${PORT:-10000} WA_BRIDGE_PORT=3005 WA_AUTH_DIR=/app/.wa_auth node /app/apps/wa-bridge/server.js & fi; exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --app-dir /app/apps/api-gateway"]
