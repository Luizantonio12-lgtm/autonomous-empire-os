export interface BalanceSheet {
  total_revenue_usd: number;
  total_expenses_usd: number;
  llm_api_cost_usd: number;
  sandbox_compute_cost_usd: number;
  net_profit_usd: number;
  profit_margin_pct: number;
}

export interface AgentItem {
  id: string;
  slug: string;
  name: string;
  department: string;
  role_description: string;
  model_name: string;
  tools_manifest: string[];
  status: string;
  is_dynamic: boolean;
  created_by: string;
  tasks_completed: number;
  success_rate: number;
  total_cost_usd: number;
  max_budget_per_task_usd: number;
}

export interface LedgerEntry {
  id: string;
  entry_type: 'REVENUE' | 'EXPENSE';
  category: string;
  agent_id: string | null;
  amount_usd: number;
  description: string;
  created_at: string;
}

export interface TaskItem {
  id: string;
  trace_id: string;
  title: string;
  directive: string;
  assigned_agent_id: string | null;
  department: string;
  priority: string;
  status: string;
  result_summary: string | null;
  execution_cost_usd: number;
  revenue_generated_usd: number;
  started_at: string;
}

export interface ApprovalItem {
  id: string;
  request_type: string;
  requested_by_agent: string;
  title: string;
  rationale: string;
  payload_json: {
    slug?: string;
    name?: string;
    department?: string;
    role_description?: string;
    tools_manifest?: string[];
    generated_code?: string;
    max_budget_per_task_usd?: number;
  };
  estimated_cost_usd: number;
  projected_roi_usd: number;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  created_at: string;
}

export interface HealingLogStep {
  iteration: number;
  status: string;
  exit_code: number;
  duration_ms: number;
  summary: string;
}

export interface SoftwareProjectItem {
  id: string;
  name: string;
  project_type: string;
  client_name: string;
  specification: string;
  status: string;
  sandbox_exit_code: number | null;
  healing_iterations: number;
  healing_log: HealingLogStep[];
  git_commit_hash: string | null;
  test_report: string | null;
  files_manifest: string[];
  preview_url: string | null;
  external_deploy_url: string | null;
  download_zip_url: string;
  contract_value_usd: number;
  build_cost_usd: number;
  created_at: string;
}

export interface OmnichannelItem {
  id: string;
  channel: string;
  department: string;
  contact_name: string;
  contact_handle: string;
  inbound_message: string;
  agent_response: string;
  deal_stage: string;
  deal_value_usd: number;
  created_at: string;
}

export interface PaymentInvoiceItem {
  id: string;
  provider: 'STRIPE' | 'ASAAS_PIX';
  external_id: string;
  client_name: string;
  client_email: string;
  description: string;
  amount_usd: number;
  status: 'PENDING' | 'PAID' | 'CANCELED';
  checkout_url: string | null;
  pix_copy_paste: string | null;
  pix_qr_svg: string | null;
  created_at: string;
}

export interface SemanticMemoryItem {
  id: string;
  namespace: string;
  source_agent: string;
  title: string;
  content: string;
  similarity?: number;
  created_at: string;
}

export interface ScheduledJobItem {
  id: string;
  name: string;
  department: string;
  directive_template: string;
  interval_seconds: number;
  is_enabled: boolean;
  runs_count: number;
  last_run_at: string | null;
  last_result: string | null;
}

export interface GrowthCampaignItem {
  id: string;
  title: string;
  channel: string;
  target_audience: string;
  hook_headline: string;
  content_body: string;
  cta_url: string;
  impressions: number;
  clicks: number;
  leads_captured: number;
  ad_spend_usd: number;
  attributed_revenue_usd: number;
  status: string;
  created_at: string;
}

export interface SecurityOverview {
  kill_switch_active: boolean;
  require_2fa: boolean;
  totp_secret_b32: string;
  otpauth_uri: string;
  totp_qr_svg: string;
  current_totp_demo: string;
  totp_seconds_remaining: number;
  default_password_hint: string;
}

export interface SecurityLogItem {
  id: string;
  action: string;
  actor: string;
  details: string;
  created_at: string;
}

export interface BusinessVentureItem {
  id: string;
  codename: string;
  name: string;
  niche: string;
  tagline: string;
  monthly_price_usd: number;
  active_customers: number;
  mrr_usd: number;
  total_revenue_usd: number;
  software_project_id: string | null;
  dedicated_agent_id: string | null;
  public_url: string | null;
  status: string;
  created_at: string;
}

export interface WhatsAppInstanceState {
  instance_name: string;
  status: 'DISCONNECTED' | 'QR_READY' | 'CONNECTED';
  paired_number: string | null;
  pairing_code: string;
  qr_base64: string | null;
  qr_svg: string | null;
  mode: string;
}

export interface VaultKeyStatus {
  key_name: string;
  configured: boolean;
  masked_value: string | null;
  source: string;
}

export interface TelemetryEvent {
  id: string;
  timestamp: string;
  event_type: string;
  agent: string;
  level: string;
  message: string;
  payload?: Record<string, unknown>;
}

export interface DashboardOverview {
  balance: BalanceSheet;
  holding_mrr_usd: number;
  ventures: BusinessVentureItem[];
  agents: AgentItem[];
  ledger: LedgerEntry[];
  tasks: TaskItem[];
  approvals: ApprovalItem[];
  projects: SoftwareProjectItem[];
  interactions: OmnichannelItem[];
  invoices: PaymentInvoiceItem[];
  memories: SemanticMemoryItem[];
  scheduler: {
    autopilot_enabled: boolean;
    total_cycles_executed: number;
    kill_switch_blocked: boolean;
  };
  scheduled_jobs: ScheduledJobItem[];
  growth_campaigns: GrowthCampaignItem[];
  security: SecurityOverview;
  security_logs: SecurityLogItem[];
  whatsapp_instance: WhatsAppInstanceState;
  vault_status: VaultKeyStatus[];
  telemetry: TelemetryEvent[];
}
