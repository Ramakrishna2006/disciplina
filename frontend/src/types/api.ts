// The shapes of the data the backend sends (see docs/API.md). Keep in sync with User.to_dict().

export interface User {
  id: number
  email: string
  name: string
  role: "member" | "admin"
  theme: "system" | "light" | "dark"
  default_model: "base" | "full" | "lora"
  default_temperature: number
  created_at: string
  last_login_at: string | null
}

export interface Health {
  status: "ok" | "degraded"
  database: "ok" | "unreachable"
  app: string
  version: string
  environment: string
  training_enabled: boolean
  models: "loaded" | "available" | "missing"
}

/** The body of every error response: {"error": {...}} */
export interface ApiErrorBody {
  code: string
  message: string
  fields: Record<string, string>
  request_id?: string
}

// ----------------------------------------------------------------------------- stage 5
export type ModelId = "base" | "full" | "lora"

/** `meta` of a paged list: {"data": [...], "meta": {...}} */
export interface PageMeta {
  page: number
  per_page: number
  total: number
  pages: number
}

export interface Paged<T> {
  items: T[]
  meta: PageMeta
}

export interface AppConfig {
  app: string
  version: string
  training_enabled: boolean
  presets: { name: string; pretrain_steps: number; finetune_steps: number; minutes: string | null }[]
  limits: Record<string, { min?: number; max: number }>
  models: { id: ModelId; label: string; description: string }[]
}

export interface ChatMessage {
  id: number
  role: "user" | "assistant"
  content: string
  model: ModelId
  temperature: number
  top_k: number | null
  latency_ms: number | null
  created_at: string
}

export interface ChatSession {
  id: number
  title: string
  model: ModelId
  created_at: string
  updated_at: string
  message_count?: number
  last_message?: string | null
}

export interface ChatReply {
  session_id: number
  reply: string
  latency_ms: number
  tokens: number
  messages: ChatMessage[]
}

export interface Token {
  id: number
  text: string
}

export interface Tokenized {
  tokens: Token[]
  count: number
  characters: number
  chars_per_token: number
}

export type Category = "city" | "job" | "food"

export interface EmbeddingPoint {
  word: string
  category: Category
  x: number
  y: number
}

export interface Neighbor {
  word: string
  similarity: number
}

export interface Person {
  id: number
  name: string
  city: string
  job: string
  food: string
  split: "fine-tuning" | "held-out"
}

export interface Facets {
  city: { value: string; count: number }[]
  job: { value: string; count: number }[]
  food: { value: string; count: number }[]
  split: { value: string; count: number }[]
  total: number
}

export type ExperimentStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted"

export interface ExperimentResult {
  model: ModelId
  qa_seen: number
  qa_heldout: number
  completion: number
  perplexity: number
  trainable_params: number
}

export interface Experiment {
  id: number
  name: string
  description: string
  status: ExperimentStatus
  is_public: boolean
  owner_id: number
  owner_name: string | null
  pretrain_steps: number
  finetune_steps: number
  lora_rank: number
  replay: boolean
  seed: number
  phase: string | null
  progress: number
  error: string | null
  cancel_requested: boolean
  created_at: string
  started_at: string | null
  finished_at: string | null
  is_owner: boolean
  results?: ExperimentResult[]
}

export interface ExperimentSettings {
  name: string
  description: string
  pretrain_steps: number
  finetune_steps: number
  lora_rank: number
  replay: boolean
  seed: number
}

export type MetricPhase = "pretrain" | "full" | "lora"

export interface Metric {
  id: number
  phase: MetricPhase
  step: number
  train_loss: number
  val_loss: number | null
}

export interface MetricsPage {
  items: Metric[]
  meta: { last_id: number; status: ExperimentStatus; progress: number; phase: string | null; complete: boolean }
}

export interface ActivityEvent {
  id: number
  type: string
  message: string
  experiment_id: number | null
  created_at: string
  read_at: string | null
}

export interface Dashboard {
  kpis: {
    experiments: number
    completed: number
    active: number
    chats: number
    questions: number
    best_heldout: number | null
  }
  latest: { experiment: Experiment; metrics: Metric[] } | null
  active_experiment: Experiment | null
  activity: ActivityEvent[]
  unread: number
}
