const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`${res.status} ${detail}`)
  }
  return (await res.json()) as T
}

export const get = <T,>(path: string) => request<T>(path)
export const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })
export const put = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
export const del = <T,>(path: string) => request<T>(path, { method: 'DELETE' })

// ---------------------------------------------------------------- types
export type Stance = 'long' | 'watch' | 'avoid'

export interface Health {
  status: string
  orchestrator: string
  provider: { name: string; ok: boolean; detail: string }
  agents: string[]
  demo_mode: boolean
}

export interface Signal {
  as_of: string
  run_id: string
  code: string
  name: string
  stance: Stance
  conviction: number
  sources: string[]
  rationale: string
}

export interface RunSummary {
  run_id: string
  goal: string
  status: string
  orchestrator: string
  started_at: string | null
  error: string | null
}

export interface Strategy {
  strategy_id: number
  name: string
  kind: string
  params: Record<string, unknown>
  enabled: boolean
}

export interface Review {
  review_id: string
  period: string
  samples: number
  hit_rate: number
  avg_return: number
  improvements: string[]
}

export interface Conclusion {
  summary: string
  picks: Array<{
    code: string
    name: string
    stance: Stance
    conviction: number
    sources: string[]
    rationale: string
  }>
  disagreements: Array<{ code: string; agents: string[]; summary: string }>
  risk_notes: string[]
}

export interface RunResult {
  run_id: string
  status: string
  conclusion: Conclusion | null
  snapshot_source: string | null
  traces: Array<{ agent: string; status: string; duration_ms: number }>
}

// ---------------------------------------------------------------- agents
export type OutputFormatType = 'json_schema' | 'markdown_table' | 'text'

export interface AgentTool {
  key: string
  label: string
  description: string
  params: string[]
}

export interface WorkflowStep {
  name: string
  instruction: string
}

export interface AgentOutputFormat {
  type: OutputFormatType
  schema?: Record<string, unknown>
}

export interface AgentConfig {
  agent_id: string
  name: string
  role: string
  profile: string
  task: string
  workflow: WorkflowStep[]
  tools: string[]
  output_format: AgentOutputFormat
  output_spec: string
  enabled: boolean
  builtin: boolean
  updated_at: string | null
}

export interface AgentMeta {
  tools: AgentTool[]
  output_formats: Array<{ type: OutputFormatType; label: string; description: string }>
  default_schema: Record<string, unknown>
}

export interface AgentToolCallRecord {
  tool: string
  args?: Record<string, unknown>
  result?: unknown
  error?: string
}

export interface AgentRunResult {
  agent_id: string
  output: unknown
  raw: string
  format_ok: boolean
  error: string | null
  tokens: number
  mock: boolean
  tool_calls: AgentToolCallRecord[]
  rounds: number
  prompt_preview: string
  report_id?: string
}

export interface AgentReportSummary {
  report_id: string
  agent_id: string
  agent_name: string
  title: string
  format: 'text' | 'json'
  tokens: number
  rounds: number
  mock: boolean
  tool_calls: AgentToolCallRecord[]
  input: Record<string, unknown>
  created_at: string | null
  length: number
}

export interface AgentReport extends AgentReportSummary {
  content: string
}

// ---------------------------------------------------------------- dashboard
export type ModuleStatus = 'ok' | 'degraded' | 'missing'

export interface DashboardModule<T> {
  status: ModuleStatus
  source: string
  as_of?: string
  note?: string
  data: T
}

export interface PanoramaData {
  brief: string
  phase: { key: string; label: string; since: string; days: number }
  sentiment_index: { today: number; yesterday: number; delta: number; trend_5d: string }
  core_conflict: {
    text: string
    evidences: Array<{ label: string; value: string; change: string }>
  }
}

export interface FlowItem {
  board: string
  net_inflow_yi?: number
  net_outflow_yi?: number
  change_pct: number
  leader: string
}

export interface CapitalFlowData {
  net_inflow_top: FlowItem[]
  net_outflow_top: FlowItem[]
  note?: string
}

export interface SentimentPoint {
  date: string
  value: number
}

