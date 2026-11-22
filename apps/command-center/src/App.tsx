import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Bot,
  BrainCircuit,
  CheckCircle2,
  Clock,
  CloudUpload,
  Code2,
  Copy,
  Cpu,
  CreditCard,
  DollarSign,
  Download,
  ExternalLink,
  Factory,
  FileCode,
  GitBranch,
  KeyRound,
  Layers,
  Lock,
  Megaphone,
  MessageSquare,
  Pause,
  Play,
  PlusCircle,
  Power,
  QrCode,
  RefreshCw,
  Rocket,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  TrendingUp,
  Unlock,
  Wallet,
  Wrench,
  X,
  Zap,
} from 'lucide-react';
import type {
  AgentItem,
  BusinessVentureItem,
  DashboardOverview,
  HealingLogStep,
  ScheduledJobItem,
  SemanticMemoryItem,
  SoftwareProjectItem,
  TelemetryEvent,
} from './types/empire';

type TabKey =
  | 'OVERVIEW'
  | 'VENTURES'
  | 'AUTOPILOT_GROWTH'
  | 'FACTORY'
  | 'LEDGER'
  | 'OMNICHANNEL'
  | 'META'
  | 'MEMORY_LLM'
  | 'LEAD_HUNTER';

interface RealLeadItem {
  id: string;
  business_name: string;
  city: string;
  niche: string;
  phone_digits: string;
  phone_display: string;
  instagram: string;
  source_url: string;
  maps_url: string;
  snippet: string;
  venture_id: string;
  venture_name: string;
  price_usd: number;
  price_brl: string;
  whatsapp_pitch: string;
  whatsapp_url: string;
}

