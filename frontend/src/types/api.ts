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
}

/** The body of every error response: {"error": {...}} */
export interface ApiErrorBody {
  code: string
  message: string
  fields: Record<string, string>
  request_id?: string
}
