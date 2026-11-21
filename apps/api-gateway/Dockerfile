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

RUN mkdir -p /app/deployments

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=4s --retries=5 CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/apps/api-gateway"]