export interface ExtremeItem {
  type: 'stock' | 'board'
  code: string
  name: string
  reason: string
  side: 'hot' | 'cold'
}

export interface SentimentData {
  series: SentimentPoint[]
  ma20: number
  extremes: ExtremeItem[]
}

export interface OpportunityData {
  axes: string[]
  today: number[]
  ma5: number[]
  picks: Array<{ direction: string; conviction: number; reason: string }>
}

export interface RiskItem {
  level: 'high' | 'medium' | 'low'
  title: string
  evidence: string
  source: string
  time: string
}

export interface Position {
  code: string
  name: string
  cost: number
  price: number
  pnl_pct: number
  weight: number
  hot_board: string
}

export interface PortfolioData {
  summary: { total_pnl: number; total_pnl_pct: number; today_pnl: number; match_score: number }
  positions: Position[]
  advices: Array<{ code: string; action: string; reason: string; trigger: string }>
}

export interface DashboardPayload {
  as_of: string
  generated_at: string
  mock: boolean
  degraded_modules: string[]
  modules: {
    panorama: DashboardModule<PanoramaData>
    capital_flow: DashboardModule<CapitalFlowData>
    sentiment: DashboardModule<SentimentData>
    opportunity: DashboardModule<OpportunityData>
    risks: DashboardModule<{ items: RiskItem[] }>
    portfolio: DashboardModule<PortfolioData>
  }
}

export type AgentConfigPayload = Omit<AgentConfig, 'agent_id' | 'builtin' | 'updated_at'>

export interface AgentVersion {
  version: number
  note: string
  created_at: string | null
  payload: {
    name: string
    role: string
    profile: string
    task: string
    workflow: WorkflowStep[]
    tools: string[]
    output_format: AgentOutputFormat
    output_spec: string
    enabled: boolean
  }
}

export interface AgentVersionDiff {
  before_label: string
  after_label: string
  changes: Array<{ field: string; label: string; before: unknown; after: unknown }>
}

export const api = {
  health: () => get<Health>('/health'),
  signals: () => get<Signal[]>('/signals'),
  runs: () => get<RunSummary[]>('/runs'),
  strategies: () => get<Strategy[]>('/strategies'),
  reviews: () => get<Review[]>('/reviews'),
  createStrategy: (body: Omit<Strategy, 'strategy_id'>) => post<{ strategy_id: number }>('/strategies', body),
  deleteStrategy: (id: number) => del<{ deleted: number }>(`/strategies/${id}`),
  createRun: (body: { goal: string; universe: string[]; capital: number; risk: string }) =>
    post<RunResult>('/runs', body),

  agentMeta: () => get<AgentMeta>('/agents/meta'),
  agents: () => get<AgentConfig[]>('/agents'),
  createAgent: (body: AgentConfigPayload) => post<AgentConfig>('/agents', body),
  updateAgent: (id: string, body: AgentConfigPayload) => put<AgentConfig>(`/agents/${id}`, body),
  deleteAgent: (id: string) => del<{ deleted: string }>(`/agents/${id}`),
  runAgent: (id: string, input: Record<string, unknown>) =>
    post<AgentRunResult>(`/agents/${id}/run`, { input }),

  agentVersions: (id: string) => get<AgentVersion[]>(`/agents/${id}/versions`),
  agentVersionDiff: (id: string, version: number, against?: number) =>
    get<AgentVersionDiff>(
      `/agents/${id}/versions/${version}/diff${against ? `?against=${against}` : ''}`,
    ),
  restoreAgentVersion: (id: string, version: number) =>
    post<AgentConfig & { restored_from: number; new_version: number | null }>(
      `/agents/${id}/versions/${version}/restore`,
      {},
    ),

  reports: (agentId?: string) =>
    get<AgentReportSummary[]>(`/reports${agentId ? `?agent_id=${agentId}` : ''}`),
  report: (id: string) => get<AgentReport>(`/reports/${id}`),
  deleteReport: (id: string) => del<{ deleted: string }>(`/reports/${id}`),

  dashboard: () => get<DashboardPayload>('/dashboard'),
}
