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
  workflow: WorkflowStep[]
  tools: string[]
  output_format: AgentOutputFormat
  enabled: boolean
  builtin: boolean
  updated_at: string | null
}

export interface AgentMeta {
  tools: AgentTool[]
  output_formats: Array<{ type: OutputFormatType; label: string; description: string }>
  default_schema: Record<string, unknown>
}

export interface AgentRunResult {
  agent_id: string
  output: unknown
  raw: string
  format_ok: boolean
  error: string | null
  tokens: number
  mock: boolean
  prompt_preview: string
}

export type AgentConfigPayload = Omit<AgentConfig, 'agent_id' | 'builtin' | 'updated_at'>

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
}
