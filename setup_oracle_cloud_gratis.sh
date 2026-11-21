#!/usr/bin/env bash
set -euo pipefail

echo "=================================================================="
echo " AUTONOMOUS EMPIRE OS — INSTALADOR ORACLE CLOUD ALWAYS FREE (R$ 0)"
echo " Compatível com ARM64 (Ampere A1 12GB) e x86_64 (Ubuntu 22.04/24.04)"
echo "=================================================================="

if [ "$(id -u)" -ne 0 ]; then
  echo "[!] A reexecutar com privilégios sudo..."
  exec sudo bash "$0" "$@"
fi

cd "$(dirname "$0")"
ARCH=$(uname -m)
echo "[INFO] Arquitetura detetada: ${ARCH}"

echo "[1/5] Atualizando pacotes base e instalando Docker oficial..."
apt-get update -qq
apt-get install -y -qq curl git unzip iptables-persistent openssl

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

echo "[2/5] Liberando firewall interna da Oracle Cloud (iptables portas 80, 443, 3000, 8000, 8080)..."
for PORT in 80 443 3000 8000 8080; do
  iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null || \
  iptables -I INPUT 5 -p tcp --dport "$PORT" -j ACCEPT
done
netfilter-persistent save || true

echo "[3/5] Garantindo memória Swap de segurança (4 GB)..."
if ! swapon --show | grep -q '/swapfile'; then
  fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "[4/5] Configurando variáveis .env de produção..."
if [ ! -f .env ]; then
  cp .env.example .env
  JWT_RAND=$(openssl rand -hex 24)
  echo "" >> .env
  echo "EMPIRE_JWT_SECRET=${JWT_RAND}" >> .env
fi

echo "[5/5] Subindo os 5 contentores (Postgres pgvector + Redis + Evolution API ARM64/x86 + API Gateway + Painel ADM)..."
docker compose up -d --build

PUBLIC_IP=$(curl -4 -fsS ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

echo "=================================================================="
echo " VPS GRATUITA 100% ATIVA COM AUTONOMOUS EMPIRE OS!"
echo " -> Painel Administrativo: http://${PUBLIC_IP}:3000"
echo " -> API Swagger Docs:      http://${PUBLIC_IP}:8000/docs"
echo " -> WhatsApp Evolution:    http://${PUBLIC_IP}:8080"
echo " -> Senha CEO Padrão:      empire2026 (+ 2FA TOTP)"
echo " [IMPORTANTE] Lembra-te de liberar a porta TCP 3000 na Ingress Rule"
echo " da Security List (VCN) dentro do painel web da Oracle Cloud!"
echo "=================================================================="
