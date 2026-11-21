#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " AUTONOMOUS EMPIRE OS v3.0 — ARRANQUE DIRETO SEM DOCKER"
echo "=========================================================="

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo "[1/4] Criando ambiente virtual Python (.venv)..."
  python3 -m venv .venv
fi

source .venv/bin/activate
echo "[2/4] Instalando dependências Python..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "[3/4] Instalando dependências Frontend (Command Center)..."
cd "$ROOT_DIR/apps/command-center"
if [ ! -d "node_modules" ]; then
  npm install
fi

echo "[4/4] Iniciando API Gateway (porta 8000) e Painel ADM (porta 3000)..."
cd "$ROOT_DIR/apps/api-gateway"
uvicorn main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

trap 'echo "Encerrando serviços..."; kill $API_PID 2>/dev/null || true' EXIT

cd "$ROOT_DIR/apps/command-center"
npm run dev
