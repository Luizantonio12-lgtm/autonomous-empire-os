#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " AUTONOMOUS EMPIRE OS v3.0 — DEPLOY TURNKEY (DOCKER / VPS)"
echo "=========================================================="

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERRO] Docker não detetado. Instala Docker primeiro: curl -fsSL https://get.docker.com | sh"
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  JWT_RAND=$(openssl rand -hex 24 2>/dev/null || date +%s%N)
  echo "" >> .env
  echo "EMPIRE_JWT_SECRET=${JWT_RAND}" >> .env
  echo "[OK] Ficheiro .env criado a partir de .env.example com segredo JWT gerado."
fi

echo "[1/3] Construindo imagens e subindo cluster (Postgres pgvector + Redis + Evolution API + API Gateway + Command Center)..."
docker compose up -d --build

echo "[2/3] Aguardando verificação de saúde do API Gateway..."
for i in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "[OK] API Gateway 100% operacional!"
    break
  fi
  sleep 2
done

echo "=========================================================="
echo " IMPÉRIO EMPRESARIAL AUTÓNOMO ONLINE!"
echo " -> Painel Administrativo (CEO): http://localhost:3000"
echo " -> Documentação Swagger API:    http://localhost:8000/docs"
echo " -> Evolution API (WhatsApp):    http://localhost:8080"
echo " -> Senha CEO Padrão:            empire2026 (+ 2FA TOTP)"
echo "=========================================================="