export default function App() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>('LEAD_HUNTER');
  const [busy, setBusy] = useState(false);

  // Portfólio de Empresas & Venture Launcher
  const [venName, setVenName] = useState('LexGuard AI');
  const [venNiche, setVenNiche] = useState('Sociedades de Advogados & Departamentos Jurídicos');
  const [venPrice, setVenPrice] = useState('397');
  const [venTagline, setVenTagline] = useState(
    'Revisão Autónoma de Contratos B2B, Conformidade LGPD/GDPR e Assinatura em 10 Segundos'
  );
  const [activeVenture, setActiveVenture] = useState<BusinessVentureItem | null>(null);

  // Segurança Soberana (Lock Screen JWT + 2FA TOTP)
  const [isLocked, setIsLocked] = useState(false);
  const [jwtToken, setJwtToken] = useState<string | null>(null);
  const [loginPassword, setLoginPassword] = useState('empire2026');
  const [loginTotp, setLoginTotp] = useState('');
  const [loginError, setLoginError] = useState<string | null>(null);

  // Consola de Comando Direto (CEO)
  const [directiveText, setDirectiveText] = useState('');
  const [targetDept, setTargetDept] = useState('AUTO');

  // Scheduler 24/7 & Growth Social
  const [cronName, setCronName] = useState('Caçador Leads Fintech Internacional');
  const [cronDept, setCronDept] = useState('SALES');
  const [cronInterval, setCronInterval] = useState('30');
  const [cronDirective, setCronDirective] = useState(
    'Prospectar CTOs de fintechs e apresentar proposta de automação SaaS.'
  );

  const [campTitle, setCampTitle] = useState('Série Viral: Empresa Gerida por 7 Agentes IA');
  const [campChannel, setCampChannel] = useState('INSTAGRAM_REELS');
  const [campDirective, setCampDirective] = useState(
    'Criar roteiro e campanha de alta conversão demonstrando Self-Healing e vendas autónomas 24/7.'
  );

  // Fábrica de Software Nível 2
  const [projName, setProjName] = useState('Astro Raiders 2026');
  const [projType, setProjType] = useState('GAME_HTML5');
  const [projClient, setProjClient] = useState('Cliente Enterprise Global');
  const [projValue, setProjValue] = useState('3200');
  const [projSpec, setProjSpec] = useState(
    'Jogo arcade espacial rápido com ondas progressivas de drones, escudos recarregáveis e partículas.'
  );
  const [simulateHealing, setSimulateHealing] = useState(true);
  const [activePreviewProject, setActivePreviewProject] = useState<SoftwareProjectItem | null>(
    null
  );
  const [inspectedSource, setInspectedSource] = useState<{
    name: string;
    git_commit_hash: string | null;
    healing_iterations: number;
    healing_log: HealingLogStep[];
    test_report: string;
    sources: Record<string, string>;
  } | null>(null);
  const [selectedSourceFile, setSelectedSourceFile] = useState<string>('index.html');

  // Meta-Agente
  const [metaPrompt, setMetaPrompt] = useState(
    'Criar Agente Jurídico & Contratos SaaS Internacionais para revisão autónoma de cláusulas B2B'
  );

  // WhatsApp Evolution API QR + Webhook
  const [pairPhone, setPairPhone] = useState('+55 16 99810-2026');
  const [waName, setWaName] = useState('Mariana Costa (Diretora Operações)');
  const [waPhone, setWaPhone] = useState('+5511997410022');
  const [waMessage, setWaMessage] = useState(
    'Olá! Estamos com um pico de acessos e preciso validar se a nossa chave API e fatura Pix estão liberadas.'
  );

  // Pagamentos Stripe / Asaas Pix
  const [invProvider, setInvProvider] = useState<'ASAAS_PIX' | 'STRIPE'>('ASAAS_PIX');
  const [invClient, setInvClient] = useState('Grupo Industrial Vale');
  const [invEmail, setInvEmail] = useState('tesouraria@grupovale.com.br');
  const [invDesc, setInvDesc] = useState('Setup Fábrica de Software + Agentes Dedicados');
  const [invAmount, setInvAmount] = useState('2750');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [ledgerFilter, setLedgerFilter] = useState<'ALL' | 'REVENUE' | 'EXPENSE'>('ALL');

  // Memória Vetorial (pgvector) & Cofre Multi-LLM
  const [memQuery, setMemQuery] = useState('');
  const [memSearchResults, setMemSearchResults] = useState<SemanticMemoryItem[] | null>(null);
  const [newMemNamespace, setNewMemNamespace] = useState('CEO_DIRECTIVES');
  const [newMemTitle, setNewMemTitle] = useState('');
  const [newMemContent, setNewMemContent] = useState('');
  const [selectedVaultKey, setSelectedVaultKey] = useState('GEMINI_API_KEY');
  const [vaultSecretInput, setVaultSecretInput] = useState('');

  // Caçador de Clientes Reais B2B (Web + Maps + Instagram + WhatsApp)
  const [huntNiche, setHuntNiche] = useState('Barbearia');
  const [huntCity, setHuntCity] = useState('Guaíra SP');
  const [huntVentureId, setHuntVentureId] = useState('');
  const [huntedLeads, setHuntedLeads] = useState<RealLeadItem[]>([]);
  const [huntingLoading, setHuntingLoading] = useState(false);
  const [myWaPhone, setMyWaPhone] = useState('');
  const [pairCodeLoading, setPairCodeLoading] = useState(false);
  const [autoOutreachMsg, setAutoOutreachMsg] = useState<string | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [deferredInstallPrompt, setDeferredInstallPrompt] = useState<any>(null);

  const requestMyWaPairingCode = async () => {
    const clean = myWaPhone.replace(/\D/g, '');
    if (clean.length < 10) {
      alert('Digita o teu DDD + Número do WhatsApp (ex: 17999998888)');
      return;
    }
    setPairCodeLoading(true);
    try {
      const res = await fetch('/api/whatsapp/pair-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: clean }),
      });
      const json = await res.json();
      if (!res.ok) {
        alert(json.detail || 'Erro ao pedir código de pareamento.');
      }
      await fetchOverview();
    } finally {
      setPairCodeLoading(false);
    }
  };

  const launchAutonomousOutreach = async () => {
    setHuntingLoading(true);
    setAutoOutreachMsg(null);
    try {
      const res = await fetch('/api/leads/auto-outreach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          niche: huntNiche,
          city: huntCity,
          venture_id: huntVentureId || null,
        }),
      });
      const json = await res.json();
      if (!json.ok) {
        setAutoOutreachMsg(
          '⚠️ Conecta primeiro o teu WhatsApp no quadro abaixo com o Código de 8 Dígitos para os agentes enviarem mensagens sozinhos!'
        );
      } else {
        if (json.leads) setHuntedLeads(json.leads);
        setAutoOutreachMsg(
          `✅ PILOTO COMERCIAL EM EXECUÇÃO! ${json.queued_with_phone} empresas reais com telefone entraram na fila automática (envio humano seguro a cada 25s). Quando responderem, o Agente Closer tira dúvidas e manda o teu Pix Asaas sozinho!`
        );
      }
      await fetchOverview();
    } finally {
      setHuntingLoading(false);
    }
  };

  const agentSendSingleNow = async (lead: RealLeadItem) => {
    setBusy(true);
    try {
      const res = await fetch('/api/leads/send-one', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_name: lead.business_name,
          phone_digits: lead.phone_digits,
          message: lead.whatsapp_pitch,
          venture_name: lead.venture_name,
          price_usd: lead.price_usd,
        }),
      });
      const json = await res.json();
      if (json.ok) {
        setAutoOutreachMsg(`✅ Agente enviou proposta no WhatsApp para ${lead.business_name}!`);
      } else if (json.error === 'WHATSAPP_NOT_CONNECTED') {
        setAutoOutreachMsg('⚠️ Conecta primeiro o teu WhatsApp com o Código de 8 Dígitos acima!');
      } else {
        setAutoOutreachMsg(`ℹ️ Este telefone (${lead.phone_display}) é apenas fixo sem conta WhatsApp ativa.`);
      }
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const handler = (e: any) => {
      e.preventDefault();
      setDeferredInstallPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const installAndroidApp = async () => {
    if (deferredInstallPrompt) {
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
      setDeferredInstallPrompt(null);
    } else {
      alert(
        'Para instalar no Android:\n1. Toca nos 3 pontinhos (⋮) no canto superior direito do Chrome\n2. Toca em "Instalar aplicativo" (ou "Adicionar à tela inicial")!'
      );
    }
  };

  const resetRealMode = async () => {
    setBusy(true);
    try {
      await fetch('/api/system/reset-real-mode', { method: 'POST' });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const runRealLeadHunter = async (overrideNiche?: string, overrideCity?: string) => {
    const n = overrideNiche ?? huntNiche;
    const c = overrideCity ?? huntCity;
    if (!n.trim() || !c.trim()) return;
    setHuntingLoading(true);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 14000);
    try {
      const selectedVen =
        huntVentureId ||
        data?.ventures.find((v) =>
          n.toLowerCase().includes('pizz') || n.toLowerCase().includes('hamb')
            ? v.name.includes('ZapPedido')
            : n.toLowerCase().includes('clín') || n.toLowerCase().includes('odont')
            ? v.name.includes('NexusFlow')
            : v.name.includes('AgendaCorte')
        )?.id ||
        data?.ventures[0]?.id ||
        '';
      const res = await fetch('/api/leads/hunt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche: n, city: c, venture_id: selectedVen || null }),
        signal: controller.signal,
      });
      if (res.ok) {
        const json = await res.json();
        setHuntedLeads(json.leads || []);
      }
    } catch {
      // fallback safe: never freeze buttons
    } finally {
      clearTimeout(timer);
      setHuntingLoading(false);
    }
  };

  const createPixForRealLead = async (lead: RealLeadItem) => {
    setBusy(true);
    try {
      await fetch('/api/payments/invoices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: 'ASAAS_PIX',
          client_name: lead.business_name,
          client_email: 'cliente@assinatura.com.br',
          description: `${lead.venture_name} Mensal`,
          amount_usd: lead.price_usd,
        }),
      });
      await fetchOverview();
      setActiveTab('LEDGER');
    } finally {
      setBusy(false);
    }
  };

  const logEndRef = useRef<HTMLDivElement | null>(null);

  const fetchOverview = useCallback(async () => {
    try {
      const res = await fetch('/api/dashboard/overview');
      if (!res.ok) return;
      const json: DashboardOverview = await res.json();
      setData(json);
      setEvents((prev) => (prev.length === 0 ? json.telemetry : prev));
      if (!activePreviewProject && json.projects.length > 0) {
        setActivePreviewProject(json.projects[0]);
      }
      if (json.ventures && json.ventures.length > 0) {
        setActiveVenture((prev) =>
          prev ? json.ventures.find((v) => v.id === prev.id) ?? json.ventures[0] : json.ventures[0]
        );
      }
    } catch {
      // ignore during reconnect
    }
  }, [activePreviewProject]);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;
    let ws: WebSocket | null = null;
    let reconnectTimer: number | undefined;

    const connect = () => {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => setWsConnected(true);
      ws.onmessage = (msg) => {
        try {
          const parsed = JSON.parse(msg.data);
          if (parsed.type === 'SNAPSHOT' && Array.isArray(parsed.events)) {
            setEvents(parsed.events);
          } else if (parsed.type === 'EVENT' && parsed.event) {
            setEvents((prev) => [...prev.slice(-139), parsed.event]);
            fetchOverview();
          }
        } catch {
          // ignore
        }
      };
      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimer = window.setTimeout(connect, 2500);
      };
    };

    connect();
    return () => {
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [fetchOverview]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  const pendingApprovals = useMemo(
    () => data?.approvals.filter((a) => a.status === 'PENDING') ?? [],
    [data]
  );

  const pendingInvoices = useMemo(
    () => data?.invoices.filter((i) => i.status === 'PENDING') ?? [],
    [data]
  );

  const filteredLedger = useMemo(() => {
    if (!data) return [];
    if (ledgerFilter === 'ALL') return data.ledger;
    return data.ledger.filter((l) => l.entry_type === ledgerFilter);
  }, [data, ledgerFilter]);

  // Ações de Segurança Soberana
  const handleCeoLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setBusy(true);
    try {
      const res = await fetch('/api/security/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          password: loginPassword,
          totp_code: loginTotp || data?.security.current_totp_demo || '',
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        setLoginError(json.detail || 'Falha na autenticação 2FA.');
        return;
      }
      setJwtToken(json.token);
      setIsLocked(false);
      setLoginTotp('');
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const toggleKillSwitch = async () => {
    if (!data || busy) return;
    setBusy(true);
    try {
      await fetch('/api/security/kill-switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ engage: !data.security.kill_switch_active }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  // Ações Scheduler 24/7 & Growth
  const toggleAutopilot = async () => {
    if (!data || busy) return;
    setBusy(true);
    try {
      await fetch('/api/scheduler/autopilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !data.scheduler.autopilot_enabled }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const runCronJobNow = async (jobId: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await fetch(`/api/scheduler/jobs/${jobId}/run`, { method: 'POST' });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const toggleCronJob = async (job: ScheduledJobItem) => {
    await fetch(`/api/scheduler/jobs/${job.id}/toggle`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_enabled: !job.is_enabled }),
    });
    await fetchOverview();
  };

  const createCronJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cronName.trim() || busy) return;
    setBusy(true);
    try {
      await fetch('/api/scheduler/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: cronName,
          department: cronDept,
          directive_template: cronDirective,
          interval_seconds: Math.max(10, Number(cronInterval) || 30),
        }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const launchGrowthCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campTitle.trim() || busy) return;
    setBusy(true);
    try {
      await fetch('/api/growth/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: campTitle,
          channel: campChannel,
          directive: campDirective,
        }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const launchNewVenture = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!venName.trim() || busy) return;
    setBusy(true);
    try {
      await fetch('/api/ventures/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: venName,
          niche: venNiche,
          tagline: venTagline,
          monthly_price_usd: Number(venPrice) || 297,
          initial_customers: 4,
        }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const quickConvertSubscriber = async (ven: BusinessVentureItem) => {
    if (busy) return;
    setBusy(true);
    try {
      await fetch(`/api/ventures/${ven.id}/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_name: `Cliente B2B #${ven.active_customers + 1} (${ven.name})`,
          customer_email: `ceo${ven.active_customers + 1}@empresa.com.br`,
          customer_phone: '+5511998761234',
          provider: 'ASAAS_PIX',
        }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  // Comando Direto & Restantes Módulos
  const sendDirectCommand = async (customDirective?: string, customDept?: string) => {
    const text = (customDirective ?? directiveText).trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      await fetch('/api/command/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          directive: text,
          department: customDept ?? targetDept,
          priority: 'CRITICAL',
        }),
      });
      if (!customDirective) setDirectiveText('');
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const triggerSoftwareBuild = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projName.trim() || !projSpec.trim() || busy) return;
    setBusy(true);
    try {
      const res = await fetch('/api/factory/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: projName,
          project_type: projType,
          specification: projSpec,
          client_name: projClient,
          contract_value_usd: Number(projValue) || 1800,
          simulate_fault_healing: simulateHealing,
        }),
      });
      const out = await res.json();
      await fetchOverview();
      if (out?.project) {
        setActivePreviewProject(out.project);
      }
    } finally {
      setBusy(false);
    }
  };

  const deployProjectCloud = async (projectId: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await fetch(`/api/factory/projects/${projectId}/deploy-cloud`, { method: 'POST' });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const openProjectSource = async (projectId: string) => {
    const res = await fetch(`/api/factory/projects/${projectId}/source`);
    if (!res.ok) return;
    const json = await res.json();
    setInspectedSource(json);
    const firstFile = Object.keys(json.sources || {})[0] || 'index.html';
    setSelectedSourceFile(firstFile);
  };

  const decideApproval = async (approvalId: string, approve: boolean) => {
    if (busy) return;
    setBusy(true);
    try {
      await fetch(`/api/approvals/${approvalId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approve }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const toggleAgentStatus = async (agent: AgentItem) => {
    const nextStatus = agent.status === 'PAUSED' ? 'IDLE' : 'PAUSED';
    await fetch(`/api/agents/${agent.id}/toggle`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: nextStatus }),
    });
    await fetchOverview();
  };

  const refreshWhatsAppQR = async () => {
    setBusy(true);
    try {
      await fetch('/api/whatsapp/qr/refresh', { method: 'POST' });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const confirmWhatsAppPair = async () => {
    setBusy(true);
    try {
      await fetch('/api/whatsapp/pair', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: pairPhone }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const disconnectWhatsApp = async () => {
    setBusy(true);
    try {
      await fetch('/api/whatsapp/disconnect', { method: 'POST' });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const simulateEvolutionWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!waMessage.trim() || busy) return;
    setBusy(true);
    try {
      await fetch('/api/webhooks/evolution', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event: 'messages.upsert',
          contact_name: waName,
          contact_handle: waPhone,
          message: waMessage,
        }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const createInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!invClient.trim() || busy) return;
    setBusy(true);
    try {
      await fetch('/api/payments/invoices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: invProvider,
          client_name: invClient,
          client_email: invEmail,
          description: invDesc,
          amount_usd: Number(invAmount) || 1500,
        }),
      });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const settleInvoiceWebhook = async (invoiceId: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await fetch(`/api/webhooks/payments/${invoiceId}/settle`, { method: 'POST' });
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const copyText = (id: string, text: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedId(id);
    window.setTimeout(() => setCopiedId(null), 1800);
  };

  const runSemanticSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!memQuery.trim()) {
      setMemSearchResults(null);
      return;
    }
    const res = await fetch(`/api/memory/search?q=${encodeURIComponent(memQuery)}&namespace=ALL`);
    if (res.ok) {
      const json = await res.json();
      setMemSearchResults(json.results || []);
    }
  };

  const saveNewMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMemTitle.trim() || !newMemContent.trim() || busy) return;
    setBusy(true);
    try {
      await fetch('/api/memory/store', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          namespace: newMemNamespace,
          title: newMemTitle,
          content: newMemContent,
        }),
      });
      setNewMemTitle('');
      setNewMemContent('');
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const saveVaultSecret = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await fetch('/api/vault/secret', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key_name: selectedVaultKey,
          value: vaultSecretInput,
        }),
      });
      setVaultSecretInput('');
      await fetchOverview();
    } finally {
      setBusy(false);
    }
  };

  const balance = data?.balance ?? {
    total_revenue_usd: 0,
    total_expenses_usd: 0,
    llm_api_cost_usd: 0,
    sandbox_compute_cost_usd: 0,
    net_profit_usd: 0,
    profit_margin_pct: 0,
  };

  const waState = data?.whatsapp_instance;
  const autopilotOn = data?.scheduler.autopilot_enabled ?? false;
  const killSwitchOn = data?.security.kill_switch_active ?? false;

  // ===========================================================================
  // ECRÃ DE BLOQUEIO CRIPTOGRÁFICO SOBERANO (JWT HS256 + RFC 6238 TOTP 2FA)
  // ===========================================================================
  if (isLocked) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4">
        <form
          onSubmit={handleCeoLogin}
          className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-7 space-y-5 shadow-2xl"
        >
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-violet-500/20 border border-violet-500/40 flex items-center justify-center text-violet-300">
              <Lock className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Cofre Executivo Bloqueado</h1>
              <p className="text-xs text-slate-400">
                Autenticação Soberana CEO • JWT HS256 + 2FA TOTP (RFC 6238)
              </p>
            </div>
          </div>

          {data?.security.totp_qr_svg && (
            <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex items-center gap-4">
              <div
                className="shrink-0"
                dangerouslySetInnerHTML={{
                  __html: data.security.totp_qr_svg
                    .replace('width="192"', 'width="96"')
                    .replace('height="192"', 'height="96"'),
                }}
              />
              <div className="text-xs space-y-1">
                <div className="text-slate-400">Código 2FA TOTP Atual (Authenticator):</div>
                <div className="text-xl font-mono font-bold tracking-widest text-emerald-400">
                  {data.security.current_totp_demo}
                </div>
                <div className="text-[11px] text-slate-500">
                  Senha padrão: <code>empire2026</code>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Senha Mestre do CEO</label>
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-white"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Código 2FA TOTP (6 dígitos — vazio usa código ativo acima)
              </label>
              <input
                type="text"
                maxLength={6}
                value={loginTotp}
                onChange={(e) => setLoginTotp(e.target.value)}
                placeholder={data?.security.current_totp_demo ?? '000000'}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm font-mono tracking-widest text-emerald-300"
              />
            </div>
          </div>

          {loginError && (
            <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/40 text-xs text-rose-300">
              {loginError}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 cursor-pointer"
          >
            <Unlock className="w-4 h-4" />
            {busy ? 'Validando Assinatura Criptográfica...' : 'Desbloquear Império (Emitir JWT)'}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* BANNER DE EMERGÊNCIA QUANDO KILL-SWITCH ATIVO */}
      {killSwitchOn && (
        <div className="bg-rose-600 text-white px-5 py-2 text-xs font-bold flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 animate-bounce" />
            GLOBAL KILL-SWITCH ATIVO: Todos os departamentos, schedulers 24/7 e gastos de API estão
            congelados por ordem soberana.
          </div>
          <button
            onClick={toggleKillSwitch}
            className="px-3 py-1 rounded bg-white text-rose-700 font-extrabold cursor-pointer"
          >
            Restaurar Operação
          </button>
        </div>
      )}

      {/* HEADER SOBERANO v3.0 */}
      <header className="border-b border-slate-800/80 bg-slate-950/90 backdrop-blur sticky top-0 z-30">
        <div className="max-w-[1440px] mx-auto px-5 py-3.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Cpu className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold tracking-tight text-white">
                  AUTONOMOUS EMPIRE OS
                </h1>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  v3.0 • Full Autonomy 24/7
                </span>
                {jwtToken && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-violet-500/20 text-violet-300">
                    JWT+2FA VERIFIED
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                7 Departamentos Autónomos • Scheduler 24/7 • Growth Social • Stripe/Pix • Fábrica L2
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* INSTALAR APP ANDROID (PWA NATIVO) */}
            <button
              onClick={installAndroidApp}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-400/50 text-emerald-300 hover:bg-emerald-500/30 text-xs font-bold transition cursor-pointer"
              title="Instalar Painel como Aplicativo no Android"
            >
              <Download className="w-3.5 h-3.5" />
              Instalar App
            </button>

            {/* MODO CAIXA 100% REAL (ZERAR SIMULAÇÕES) */}
            <button
              onClick={resetRealMode}
              disabled={busy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/25 text-xs font-bold transition cursor-pointer"
              title="Zerar valores simulados e exibir exclusivamente Pix/Stripe reais pagos"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              Caixa 100% Real
            </button>

            {/* PILOTO AUTOMÁTICO 24/7 TOGGLE */}
            <button
              onClick={toggleAutopilot}
              disabled={busy || killSwitchOn}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-bold transition cursor-pointer ${
                autopilotOn
                  ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-lg shadow-emerald-500/25'
                  : 'bg-slate-900 text-slate-300 border-slate-700 hover:border-emerald-500/50'
              }`}
            >
              <Clock className={`w-3.5 h-3.5 ${autopilotOn ? 'animate-spin' : ''}`} />
              {autopilotOn ? 'Piloto 24/7: ATIVO' : 'Ligar Piloto 24/7'}
            </button>

            {/* KILL SWITCH */}
            <button
              onClick={toggleKillSwitch}
              disabled={busy}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold transition cursor-pointer ${
                killSwitchOn
                  ? 'bg-rose-500 text-white border-rose-400'
                  : 'bg-rose-950/40 text-rose-300 border-rose-500/40 hover:bg-rose-900/50'
              }`}
              title="Congelamento de Emergência Global"
            >
              <Power className="w-3.5 h-3.5" />
              {killSwitchOn ? 'Kill-Switch ON' : 'Kill-Switch'}
            </button>

            {/* LOCK CEO 2FA */}
            <button
              onClick={() => setIsLocked(true)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-violet-300 hover:border-violet-500/50 text-xs font-semibold cursor-pointer"
              title="Bloquear Painel com Senha + 2FA TOTP"
            >
              <Lock className="w-3.5 h-3.5" />
              2FA Lock
            </button>

            <a
              href="/api/system/export-monorepo.zip"
              download
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-cyan-500/15 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/25 text-xs font-bold transition"
              title="Descarregar Monorepo Completo Pronto para VPS / Docker"
            >
              <Download className="w-3.5 h-3.5" />
              Baixar .ZIP
            </a>

            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs">
              <span
                className={`w-2 h-2 rounded-full ${
                  wsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'
                }`}
              />
              <span className="text-slate-300 font-medium">{wsConnected ? 'WS' : '...'}</span>
            </div>

            <button
              onClick={fetchOverview}
              className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin text-emerald-400' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1440px] w-full mx-auto px-5 py-6 space-y-6 flex-1">
        {/* RIBBON FINANCEIRO & OPERACIONAL */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>RECEITA BRUTA ACUMULADA</span>
              <DollarSign className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-white">
                ${balance.total_revenue_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
              <span className="text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                MRR: ${(data?.holding_mrr_usd ?? 0).toLocaleString()}/mês
              </span>
            </div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>LUCRO LÍQUIDO & MARGEM</span>
              <TrendingUp className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-emerald-400">
                ${balance.net_profit_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
              <span className="text-xs font-bold text-cyan-300 bg-cyan-500/10 px-2 py-0.5 rounded">
                {balance.profit_margin_pct}% Margem
              </span>
            </div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>CUSTOS DE APIs, ADS & INFRA</span>
              <Wallet className="w-4 h-4 text-rose-400" />
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-slate-100">
                ${balance.total_expenses_usd.toFixed(4)}
              </span>
              <span className="text-[11px] text-slate-400">
                LLM: ${balance.llm_api_cost_usd.toFixed(4)} • Sbx: $
                {balance.sandbox_compute_cost_usd.toFixed(4)}
              </span>
            </div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>AGENTES & CICLOS 24/7</span>
              <Bot className="w-4 h-4 text-violet-400" />
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-2xl font-bold text-white">
                {data?.agents.filter((a) => a.status !== 'PAUSED').length ?? 7} /{' '}
                {data?.agents.length ?? 7} Ativos
              </span>
              <span className="text-xs font-semibold text-violet-300 bg-violet-500/15 px-2 py-0.5 rounded">
                {data?.scheduler.total_cycles_executed ?? 0} Ciclos Cron
              </span>
            </div>
          </div>
        </section>

        {/* CONSOLA DE COMANDO DIRETO AO ORQUESTRADOR MESTRE */}
        <section className="bg-gradient-to-r from-slate-900 via-slate-900 to-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Comando Soberano ao Agente Orquestrador Mestre
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() =>
                  sendDirectCommand(
                    'Publicar campanha viral de aquisição B2B no LinkedIn e Reels',
                    'GROWTH_SOCIAL'
                  )
                }
                disabled={busy || killSwitchOn}
                className="text-xs px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-pink-300 border border-slate-700 transition cursor-pointer"
              >
                + Disparar Campanha Growth/Social
              </button>
              <button
                onClick={() =>
                  sendDirectCommand(
                    'Executar campanha outbound B2B para fechar novo contrato SaaS Enterprise',
                    'SALES'
                  )
                }
                disabled={busy || killSwitchOn}
                className="text-xs px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 transition cursor-pointer"
              >
                + Prospecção & Venda B2B
              </button>
              <button
                onClick={() =>
                  sendDirectCommand(
                    'Executar auditoria financeira completa de margens, ROAS e consumo de tokens',
                    'FINANCE'
                  )
                }
                disabled={busy || killSwitchOn}
                className="text-xs px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 transition cursor-pointer"
              >
                + Auditar Balanço (CFO)
              </button>
            </div>
          </div>

          <div className="flex flex-col md:flex-row gap-3">
            <select
              value={targetDept}
              onChange={(e) => setTargetDept(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="AUTO">Auto-Roteamento Inteligente (Mestre)</option>
              <option value="GROWTH_SOCIAL">Tráfego, Conteúdo Social & SEO</option>
              <option value="SALES">Departamento Vendas & Prospecção</option>
              <option value="SOFTWARE_FACTORY">Fábrica de Software Nível 2</option>
              <option value="SUPPORT">Suporte 24h (WhatsApp/Email)</option>
              <option value="FINANCE">Departamento Financeiro</option>
              <option value="META_CREATOR">Meta-Agente (Criar Sub-Agente)</option>
              {data?.agents
                .filter((a) => a.is_dynamic)
                .map((da) => (
                  <option key={da.id} value={`DYNAMIC:${da.id}`}>
                    [Meta] {da.name}
                  </option>
                ))}
            </select>

            <input
              type="text"
              value={directiveText}
              onChange={(e) => setDirectiveText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendDirectCommand()}
              placeholder="Ordena qualquer missão (ex: 'Lançar campanha Google Ads SaaS', 'Criar jogo espacial HTML5', 'Fechar contrato logística')..."
              className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />

            <button
              onClick={() => sendDirectCommand()}
              disabled={busy || killSwitchOn || !directiveText.trim()}
              className="px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 transition cursor-pointer"
            >
              <Send className="w-4 h-4" />
              {busy ? 'Executando...' : 'Executar Ordem'}
            </button>
          </div>
        </section>

        {/* NAVEGAÇÃO POR MÓDULOS DO PAINEL ADM v3.0 */}
        <nav className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
          {(
            [
              {
                id: 'LEAD_HUNTER',
                label: '🎯 Caçador de Clientes Reais',
                icon: Search,
              },
              {
                id: 'VENTURES',
                label: `Empresas & Produtos SaaS (${data?.ventures.length ?? 0})`,
                icon: Rocket,
              },
              { id: 'OVERVIEW', label: 'Departamentos & Telemetria', icon: Layers },
              {
                id: 'AUTOPILOT_GROWTH',
                label: `Piloto 24/7 & Growth Social (${data?.growth_campaigns.length ?? 0})`,
                icon: Megaphone,
              },
              {
                id: 'FACTORY',
                label: `Fábrica L2 • Self-Healing (${data?.projects.length ?? 0})`,
                icon: Factory,
              },
              {
                id: 'LEDGER',
                label: `Stripe / Pix & Ledger (${pendingInvoices.length} abertas)`,
                icon: CreditCard,
              },
              {
                id: 'OMNICHANNEL',
                label: `WhatsApp QR (${waState?.status ?? 'QR'}) & CRM`,
                icon: QrCode,
              },
              {
                id: 'META',
                label: `Meta-Agente (${pendingApprovals.length})`,
                icon: Sparkles,
              },
              {
                id: 'MEMORY_LLM',
                label: 'Segurança 2FA, Vault & pgvector',
                icon: BrainCircuit,
              },
            ] as const
          ).map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition cursor-pointer ${
                  active
                    ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40'
                    : 'bg-slate-900/70 text-slate-400 border border-slate-800 hover:text-slate-200'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* =================================================================
            TAB CAÇADOR DE CLIENTES REAIS (WEB + MAPS + INSTAGRAM + WHATSAPP)
        ================================================================== */}
        {activeTab === 'LEAD_HUNTER' && (
          <div className="space-y-6">
            {/* CENTRAL DE DISPARO & FECHAMENTO 100% AUTÓNOMO NO WHATSAPP */}
            <div className="bg-gradient-to-r from-emerald-950/60 via-slate-900 to-slate-900 border border-emerald-500/40 rounded-2xl p-5 space-y-4 shadow-xl">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-bold text-emerald-300 flex items-center gap-2">
                    <Bot className="w-5 h-5 text-emerald-400" />
                    Agentes em Piloto Automático no WhatsApp (Enviam, Respondem & Mandam Pix Sozinhos!)
                  </h2>
                  <p className="text-xs text-slate-300 mt-0.5">
                    Conecta o teu WhatsApp abaixo com o Código de 8 Dígitos (no próprio celular, sem precisar doutro aparelho). Os agentes falam apenas com as lojas abordadas (protege 100% as tuas conversas pessoais!).
                  </p>
                </div>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold border ${
                    waState?.status === 'CONNECTED'
                      ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300'
                      : 'bg-amber-500/20 border-amber-400/50 text-amber-300'
                  }`}
                >
                  {waState?.status === 'CONNECTED'
                    ? `🟢 WhatsApp Ativo (+${waState.paired_number || 'Conectado'})`
                    : '⚡ Falta Conectar Teu WhatsApp (10s)'}
                </span>
              </div>

              {waState?.status !== 'CONNECTED' ? (
                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
                  <div className="flex flex-col sm:flex-row gap-2.5">
                    <input
                      value={myWaPhone}
                      onChange={(e) => setMyWaPhone(e.target.value)}
                      placeholder="Teu WhatsApp c/ DDD (ex: 17999998888)"
                      className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500"
                    />
                    <button
                      onClick={requestMyWaPairingCode}
                      disabled={pairCodeLoading}
                      className="px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-sm cursor-pointer transition"
                    >
                      {pairCodeLoading ? 'Gerando Código Oficial...' : '1. Gerar Código de 8 Dígitos'}
                    </button>
                  </div>

                  {waState?.pairing_code && waState.status === 'PAIRING_CODE_READY' && (
                    <div className="bg-emerald-950/50 border border-emerald-500/50 rounded-xl p-4 text-center space-y-2">
                      <p className="text-xs text-emerald-200 font-semibold">
                        TEU CÓDIGO OFICIAL DO WHATSAPP ( Toca para copiar ):
                      </p>
                      <button
                        onClick={() => navigator.clipboard.writeText(waState.pairing_code.replace('-', ''))}
                        className="text-2xl sm:text-3xl font-mono font-extrabold tracking-widest text-white bg-slate-900 px-6 py-2.5 rounded-xl border border-emerald-400 cursor-pointer"
                      >
                        {waState.pairing_code}
                      </button>
                      <p className="text-xs text-slate-300">
                        Agora abre o teu <strong>WhatsApp</strong> → <strong>3 pontinhos (⋮)</strong> →{' '}
                        <strong>Aparelhos conectados</strong> → <strong>Conectar um aparelho</strong> → lá embaixo toca em{' '}
                        <strong>&quot;Conectar com número de telefone&quot;</strong> e digita o código acima!
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={launchAutonomousOutreach}
                    disabled={huntingLoading}
                    className="px-5 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-extrabold text-sm flex items-center gap-2 shadow-lg shadow-emerald-500/25 cursor-pointer transition"
                  >
                    <Rocket className="w-4 h-4" />
                    {huntingLoading
                      ? 'Iniciando Disparo Automático...'
                      : `🤖 Mandar Agentes Abordarem ${huntNiche} em ${huntCity} Sozinhos!`}
                  </button>
                  <span className="text-xs text-slate-400">
                    Intervalo seguro anti-banimento (25s por loja) + Resposta & Pix Asaas 100% automáticos!
                  </span>
                </div>
              )}

              {autoOutreachMsg && (
                <div className="bg-slate-950 border border-emerald-500/40 rounded-xl px-4 py-2.5 text-xs text-emerald-300 font-semibold">
                  {autoOutreachMsg}
                </div>
              )}
            </div>

            <div className="bg-slate-900 border border-emerald-500/30 rounded-2xl p-5 space-y-4 shadow-xl">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <Search className="w-5 h-5 text-emerald-400" />
                    Caçador de Clientes Reais B2B (Google Maps • Instagram • Web)
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Busca estabelecimentos reais que existem de verdade na tua cidade ou em qualquer região do Brasil, gera abordagem com Gemini 3 Flash e dispara no WhatsApp + Pix Asaas em 1 toque.
                  </p>
                </div>
                <button
                  onClick={resetRealMode}
                  disabled={busy}
                  className="px-3 py-1.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 text-xs font-bold cursor-pointer"
                >
                  Zerar Simulações (Caixa 100% Real)
                </button>
              </div>

              {/* Atalhos Rápidos de Nichos e Cidades */}
              <div className="flex flex-wrap gap-1.5">
                {['Barbearia', 'Pizzaria', 'Hamburgueria', 'Clínica Odontológica', 'Salão de Beleza', 'Estética'].map(
                  (preset) => (
                    <button
                      key={preset}
                      onClick={() => setHuntNiche(preset)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold border cursor-pointer ${
                        huntNiche === preset
                          ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                      }`}
                    >
                      {preset}
                    </button>
                  )
                )}
                <span className="text-slate-600 px-1">|</span>
                {['Guaíra SP', 'Barretos SP', 'Ribeirão Preto SP', 'Franca SP', 'São José do Rio Preto SP'].map(
                  (cityPreset) => (
                    <button
                      key={cityPreset}
                      onClick={() => setHuntCity(cityPreset)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold border cursor-pointer ${
                        huntCity === cityPreset
                          ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                      }`}
                    >
                      📍 {cityPreset}
                    </button>
                  )
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1 font-semibold">
                    Nicho / Tipo de Comércio
                  </label>
                  <input
                    value={huntNiche}
                    onChange={(e) => setHuntNiche(e.target.value)}
                    placeholder="Ex: Barbearia, Pizzaria..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1 font-semibold">
                    Cidade + Estado
                  </label>
                  <input
                    value={huntCity}
                    onChange={(e) => setHuntCity(e.target.value)}
                    placeholder="Ex: Guaíra SP"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1 font-semibold">
                    Produto SaaS p/ Ofertar
                  </label>
                  <select
                    value={huntVentureId}
                    onChange={(e) => setHuntVentureId(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-emerald-300"
                  >
                    <option value="">Auto-Selecionar pelo Nicho</option>
                    {data?.ventures.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} (${v.monthly_price_usd}/mês)
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-end">
                  <button
                    onClick={() => runRealLeadHunter()}
                    disabled={huntingLoading}
                    className="w-full py-2.5 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 transition cursor-pointer"
                  >
                    <Search className="w-4 h-4" />
                    {huntingLoading ? 'Buscando na Web Real...' : 'Buscar Empresas Reais'}
                  </button>
                </div>
              </div>
            </div>

            {/* Resultados Reais Encontrados */}
            {huntedLeads.length === 0 ? (
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center space-y-2">
                <p className="text-sm text-slate-300 font-semibold">
                  Pronto para encontrar os teus primeiros clientes reais!
                </p>
                <p className="text-xs text-slate-400">
                  Escolhe acima o nicho (ex: <strong>Barbearia</strong> ou <strong>Pizzaria</strong>) e a cidade (ex: <strong>Guaíra SP</strong>) e toca em <strong>Buscar Empresas Reais</strong>.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {huntedLeads.map((lead) => (
                  <div
                    key={lead.id}
                    className="bg-slate-900 border border-slate-800 hover:border-emerald-500/40 rounded-2xl p-4 flex flex-col justify-between space-y-3 transition"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-sm font-bold text-white">{lead.business_name}</h3>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 font-bold shrink-0">
                          R$ {lead.price_brl}/mês
                        </span>
                      </div>

                      <div className="flex flex-wrap gap-2 text-[11px]">
                        <span className="text-cyan-300 font-medium">📍 {lead.city}</span>
                        {lead.phone_display && (
                          <span className="text-emerald-400 font-mono font-bold">
                            📞 {lead.phone_display}
                          </span>
                        )}
                        {lead.instagram && (
                          <span className="text-pink-300 font-semibold">{lead.instagram}</span>
                        )}
                      </div>

                      {lead.snippet && (
                        <p className="text-xs text-slate-400 line-clamp-2">{lead.snippet}</p>
                      )}

                      <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-2.5 text-[11px] text-slate-300 whitespace-pre-line">
                        {lead.whatsapp_pitch}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 pt-1">
                      {lead.phone_digits && waState?.status === 'CONNECTED' && (
                        <button
                          onClick={() => agentSendSingleNow(lead)}
                          disabled={busy}
                          className="flex-1 min-w-[165px] py-2 px-3 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-bold text-xs flex items-center justify-center gap-1.5 cursor-pointer transition"
                        >
                          <Bot className="w-3.5 h-3.5" />
                          🤖 Agente Enviar Sozinho
                        </button>
                      )}

                      <a
                        href={lead.whatsapp_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 min-w-[155px] py-2 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-1.5 transition"
                      >
                        <MessageSquare className="w-3.5 h-3.5" />
                        {lead.phone_digits ? 'Enviar no WhatsApp Direto' : 'Abrir Msg no WhatsApp'}
                      </a>

                      <a
                        href={lead.maps_url}
                        target="_blank"
                        rel="noreferrer"
                        className="py-2 px-3 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/40 text-cyan-300 font-bold text-xs flex items-center gap-1 transition"
                        title="Abrir ficha e telefone oficial deste local no Google Maps"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        Maps / Telefone
                      </a>

                      <a
                        href={lead.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="py-2 px-3 rounded-xl bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500/40 text-pink-300 font-bold text-xs flex items-center gap-1 transition"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        Perfil / Site
                      </a>

                      <button
                        onClick={() => createPixForRealLead(lead)}
                        disabled={busy}
                        className="py-2 px-3 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 font-bold text-xs flex items-center gap-1 cursor-pointer transition"
                      >
                        <QrCode className="w-3.5 h-3.5" />
                        Emitir Pix Asaas
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* =================================================================
            TAB 0: PORTFÓLIO DE EMPRESAS COMERCIAIS & VENTURE BUILDER LIVE
        ================================================================== */}
        {activeTab === 'VENTURES' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Coluna Esquerda: Portfólio da Holding + Lançador de Novo Negócio */}
            <div className="lg:col-span-5 space-y-5">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Rocket className="w-5 h-5 text-emerald-400" />
                    <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                      Empresas Operadas pela Holding ({data?.ventures.length ?? 0})
                    </h2>
                  </div>
                  <span className="text-xs font-bold text-emerald-400 bg-emerald-500/15 px-2.5 py-0.5 rounded-full">
                    MRR Total: ${(data?.holding_mrr_usd ?? 0).toLocaleString()}/mês
                  </span>
                </div>

                <div className="space-y-3 max-h-[310px] overflow-y-auto">
                  {data?.ventures.map((v) => (
                    <div
                      key={v.id}
                      className={`p-4 rounded-2xl border transition ${
                        activeVenture?.id === v.id
                          ? 'bg-slate-950 border-emerald-500/60'
                          : 'bg-slate-950/60 border-slate-800'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <span className="font-bold text-sm text-white">{v.name}</span>
                          <span className="ml-2 text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                            ${v.monthly_price_usd}/mês
                          </span>
                        </div>
                        <span className="text-xs font-bold text-cyan-300">
                          MRR: ${v.mrr_usd.toLocaleString()}
                        </span>
                      </div>

                      <p className="text-xs text-slate-400 mt-1">{v.niche}</p>

                      <div className="mt-2.5 flex items-center justify-between text-[11px] text-slate-300">
                        <span>
                          Assinantes Ativos:{' '}
                          <strong className="text-emerald-400">{v.active_customers}</strong>
                        </span>
                        <span>
                          Faturação Total:{' '}
                          <strong className="text-white">
                            ${v.total_revenue_usd.toLocaleString()}
                          </strong>
                        </span>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          onClick={() => setActiveVenture(v)}
                          className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 font-bold cursor-pointer"
                        >
                          Abrir SaaS & Checkout Live
                        </button>
                        <button
                          onClick={() => quickConvertSubscriber(v)}
                          disabled={busy || killSwitchOn}
                          className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold cursor-pointer"
                        >
                          + Converter Assinante (+${v.monthly_price_usd})
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Lançador de Nova Empresa em 1 Clique */}
              <form
                onSubmit={launchNewVenture}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-violet-300">
                    + Construir & Lançar Nova Empresa SaaS Completa
                  </span>
                  <div className="flex gap-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        setVenName('ImobPulse AI');
                        setVenNiche('Imobiliárias & Incorporadoras');
                        setVenPrice('247');
                        setVenTagline(
                          'Qualificação WhatsApp de Compradores 24h & Agendamento de Visitas IA'
                        );
                      }}
                      className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 hover:text-white cursor-pointer"
                    >
                      Preset Imobiliário
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setVenName('FinRecover AI');
                        setVenNiche('SaaS, Escolas & Assinaturas');
                        setVenPrice('347');
                        setVenTagline(
                          'Recuperação Autónoma de Inadimplência via WhatsApp + Pix Instantâneo'
                        );
                      }}
                      className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 hover:text-white cursor-pointer"
                    >
                      Preset Cobrança IA
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2.5">
                  <input
                    value={venName}
                    onChange={(e) => setVenName(e.target.value)}
                    placeholder="Marca do Produto"
                    className="col-span-2 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                    required
                  />
                  <input
                    type="number"
                    value={venPrice}
                    onChange={(e) => setVenPrice(e.target.value)}
                    placeholder="USD/mês"
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-emerald-400 font-bold"
                    required
                  />
                </div>

                <input
                  value={venNiche}
                  onChange={(e) => setVenNiche(e.target.value)}
                  placeholder="Nicho de Mercado Alvo"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                  required
                />

                <textarea
                  rows={2}
                  value={venTagline}
                  onChange={(e) => setVenTagline(e.target.value)}
                  placeholder="Proposta única de valor..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white"
                  required
                />

                <button
                  type="submit"
                  disabled={busy || killSwitchOn}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 hover:opacity-95 text-slate-950 font-extrabold text-xs cursor-pointer"
                >
                  {busy
                    ? 'Orquestrando Fábrica + Sub-Agente + Ads + Checkout...'
                    : 'Construir Produto, Criar Squad IA, Lançar Ads & Iniciar Vendas'}
                </button>
              </form>
            </div>

            {/* Coluna Direita: Viewport Ao Vivo do Produto SaaS Comercial + Checkout Integrado */}
            <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden flex flex-col min-h-[650px]">
              <div className="px-4 py-3 bg-slate-950 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="text-xs font-bold text-white">
                    PRODUTO COMERCIAL EM OPERAÇÃO:{' '}
                    {activeVenture ? activeVenture.name : 'Seleciona uma empresa'}
                  </span>
                  <span className="ml-2 text-[11px] text-emerald-400">
                    (Testa o Checkout Self-Serve abaixo — fatura direto no teu Ledger!)
                  </span>
                </div>
                {activeVenture?.public_url && (
                  <a
                    href={activeVenture.public_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-cyan-400 hover:underline flex items-center gap-1"
                  >
                    Abrir Site Público do SaaS <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>

              {activeVenture?.public_url ? (
                <iframe
                  key={activeVenture.public_url}
                  src={activeVenture.public_url}
                  title={activeVenture.name}
                  className="w-full flex-1 bg-slate-950 border-0 min-h-[600px]"
                />
              ) : (
                <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                  Nenhuma unidade de negócio selecionada.
                </div>
              )}
            </div>
          </div>
        )}

        {/* =================================================================
            TAB 1: VISÃO GERAL — 7 DEPARTAMENTOS + TERMINAL WS LIVE
        ================================================================== */}
        {activeTab === 'OVERVIEW' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 space-y-4">
              {pendingApprovals.length > 0 && (
                <div className="bg-amber-950/25 border border-amber-500/40 rounded-2xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-300 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4" />
                      Autorização Direta Requerida pelo Meta-Agente
                    </span>
                    <span className="text-[11px] text-amber-400">Human-in-the-Loop</span>
                  </div>
                  {pendingApprovals.map((ap) => (
                    <div
                      key={ap.id}
                      className="bg-slate-950/80 border border-amber-500/20 rounded-xl p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div>
                        <div className="font-semibold text-sm text-white">{ap.title}</div>
                        <p className="text-xs text-slate-400 mt-0.5">{ap.rationale}</p>
                        <div className="text-[11px] text-emerald-400 font-medium mt-1">
                          ROI Projetado: +${ap.projected_roi_usd.toLocaleString()}/mês • Tools:{' '}
                          {(ap.payload_json.tools_manifest || []).join(', ')}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => decideApproval(ap.id, true)}
                          className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs cursor-pointer"
                        >
                          Autorizar Agente
                        </button>
                        <button
                          onClick={() => decideApproval(ap.id, false)}
                          className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-rose-950 text-slate-300 text-xs cursor-pointer"
                        >
                          Rejeitar
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300">
                  Departamentos Autónomos ({data?.agents.length ?? 0})
                </h2>
                <span className="text-xs text-slate-500">
                  Piloto 24/7: {autopilotOn ? 'ATIVO' : 'MANUAL'}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {data?.agents.map((ag) => (
                  <div
                    key={ag.id}
                    className={`rounded-2xl p-4 border transition ${
                      ag.is_dynamic
                        ? 'bg-violet-950/15 border-violet-500/35'
                        : 'bg-slate-900/90 border-slate-800'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              ag.status === 'RUNNING'
                                ? 'bg-amber-400 animate-ping'
                                : ag.status === 'PAUSED'
                                ? 'bg-rose-500'
                                : 'bg-emerald-400'
                            }`}
                          />
                          <h3 className="font-bold text-sm text-white">{ag.name}</h3>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                            {ag.department}
                          </span>
                          <span className="text-[10px] font-mono text-cyan-400">
                            {ag.model_name}
                          </span>
                          {ag.is_dynamic && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-violet-500/20 text-violet-300">
                              META-SPAWNED
                            </span>
                          )}
                        </div>
                      </div>

                      <button
                        onClick={() => toggleAgentStatus(ag)}
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
                        title={ag.status === 'PAUSED' ? 'Retomar Agente' : 'Pausar Agente'}
                      >
                        {ag.status === 'PAUSED' ? (
                          <Play className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Pause className="w-3.5 h-3.5 text-slate-400" />
                        )}
                      </button>
                    </div>

                    <p className="text-xs text-slate-400 mt-2.5 line-clamp-2">
                      {ag.role_description}
                    </p>

                    <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                      <span>
                        Missões: <strong className="text-slate-200">{ag.tasks_completed}</strong>
                      </span>
                      <span>
                        Custo API:{' '}
                        <strong className="text-rose-300">${ag.total_cost_usd.toFixed(4)}</strong>
                      </span>
                      <span>
                        SLA: <strong className="text-emerald-400">{ag.success_rate}%</strong>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="lg:col-span-5 flex flex-col gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden flex flex-col h-[440px]">
                <div className="px-4 py-3 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
                    <Terminal className="w-4 h-4 text-emerald-400" />
                    BARRAMENTO DE EVENTOS EM TEMPO REAL (REDIS / WS)
                  </div>
                  <span className="text-[11px] font-mono text-slate-500">
                    {events.length} eventos
                  </span>
                </div>

                <div className="p-3.5 overflow-y-auto flex-1 font-mono text-xs space-y-2 bg-slate-950/60">
                  {events.map((ev) => {
                    const badgeColor =
                      ev.level === 'SUCCESS'
                        ? 'text-emerald-400'
                        : ev.level === 'FINANCE'
                        ? 'text-cyan-400'
                        : ev.level === 'WARNING'
                        ? 'text-amber-400'
                        : ev.level === 'ERROR'
                        ? 'text-rose-400'
                        : 'text-slate-400';
                    return (
                      <div
                        key={ev.id}
                        className="border-l-2 border-slate-800 pl-2.5 py-0.5 leading-relaxed"
                      >
                        <span className="text-slate-600">[{ev.timestamp.slice(11, 19)}]</span>{' '}
                        <span className={`font-semibold ${badgeColor}`}>[{ev.agent}]</span>{' '}
                        <span className="text-slate-200">{ev.message}</span>
                      </div>
                    );
                  })}
                  <div ref={logEndRef} />
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-3">
                  Últimas Execuções do Grafo (Tasks)
                </h3>
                <div className="space-y-2.5 max-h-[210px] overflow-y-auto">
                  {(data?.tasks ?? []).slice(0, 6).map((t) => (
                    <div
                      key={t.id}
                      className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-2.5 text-xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-slate-200 truncate">{t.title}</span>
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                            t.status === 'COMPLETED'
                              ? 'bg-emerald-500/15 text-emerald-400'
                              : 'bg-amber-500/15 text-amber-300'
                          }`}
                        >
                          {t.status}
                        </span>
                      </div>
                      {t.result_summary && (
                        <p className="text-slate-400 mt-1 line-clamp-2">{t.result_summary}</p>
                      )}
                    </div>
                  ))}
                  {(data?.tasks.length ?? 0) === 0 && (
                    <p className="text-xs text-slate-500">
                      Liga o Piloto 24/7 no topo ou envia uma ordem direta.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================
            TAB 2: SCHEDULER AUTÓNOMO 24/7 & AGENTE TRÁFEGO / SOCIAL / SEO
        ================================================================== */}
        {activeTab === 'AUTOPILOT_GROWTH' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Coluna Esquerda: Scheduler 24/7 + Novo Pipeline */}
            <div className="lg:col-span-5 space-y-5">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock className="w-5 h-5 text-emerald-400" />
                    <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                      Scheduler Autónomo 24/7 (Cron Daemon)
                    </h2>
                  </div>
                  <button
                    onClick={toggleAutopilot}
                    disabled={busy || killSwitchOn}
                    className={`px-3 py-1 rounded-lg text-xs font-bold cursor-pointer ${
                      autopilotOn
                        ? 'bg-emerald-500 text-slate-950'
                        : 'bg-slate-800 text-emerald-300 border border-emerald-500/40'
                    }`}
                  >
                    {autopilotOn ? 'Desligar Piloto 24/7' : 'Ativar Piloto 24/7'}
                  </button>
                </div>

                <p className="text-xs text-slate-400">
                  Quando ativo, o daemon executa continuamente os pipelines habilitados abaixo em
                  background e injeta vendas, campanhas e auditorias no teu Dashboard em tempo real.
                </p>

                <div className="space-y-2.5">
                  {data?.scheduled_jobs.map((job) => (
                    <div
                      key={job.id}
                      className="bg-slate-950 border border-slate-800 rounded-xl p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <span className="font-bold text-xs text-white">{job.name}</span>
                          <span className="ml-2 text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-300">
                            a cada {job.interval_seconds}s • {job.department}
                          </span>
                        </div>
                        <span className="text-[11px] font-mono text-emerald-400">
                          {job.runs_count}x
                        </span>
                      </div>

                      {job.last_result && (
                        <p className="text-[11px] text-slate-400 line-clamp-2">{job.last_result}</p>
                      )}

                      <div className="flex items-center gap-2 pt-1">
                        <button
                          onClick={() => runCronJobNow(job.id)}
                          disabled={busy || killSwitchOn}
                          className="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-[11px] font-bold cursor-pointer"
                        >
                          Executar Ciclo Agora
                        </button>
                        <button
                          onClick={() => toggleCronJob(job)}
                          className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 text-[11px] cursor-pointer"
                        >
                          {job.is_enabled ? 'Pausar Cron' : 'Reativar Cron'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                <form
                  onSubmit={createCronJob}
                  className="pt-3 border-t border-slate-800 space-y-2.5"
                >
                  <div className="text-xs font-bold text-slate-300">
                    + Adicionar Novo Pipeline Recorrente 24/7
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <input
                      value={cronName}
                      onChange={(e) => setCronName(e.target.value)}
                      placeholder="Nome do Job"
                      className="col-span-2 bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white"
                      required
                    />
                    <input
                      type="number"
                      min={10}
                      value={cronInterval}
                      onChange={(e) => setCronInterval(e.target.value)}
                      placeholder="Segundos"
                      className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-emerald-400 font-mono"
                    />
                  </div>
                  <select
                    value={cronDept}
                    onChange={(e) => setCronDept(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white"
                  >
                    <option value="SALES">Vendas & Prospecção</option>
                    <option value="GROWTH_SOCIAL">Tráfego, Social & SEO</option>
                    <option value="FINANCE">Auditoria Financeira</option>
                  </select>
                  <input
                    value={cronDirective}
                    onChange={(e) => setCronDirective(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white"
                    required
                  />
                  <button
                    type="submit"
                    disabled={busy}
                    className="w-full py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-emerald-300 font-bold text-xs cursor-pointer"
                  >
                    Agendar Pipeline Autónomo
                  </button>
                </form>
              </div>
            </div>

            {/* Coluna Direita: Estúdio Growth, Conteúdo Social & Ads */}
            <div className="lg:col-span-7 space-y-5">
              <form
                onSubmit={launchGrowthCampaign}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4"
              >
                <div className="flex items-center gap-2">
                  <Megaphone className="w-5 h-5 text-pink-400" />
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                    Agente de Tráfego, Conteúdo Social & SEO Programático
                  </h2>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <input
                    value={campTitle}
                    onChange={(e) => setCampTitle(e.target.value)}
                    placeholder="Título da Campanha"
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                    required
                  />
                  <select
                    value={campChannel}
                    onChange={(e) => setCampChannel(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                  >
                    <option value="LINKEDIN_B2B">LinkedIn B2B Thought Leadership</option>
                    <option value="INSTAGRAM_REELS">Instagram / TikTok Reels Script</option>
                    <option value="META_GOOGLE_ADS">Meta & Google Performance Ads</option>
                    <option value="SEO_ARTICLE">Artigo Pilar SEO Programático</option>
                    <option value="X_THREAD">X / Twitter Thread Viral</option>
                  </select>
                </div>

                <textarea
                  rows={2}
                  value={campDirective}
                  onChange={(e) => setCampDirective(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-white"
                  required
                />

                <button
                  type="submit"
                  disabled={busy || killSwitchOn}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-pink-500 to-violet-500 hover:opacity-95 text-white font-bold text-xs cursor-pointer"
                >
                  {busy
                    ? 'Gerando Copy, Publicando & Capturando Leads...'
                    : 'Sintetizar & Publicar Campanha Multicanal Agora'}
                </button>
              </form>

              <div className="space-y-3 max-h-[460px] overflow-y-auto">
                {data?.growth_campaigns.map((c) => (
                  <div
                    key={c.id}
                    className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <span className="font-bold text-sm text-white">{c.title}</span>
                        <span className="ml-2 text-[10px] font-mono px-2 py-0.5 rounded bg-pink-500/15 text-pink-300">
                          {c.channel}
                        </span>
                      </div>
                      <span className="text-xs font-bold text-emerald-400">
                        +${c.attributed_revenue_usd.toLocaleString()} gerados ({c.leads_captured}{' '}
                        leads)
                      </span>
                    </div>

                    <div className="text-xs font-semibold text-cyan-300">
                      Hook: “{c.hook_headline}”
                    </div>

                    <pre className="bg-slate-950/80 border border-slate-800 rounded-xl p-3 text-xs font-sans text-slate-300 whitespace-pre-wrap">
                      {c.content_body}
                    </pre>

                    <div className="flex flex-wrap gap-4 text-[11px] text-slate-400 pt-1">
                      <span>
                        Impressões: <strong className="text-white">{c.impressions.toLocaleString()}</strong>
                      </span>
                      <span>
                        Cliques: <strong className="text-white">{c.clicks.toLocaleString()}</strong>
                      </span>
                      <span>
                        Ad Spend:{' '}
                        <strong className="text-rose-300">${c.ad_spend_usd.toFixed(2)}</strong>
                      </span>
                      <span>Público: {c.target_audience}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* =================================================================
            TAB 3: FÁBRICA DE SOFTWARE NÍVEL 2 (SELF-HEALING + GIT + CLOUD)
        ================================================================== */}
        {activeTab === 'FACTORY' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 space-y-5">
              <form
                onSubmit={triggerSoftwareBuild}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Code2 className="w-5 h-5 text-emerald-400" />
                    <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                      Fábrica Nível 2 • Self-Healing + Git + Deploy
                    </h2>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
                    Max 5 Iterações QA
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Nome do Projeto</label>
                    <input
                      value={projName}
                      onChange={(e) => setProjName(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Tipo de Arquitetura</label>
                    <select
                      value={projType}
                      onChange={(e) => setProjType(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white"
                    >
                      <option value="GAME_HTML5">Jogo Completo HTML5 / Canvas</option>
                      <option value="SAAS_LANDING">Site SaaS Alta Conversão + Calculadora</option>
                      <option value="WEB_APP">Sistema Web Operacional B2B</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Cliente / Destino</label>
                    <input
                      value={projClient}
                      onChange={(e) => setProjClient(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">
                      Contrato Faturado ($ USD)
                    </label>
                    <input
                      type="number"
                      value={projValue}
                      onChange={(e) => setProjValue(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-emerald-400 font-bold"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-slate-400 mb-1">
                    Especificação Funcional & Regras
                  </label>
                  <textarea
                    rows={2}
                    value={projSpec}
                    onChange={(e) => setProjSpec(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white"
                    required
                  />
                </div>

                <label className="flex items-center gap-2.5 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/25 text-xs text-amber-200 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={simulateHealing}
                    onChange={(e) => setSimulateHealing(e.target.checked)}
                    className="accent-emerald-500"
                  />
                  <Wrench className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>
                    Testar ciclo <strong>Self-Healing</strong> (injeta falha na Iteração #1 para o
                    Agente Dev diagnosticar e auto-corrigir na Iteração #2)
                  </span>
                </label>

                <button
                  type="submit"
                  disabled={busy || killSwitchOn}
                  className="w-full py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 transition cursor-pointer"
                >
                  <Factory className="w-4 h-4" />
                  {busy
                    ? 'Executando Sandbox + Self-Healing + Git...'
                    : 'Programar, Auto-Corrigir em Sandbox & Versionar Git'}
                </button>
              </form>

              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Repositórios Git & Deploys ({data?.projects.length ?? 0})
                </h3>
                <div className="space-y-3 max-h-[360px] overflow-y-auto">
                  {data?.projects.map((p) => (
                    <div
                      key={p.id}
                      className={`p-3.5 rounded-xl border transition ${
                        activePreviewProject?.id === p.id
                          ? 'bg-slate-950 border-emerald-500/50'
                          : 'bg-slate-950/60 border-slate-800'
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-white">{p.name}</span>
                          {p.git_commit_hash && (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-violet-300 flex items-center gap-1">
                              <GitBranch className="w-3 h-3" />
                              {p.git_commit_hash}
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400">
                          {p.healing_iterations > 1
                            ? `SELF-HEALED (${p.healing_iterations}x)`
                            : '1x CLEAN PASS'}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-400 mt-1.5 flex items-center justify-between">
                        <span>{p.client_name}</span>
                        <span className="text-emerald-400 font-semibold">
                          +${p.contract_value_usd.toLocaleString()} (Custo: $
                          {p.build_cost_usd.toFixed(4)})
                        </span>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          onClick={() => setActivePreviewProject(p)}
                          className="text-xs px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 font-semibold cursor-pointer"
                        >
                          Jogar / Testar Live
                        </button>
                        <button
                          onClick={() => openProjectSource(p.id)}
                          className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center gap-1 cursor-pointer"
                        >
                          <FileCode className="w-3.5 h-3.5" />
                          Código & Self-Healing Log
                        </button>
                        <a
                          href={p.download_zip_url}
                          download
                          className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 flex items-center gap-1"
                        >
                          <Download className="w-3.5 h-3.5" />
                          .ZIP
                        </a>
                        <button
                          onClick={() => deployProjectCloud(p.id)}
                          className="text-xs px-2.5 py-1 rounded-lg bg-violet-500/20 hover:bg-violet-500/30 text-violet-300 flex items-center gap-1 cursor-pointer"
                        >
                          <CloudUpload className="w-3.5 h-3.5" />
                          Deploy Cloud
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden flex flex-col min-h-[640px]">
              <div className="px-4 py-3 bg-slate-950 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-white">
                    LIVE DEPLOY VIEWPORT:{' '}
                    {activePreviewProject ? activePreviewProject.name : 'Seleciona um projeto'}
                  </span>
                  {activePreviewProject?.git_commit_hash && (
                    <span className="text-[11px] font-mono text-violet-400">
                      commit #{activePreviewProject.git_commit_hash}
                    </span>
                  )}
                </div>
                {activePreviewProject?.preview_url && (
                  <a
                    href={activePreviewProject.preview_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-cyan-400 hover:underline flex items-center gap-1"
                  >
                    Abrir Ecrã Completo <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>

              {activePreviewProject?.preview_url ? (
                <iframe
                  key={activePreviewProject.preview_url}
                  src={activePreviewProject.preview_url}
                  title={activePreviewProject.name}
                  className="w-full flex-1 bg-slate-950 border-0 min-h-[580px]"
                />
              ) : (
                <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                  Nenhum artefacto selecionado.
                </div>
              )}
            </div>
          </div>
        )}

        {/* =================================================================
            TAB 4: STRIPE CHECKOUT + ASAAS PIX QR + RAZÃO CONTABILÍSTICO
        ================================================================== */}
        {activeTab === 'LEDGER' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <form
                onSubmit={createInvoice}
                className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 h-fit"
              >
                <div className="flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-emerald-400" />
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                    Emitir Cobrança Real (Stripe / Asaas Pix)
                  </h2>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setInvProvider('ASAAS_PIX')}
                    className={`py-2 rounded-xl text-xs font-bold border cursor-pointer ${
                      invProvider === 'ASAAS_PIX'
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300'
                        : 'bg-slate-950 border-slate-800 text-slate-400'
                    }`}
                  >
                    Asaas Pix Instantâneo (QR)
                  </button>
                  <button
                    type="button"
                    onClick={() => setInvProvider('STRIPE')}
                    className={`py-2 rounded-xl text-xs font-bold border cursor-pointer ${
                      invProvider === 'STRIPE'
                        ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300'
                        : 'bg-slate-950 border-slate-800 text-slate-400'
                    }`}
                  >
                    Stripe Checkout Global
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <input
                    value={invClient}
                    onChange={(e) => setInvClient(e.target.value)}
                    placeholder="Empresa / Cliente"
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white"
                    required
                  />
                  <input
                    value={invEmail}
                    onChange={(e) => setInvEmail(e.target.value)}
                    placeholder="financeiro@cliente.com"
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <input
                    value={invDesc}
                    onChange={(e) => setInvDesc(e.target.value)}
                    placeholder="Descrição do contrato"
                    className="sm:col-span-2 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white"
                    required
                  />
                  <input
                    type="number"
                    value={invAmount}
                    onChange={(e) => setInvAmount(e.target.value)}
                    placeholder="Valor USD"
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-emerald-400 font-bold"
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={busy}
                  className="w-full py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm cursor-pointer"
                >
                  Gerar Link de Pagamento / Pix QR Code
                </button>
              </form>

              <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Faturas Emitidas & Conciliação Automática via Webhook (
                  {data?.invoices.length ?? 0})
                </h3>
                <div className="space-y-3 max-h-[340px] overflow-y-auto">
                  {data?.invoices.map((inv) => (
                    <div
                      key={inv.id}
                      className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center"
                    >
                      <div className="flex items-center gap-3.5">
                        {inv.pix_qr_svg && (
                          <div
                            className="w-20 h-20 shrink-0 rounded-lg overflow-hidden bg-slate-950"
                            dangerouslySetInnerHTML={{
                              __html: inv.pix_qr_svg
                                .replace('width="192"', 'width="80"')
                                .replace('height="192"', 'height="80"'),
                            }}
                          />
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-white">{inv.client_name}</span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-300">
                              {inv.provider}
                            </span>
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                                inv.status === 'PAID'
                                  ? 'bg-emerald-500/20 text-emerald-400'
                                  : 'bg-amber-500/20 text-amber-300'
                              }`}
                            >
                              {inv.status}
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5">{inv.description}</p>
                          <div className="text-sm font-bold text-emerald-400 mt-1">
                            ${inv.amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}{' '}
                            USD
                          </div>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-2 shrink-0">
                        {inv.pix_copy_paste && (
                          <>
                            <button
                              onClick={() => copyText(inv.id, inv.pix_copy_paste!)}
                              className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 flex items-center gap-1 cursor-pointer"
                            >
                              <Copy className="w-3.5 h-3.5" />
                              {copiedId === inv.id ? 'Pix Copiado!' : 'Pix Copia-e-Cola'}
                            </button>
                            <a
                              href={`https://wa.me/?text=${encodeURIComponent(
                                `Olá ${inv.client_name}! Segue o código Pix Copia e Cola referente a ${inv.description} (R$ ${(inv.amount_usd * 5.65).toFixed(2)}):\n\n${inv.pix_copy_paste}`
                              )}`}
                              target="_blank"
                              rel="noreferrer"
                              className="px-2.5 py-1.5 rounded-lg bg-emerald-600/25 border border-emerald-500/40 hover:bg-emerald-600/40 text-xs text-emerald-300 font-semibold flex items-center gap-1"
                            >
                              <MessageSquare className="w-3.5 h-3.5" />
                              Cobrar no WhatsApp
                            </a>
                          </>
                        )}
                        {inv.status === 'PENDING' && (
                          <button
                            onClick={() => settleInvoiceWebhook(inv.id)}
                            disabled={busy}
                            className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs cursor-pointer"
                          >
                            Confirmar Webhook Pago
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                    Razão Contabilístico Imutável (PostgreSQL Ledger)
                  </h2>
                  <p className="text-xs text-slate-400">
                    Auditoria completa de receitas vs custos de APIs, Ads e Sandboxes
                  </p>
                </div>
                <div className="flex gap-2">
                  {(['ALL', 'REVENUE', 'EXPENSE'] as const).map((f) => (
                    <button
                      key={f}
                      onClick={() => setLedgerFilter(f)}
                      className={`px-3 py-1 rounded-lg text-xs font-semibold cursor-pointer ${
                        ledgerFilter === f
                          ? 'bg-emerald-500 text-slate-950'
                          : 'bg-slate-800 text-slate-300'
                      }`}
                    >
                      {f === 'ALL' ? 'Todos' : f === 'REVENUE' ? 'Entradas (+)' : 'Saídas / APIs (-)'}
                    </button>
                  ))}
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 uppercase">
                    <tr>
                      <th className="px-4 py-3">Horário</th>
                      <th className="px-4 py-3">Tipo</th>
                      <th className="px-4 py-3">Categoria</th>
                      <th className="px-4 py-3">Agente</th>
                      <th className="px-4 py-3">Descrição Auditável</th>
                      <th className="px-4 py-3 text-right">Valor (USD)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80">
                    {filteredLedger.map((row) => (
                      <tr key={row.id} className="hover:bg-slate-800/40">
                        <td className="px-4 py-3 font-mono text-slate-400">
                          {row.created_at.slice(0, 19).replace('T', ' ')}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                              row.entry_type === 'REVENUE'
                                ? 'bg-emerald-500/15 text-emerald-400'
                                : 'bg-rose-500/15 text-rose-400'
                            }`}
                          >
                            {row.entry_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-300">{row.category}</td>
                        <td className="px-4 py-3 text-slate-400">{row.agent_id ?? 'system'}</td>
                        <td className="px-4 py-3 text-slate-200">{row.description}</td>
                        <td
                          className={`px-4 py-3 text-right font-mono font-bold ${
                            row.entry_type === 'REVENUE' ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          {row.entry_type === 'REVENUE'
                            ? `+$${row.amount_usd.toFixed(2)}`
                            : `-$${row.amount_usd.toFixed(5)}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================
            TAB 5: PAREAMENTO QR WHATSAPP EVOLUTION API v2 + SUPORTE 24H
        ================================================================== */}
        {activeTab === 'OMNICHANNEL' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 space-y-5">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <QrCode className="w-5 h-5 text-emerald-400" />
                    <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                      Pareamento WhatsApp • Evolution API v2
                    </h2>
                  </div>
                  <span
                    className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                      waState?.status === 'CONNECTED'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : waState?.status === 'QR_READY'
                        ? 'bg-amber-500/20 text-amber-300'
                        : 'bg-rose-500/20 text-rose-400'
                    }`}
                  >
                    {waState?.status ?? 'QR_READY'}
                  </span>
                </div>

                <div className="flex flex-col sm:flex-row items-center gap-4 bg-slate-950 border border-slate-800 rounded-xl p-4">
                  {waState?.status !== 'CONNECTED' && waState?.qr_base64 ? (
                    <img
                      src={waState.qr_base64}
                      alt="Evolution WhatsApp QR"
                      className="w-36 h-36 rounded-xl"
                    />
                  ) : waState?.status !== 'CONNECTED' && waState?.qr_svg ? (
                    <div
                      className="shrink-0"
                      dangerouslySetInnerHTML={{
                        __html: waState.qr_svg
                          .replace('width="192"', 'width="144"')
                          .replace('height="192"', 'height="144"'),
                      }}
                    />
                  ) : (
                    <div className="w-28 h-28 rounded-2xl bg-emerald-500/15 border border-emerald-500/40 flex flex-col items-center justify-center text-emerald-400">
                      <CheckCircle2 className="w-10 h-10 mb-1" />
                      <span className="text-[10px] font-bold">ONLINE 24H</span>
                    </div>
                  )}

                  <div className="space-y-2 flex-1 text-xs">
                    <div>
                      <span className="text-slate-400">Instância:</span>{' '}
                      <strong className="font-mono text-white">
                        {waState?.instance_name ?? 'empire-hq'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-400">Pairing Code:</span>{' '}
                      <strong className="font-mono text-emerald-400">
                        {waState?.pairing_code}
                      </strong>
                    </div>
                    {waState?.paired_number && (
                      <div>
                        <span className="text-slate-400">Número Conectado:</span>{' '}
                        <strong className="text-cyan-300">{waState.paired_number}</strong>
                      </div>
                    )}

                    {waState?.status !== 'CONNECTED' ? (
                      <div className="space-y-2 pt-1">
                        <input
                          value={pairPhone}
                          onChange={(e) => setPairPhone(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={confirmWhatsAppPair}
                            className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs cursor-pointer"
                          >
                            Confirmar Pareamento
                          </button>
                          <button
                            onClick={refreshWhatsAppQR}
                            className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs cursor-pointer"
                          >
                            Novo QR
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={disconnectWhatsApp}
                        className="px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 font-semibold text-xs cursor-pointer"
                      >
                        Desconectar Sessão
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <form
                onSubmit={simulateEvolutionWebhook}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3"
              >
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                    Simular Mensagem Recebida (Webhook messages.upsert)
                  </h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <input
                    value={waName}
                    onChange={(e) => setWaName(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                  />
                  <input
                    value={waPhone}
                    onChange={(e) => setWaPhone(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                  />
                </div>
                <textarea
                  rows={2}
                  value={waMessage}
                  onChange={(e) => setWaMessage(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white"
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs cursor-pointer"
                >
                  Injetar Mensagem no Agente de Suporte 24h (c/ RAG)
                </button>
              </form>
            </div>

            <div className="lg:col-span-7 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Histórico Omnicanal — Suporte 24h & Funil de Vendas ({data?.interactions.length ?? 0}
                )
              </h3>
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {data?.interactions.map((it) => (
                  <div
                    key={it.id}
                    className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-bold text-sm text-white">{it.contact_name}</span>
                        <span className="ml-2 text-xs text-slate-400">({it.contact_handle})</span>
                      </div>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                          it.deal_stage === 'CLOSED_WON'
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : 'bg-sky-500/20 text-sky-300'
                        }`}
                      >
                        {it.deal_stage}
                        {it.deal_value_usd > 0 ? ` • +$${it.deal_value_usd.toLocaleString()}` : ''}
                      </span>
                    </div>
                    <div className="bg-slate-950/70 rounded-xl p-2.5 text-xs text-slate-300">
                      <strong className="text-slate-400">Entrada:</strong> {it.inbound_message}
                    </div>
                    <div className="bg-emerald-950/20 border border-emerald-500/20 rounded-xl p-2.5 text-xs text-emerald-200">
                      <strong className="text-emerald-400">Agente Autónomo:</strong>{' '}
                      {it.agent_response}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* =================================================================
            TAB 6: META-AGENTE (CRIADOR DE AGENTES)
        ================================================================== */}
        {activeTab === 'META' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 h-fit">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-violet-400" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                  Meta-Agente — Arquiteto de Novos Agentes
                </h2>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Descreve um gargalo operacional ou nova vertical. O Meta-Agente desenha o prompt,
                ferramentas, teto de orçamento e módulo Python, aguardando a tua autorização antes
                do Hot-Spawn no LangGraph.
              </p>

              <textarea
                rows={4}
                value={metaPrompt}
                onChange={(e) => setMetaPrompt(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-white"
              />

              <button
                onClick={() => sendDirectCommand(metaPrompt, 'META_CREATOR')}
                disabled={busy || killSwitchOn || !metaPrompt.trim()}
                className="w-full py-2.5 rounded-xl bg-violet-500 hover:bg-violet-400 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 transition cursor-pointer"
              >
                <PlusCircle className="w-4 h-4" />
                {busy ? 'Sintetizando Blueprint...' : 'Gerar Proposta de Novo Sub-Agente'}
              </button>
            </div>

            <div className="lg:col-span-7 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Fila de Governança & Blueprints Gerados ({data?.approvals.length ?? 0})
              </h3>
              {data?.approvals.map((ap) => (
                <div
                  key={ap.id}
                  className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="text-sm font-bold text-white">{ap.title}</span>
                      <span className="ml-2 text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-violet-300">
                        {ap.payload_json.department}
                      </span>
                    </div>
                    <span
                      className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                        ap.status === 'APPROVED'
                          ? 'bg-emerald-500/15 text-emerald-400'
                          : ap.status === 'REJECTED'
                          ? 'bg-rose-500/15 text-rose-400'
                          : 'bg-amber-500/20 text-amber-300'
                      }`}
                    >
                      {ap.status}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300">{ap.rationale}</p>

                  {ap.payload_json.generated_code && (
                    <pre className="bg-slate-950 border border-slate-800 rounded-xl p-3 text-[11px] font-mono text-cyan-300 overflow-x-auto max-h-44">
                      {ap.payload_json.generated_code}
                    </pre>
                  )}

                  {ap.status === 'PENDING' && (
                    <div className="flex items-center gap-3 pt-2">
                      <button
                        onClick={() => decideApproval(ap.id, true)}
                        className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 cursor-pointer"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        Autorizar & Instanciar no Grafo Mestre
                      </button>
                      <button
                        onClick={() => decideApproval(ap.id, false)}
                        className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-rose-950 text-slate-300 text-xs cursor-pointer"
                      >
                        Vetar Criação
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* =================================================================
            TAB 7: SEGURANÇA 2FA JWT, VAULT MULTI-LLM & MEMÓRIA PGVECTOR
        ================================================================== */}
        {activeTab === 'MEMORY_LLM' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 space-y-5">
              {/* Segurança Soberana CEO (JWT + 2FA TOTP) */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5 text-violet-400" />
                    <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                      Segurança Soberana • JWT + TOTP 2FA
                    </h2>
                  </div>
                  <button
                    onClick={() => setIsLocked(true)}
                    className="px-3 py-1 rounded-lg bg-violet-500 hover:bg-violet-400 text-slate-950 font-bold text-xs cursor-pointer"
                  >
                    Testar Ecrã Lock 2FA
                  </button>
                </div>

                {data?.security && (
                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 flex items-center gap-4">
                    <div
                      className="shrink-0"
                      dangerouslySetInnerHTML={{
                        __html: data.security.totp_qr_svg
                          .replace('width="192"', 'width="96"')
                          .replace('height="192"', 'height="96"'),
                      }}
                    />
                    <div className="text-xs space-y-1">
                      <div className="text-slate-400">Segredo Base32 (Google Authenticator):</div>
                      <div className="font-mono text-violet-300 font-bold">
                        {data.security.totp_secret_b32}
                      </div>
                      <div className="text-slate-400 pt-1">
                        Código TOTP Ativo ({data.security.totp_seconds_remaining}s):{' '}
                        <strong className="font-mono text-emerald-400 text-sm">
                          {data.security.current_totp_demo}
                        </strong>
                      </div>
                    </div>
                  </div>
                )}

                <div className="space-y-1 max-h-28 overflow-y-auto pt-1">
                  {data?.security_logs.slice(0, 4).map((sl) => (
                    <div key={sl.id} className="text-[11px] font-mono text-slate-400">
                      <span className="text-violet-400">[{sl.action}]</span> {sl.details}
                    </div>
                  ))}
                </div>
              </div>

              {/* Cofre Runtime Multi-LLM */}
              <form
                onSubmit={saveVaultSecret}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3.5"
              >
                <div className="flex items-center gap-2">
                  <KeyRound className="w-5 h-5 text-cyan-400" />
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                    Cofre Runtime • Conector Multi-LLM & Gateways
                  </h2>
                </div>

                <select
                  value={selectedVaultKey}
                  onChange={(e) => setSelectedVaultKey(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white"
                >
                  {data?.vault_status.map((vk) => (
                    <option key={vk.key_name} value={vk.key_name}>
                      {vk.key_name} ({vk.configured ? 'ATIVO' : 'FALLBACK LOCAL'})
                    </option>
                  ))}
                </select>

                <input
                  type="password"
                  value={vaultSecretInput}
                  onChange={(e) => setVaultSecretInput(e.target.value)}
                  placeholder="Cola aqui a tua API Key / Token..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                />

                <button
                  type="submit"
                  disabled={busy}
                  className="w-full py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs cursor-pointer"
                >
                  Guardar Credencial em Quente no Cofre
                </button>
              </form>
            </div>

            {/* Pesquisa Semântica Cosine RAG + Nova Memória */}
            <div className="lg:col-span-7 space-y-5">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
                <div className="flex items-center gap-2">
                  <BrainCircuit className="w-5 h-5 text-violet-400" />
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                    Explorador de Memória Semântica Partilhada (pgvector RAG)
                  </h2>
                </div>

                <form onSubmit={runSemanticSearch} className="flex gap-2">
                  <input
                    value={memQuery}
                    onChange={(e) => setMemQuery(e.target.value)}
                    placeholder="Pesquisar por significado semântico (ex: 'margem lucro deepseek', 'campanha linkedin', 'self-healing')..."
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-xl bg-violet-500 hover:bg-violet-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <Search className="w-3.5 h-3.5" />
                    Busca Vetorial
                  </button>
                  {memSearchResults && (
                    <button
                      type="button"
                      onClick={() => {
                        setMemQuery('');
                        setMemSearchResults(null);
                      }}
                      className="px-3 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs cursor-pointer"
                    >
                      Limpar
                    </button>
                  )}
                </form>

                <div className="space-y-2.5 max-h-[340px] overflow-y-auto">
                  {(memSearchResults ?? data?.memories ?? []).map((m) => (
                    <div
                      key={m.id}
                      className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-violet-500/20 text-violet-300">
                            {m.namespace}
                          </span>
                          <span className="font-bold text-xs text-white">{m.title}</span>
                        </div>
                        {typeof m.similarity === 'number' && (
                          <span className="text-[11px] font-mono text-emerald-400 font-bold">
                            Similaridade: {(m.similarity * 100).toFixed(1)}%
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">{m.content}</p>
                    </div>
                  ))}
                </div>
              </div>

              <form
                onSubmit={saveNewMemory}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3"
              >
                <h3 className="text-xs font-bold uppercase tracking-wider text-violet-300">
                  + Gravar Nova Regra Soberana na Memória Vetorial (pgvector)
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  <select
                    value={newMemNamespace}
                    onChange={(e) => setNewMemNamespace(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                  >
                    <option value="CEO_DIRECTIVES">Diretrizes do CEO</option>
                    <option value="SALES_PLAYBOOK">Playbook Comercial</option>
                    <option value="FACTORY_PATTERNS">Padrões Fábrica</option>
                  </select>
                  <input
                    value={newMemTitle}
                    onChange={(e) => setNewMemTitle(e.target.value)}
                    placeholder="Título da memória..."
                    className="sm:col-span-2 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                    required
                  />
                </div>
                <textarea
                  rows={2}
                  value={newMemContent}
                  onChange={(e) => setNewMemContent(e.target.value)}
                  placeholder="Conteúdo estratégico que todos os agentes irão consultar via RAG..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white"
                  required
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full py-2 rounded-xl bg-violet-500 hover:bg-violet-400 text-slate-950 font-bold text-xs cursor-pointer"
                >
                  Vetorizar & Indexar no pgvector
                </button>
              </form>
            </div>
          </div>
        )}
      </main>

      {/* MODAL DE INSPEÇÃO DE CÓDIGO FONTE, GIT & SELF-HEALING LOG */}
      {inspectedSource && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-4xl w-full max-h-[88vh] flex flex-col overflow-hidden">
            <div className="px-5 py-3.5 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-white">
                  Auditoria Nível 2 — {inspectedSource.name}{' '}
                  {inspectedSource.git_commit_hash && (
                    <span className="ml-2 text-xs font-mono text-violet-400">
                      [Git #{inspectedSource.git_commit_hash}]
                    </span>
                  )}
                </h3>
                <p className="text-xs text-emerald-400">
                  Concluído em {inspectedSource.healing_iterations} iteração(ões) de Sandbox QA
                </p>
              </div>
              <button
                onClick={() => setInspectedSource(null)}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-4 flex-1">
              {inspectedSource.healing_log.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[11px] font-bold uppercase text-amber-300">
                    Histórico de Iterações Self-Healing na Sandbox
                  </div>
                  {inspectedSource.healing_log.map((step) => (
                    <div
                      key={step.iteration}
                      className={`p-2.5 rounded-xl border text-xs font-mono ${
                        step.status === 'PASSED'
                          ? 'bg-emerald-950/25 border-emerald-500/30 text-emerald-300'
                          : 'bg-amber-950/25 border-amber-500/30 text-amber-200'
                      }`}
                    >
                      <strong>Iteração #{step.iteration}</strong> ({step.duration_ms}ms • exit=
                      {step.exit_code}): {step.summary}
                    </div>
                  ))}
                </div>
              )}

              <div className="bg-slate-950 border border-emerald-500/30 rounded-xl p-3">
                <div className="text-[11px] font-bold uppercase text-emerald-400 mb-1">
                  Output Final da Bateria QA (unittest + AST + node --check + DOM)
                </div>
                <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap">
                  {inspectedSource.test_report}
                </pre>
              </div>

              <div className="flex flex-wrap gap-2">
                {Object.keys(inspectedSource.sources).map((fname) => (
                  <button
                    key={fname}
                    onClick={() => setSelectedSourceFile(fname)}
                    className={`px-3 py-1 rounded-lg text-xs font-mono cursor-pointer ${
                      selectedSourceFile === fname
                        ? 'bg-cyan-500 text-slate-950 font-bold'
                        : 'bg-slate-800 text-slate-300'
                    }`}
                  >
                    {fname}
                  </button>
                ))}
              </div>

              <pre className="bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs font-mono text-cyan-200 overflow-x-auto max-h-[340px]">
                {inspectedSource.sources[selectedSourceFile]}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
