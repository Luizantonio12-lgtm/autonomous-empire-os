# Guia de Operação Imediata — Autonomous Empire OS v3.0

Todo o teu ecossistema empresarial autónomo está **100% fechado, testado e pronto a rodar** (tanto agora mesmo neste ambiente ao vivo como em qualquer servidor VPS/Cloud próprio).

---

## 1. Operação Imediata Aqui no Ambiente Live (Já Ativo!)
- **Painel Administrativo Central:** Aberto ao vivo na porta `3000` (pré-visualização lateral).
- **Piloto Automático 24/7:** Já ligado (`ATIVO`) — os agentes de **Vendas**, **Growth/Social** e **Financeiro** estão executando ciclos autónomos em background.
- **Instância WhatsApp:** Já pareada e conectada (`CONNECTED`).
- **Empresa Flagship (`NexusFlow AI`):** Online com checkout *Self-Serve* funcional a `$297/mês`.

---

## 2. Subir num Servidor VPS / Cloud Próprio em 1 Comando (Produção Docker)

Extrai o pacote `autonomous-empire-production-ready.zip` na tua VPS (Ubuntu 22.04/24.04, Hetzner, Hostinger, DigitalOcean, AWS) e executa:

```bash
chmod +x deploy_vps_docker.sh start_local.sh backup_empire.sh
./deploy_vps_docker.sh
```

Isto sobe automaticamente:
1. **`empire-postgres` (`pgvector/pgvector:pg16`)** — Base de dados transacional + extensão vetorial `pgvector` + criação automática das bases `autonomous_empire` e `evolution`.
2. **`empire-redis` (`redis:7-alpine`)** — Streams e PubSub de tempo real.
3. **`empire-whatsapp-evolution` (`evolution-api:v2.1.1`)** — Servidor oficial WhatsApp Baileys apontando webhooks automaticamente para `http://api-gateway:8000/api/webhooks/evolution`.
4. **`empire-api-gateway` (`FastAPI + LangGraph + Sandbox Git/Node`)** — Orquestrador Mestre, 7 Departamentos, Venture Builder e Gateways Financeiros.
5. **`empire-command-center` (`Nginx + React Production Bundle`)** — Painel ADM de alta performance com proxy WebSocket nativo na porta `3000`.

---

## 3. Subir no Teu Computador (Mac / Linux / WSL) Sem Docker

```bash
./start_local.sh
```
Abre automaticamente em `http://localhost:3000` usando persistência assíncrona local (`empire_state.db`).

---

## 4. Ativar Chaves Reais em Quente (Sem Reiniciar Servidor)

Acede à aba **`Segurança 2FA, Vault & pgvector`** no Painel Administrativo e cola as tuas chaves no **Cofre Runtime**:
- **`DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`:** Ativa inferência externa real na cascata `MultiModelLLMGateway`.
- **`ASAAS_API_KEY` / `STRIPE_SECRET_KEY`:** Passa a gerar cobranças Pix Banco Central reais e sessões Stripe reais.
- **`VERCEL_TOKEN`:** Publica cada projeto da Fábrica de Software diretamente em domínios públicos `.vercel.app`.
- **Segurança CEO:** Senha padrão `empire2026` (alterável via `EMPIRE_CEO_PASSWORD` no `.env`) + **2FA TOTP** compatível com Google Authenticator (`Segredo Base32: JBSWY3DPEHPK3PXP`).
