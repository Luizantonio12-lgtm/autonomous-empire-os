FROM node:20-alpine AS frontend-builder
WORKDIR /ui
COPY apps/command-center/package.json ./
RUN npm install
COPY apps/command-center ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY packages /app/packages
COPY apps/api-gateway /app/apps/api-gateway
COPY --from=frontend-builder /ui/dist /app/apps/command-center/dist

RUN mkdir -p /app/deployments
EXPOSE 10000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --app-dir /app/apps/api-gateway"]
