/**
 * The ONE place the frontend talks to the backend. Every page calls these functions instead of
 * fetch(), so the security rules live here once:
 *
 *  - Cookies: the login tokens are httpOnly cookies. The browser sends them by itself
 *    (credentials: "same-origin"); JavaScript never sees or stores a token.
 *  - CSRF: every POST, PATCH and DELETE copies the readable csrf_access_token cookie into the
 *    X-CSRF-TOKEN header. Other websites cannot read our cookies, so they cannot forge this header.
 *  - Refresh: the access token lasts 30 minutes. When a request fails because it expired, we call
 *    /api/auth/refresh once (with the 7-day refresh token) and repeat the request. The user never
 *    notices.
 *  - Errors: every failure becomes an ApiError with a status, a stable code, a message for people,
 *    and per-field messages for forms. Network failures get status 0.
 */
import type {
  ActivityEvent,
  AppConfig,
  ApiErrorBody,
  ChatMessage,
  ChatReply,
  ChatSession,
  Dashboard,
  EmbeddingPoint,
  Experiment,
  ExperimentSettings,
  Facets,
  Health,
  Metric,
  MetricsPage,
  ModelId,
  Neighbor,
  PageMeta,
  Paged,
  Person,
  Tokenized,
  User,
} from "@/types/api"

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly fields: Record<string, string>
  readonly requestId?: string

  constructor(status: number, body: ApiErrorBody) {
    super(body.message)
    this.name = "ApiError"
    this.status = status
    this.code = body.code
    this.fields = body.fields ?? {}
    this.requestId = body.request_id
  }
}

const NETWORK_ERROR: ApiErrorBody = {
  code: "network_error",
  message: "Can't reach the server. Check that it is running and try again.",
  fields: {},
}

/** 401 codes that a refresh can fix: the access token expired (or its cookie already disappeared). */
const REFRESHABLE = new Set(["token_expired", "not_signed_in"])

type Method = "GET" | "POST" | "PATCH" | "DELETE"

export function readCookie(name: string): string | null {
  for (const part of document.cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=")
    if (key === name) return decodeURIComponent(rest.join("="))
  }
  return null
}

function csrfHeader(path: string): Record<string, string> {
  // /refresh is protected by the refresh token's CSRF value; everything else by the access token's.
  // Logout may run after the access cookie expired, so it falls back to the refresh value.
  const token =
    path === "/api/auth/refresh"
      ? readCookie("csrf_refresh_token")
      : (readCookie("csrf_access_token") ?? (path === "/api/auth/logout" ? readCookie("csrf_refresh_token") : null))
  return token ? { "X-CSRF-TOKEN": token } : {}
}

async function send(method: Method, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" }
  if (body !== undefined) headers["Content-Type"] = "application/json"
  if (method !== "GET") Object.assign(headers, csrfHeader(path))
  try {
    return await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    })
  } catch {
    throw new ApiError(0, NETWORK_ERROR)
  }
}

async function readError(res: Response): Promise<ApiError> {
  try {
    const json = await res.json()
    if (json && typeof json.error?.code === "string") return new ApiError(res.status, json.error)
  } catch {
    /* not JSON: fall through */
  }
  return new ApiError(res.status, {
    code: res.status >= 500 ? "server_error" : "http_error",
    message:
      res.status >= 500 ? "Something went wrong on the server. Please try again." : `Request failed (${res.status}).`,
    fields: {},
  })
}

// If several requests expire at the same moment, they share ONE refresh call.
let refreshing: Promise<boolean> | null = null

function refreshSession(): Promise<boolean> {
  refreshing ??= send("POST", "/api/auth/refresh")
    .then((res) => res.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

const NO_RETRY = new Set(["/api/auth/login", "/api/auth/register", "/api/auth/refresh", "/api/auth/logout"])

/** The whole answer: `data` plus `meta` (page numbers, polling hints). Most callers use request(). */
export async function requestFull<T, M = unknown>(
  method: Method,
  path: string,
  body?: unknown
): Promise<{ data: T; meta: M }> {
  let res = await send(method, path, body)

  if (res.status === 401 && !NO_RETRY.has(path) && readCookie("csrf_refresh_token")) {
    const error = await readError(res.clone())
    if (REFRESHABLE.has(error.code) && (await refreshSession())) {
      res = await send(method, path, body) // try once more with the new access token
    }
  }

  if (!res.ok) throw await readError(res)
  if (res.status === 204) return { data: undefined as T, meta: undefined as M }
  const json = await res.json()
  return { data: json.data as T, meta: json.meta as M }
}

export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  return (await requestFull<T>(method, path, body)).data
}

/** ?a=1&b=x from an object; empty, null and undefined values are left out. */
export function query(params: Params): string {
  const q = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") q.set(key, String(value))
  }
  const text = q.toString()
  return text ? `?${text}` : ""
}

function paged<T>(path: string): Promise<Paged<T>> {
  return requestFull<T[], PageMeta>("GET", path).then(({ data, meta }) => ({ items: data, meta }))
}

type Params = Record<string, string | number | boolean | null | undefined>

// ----------------------------------------------------------------------------- endpoints
export const api = {
  health: () => request<Health>("GET", "/api/health"),

  me: () => request<{ user: User }>("GET", "/api/auth/me").then((d) => d.user),
  login: (email: string, password: string) =>
    request<{ user: User }>("POST", "/api/auth/login", { email, password }).then((d) => d.user),
  register: (name: string, email: string, password: string) =>
    request<{ user: User }>("POST", "/api/auth/register", { name, email, password }).then((d) => d.user),
  logout: () => request<{ signed_out: boolean }>("POST", "/api/auth/logout"),

  // Settings
  updateProfile: (changes: Partial<Pick<User, "name" | "theme" | "default_model" | "default_temperature">>) =>
    request<{ user: User }>("PATCH", "/api/users/me", changes).then((d) => d.user),
  changePassword: (current_password: string, new_password: string) =>
    request<{ user: User }>("POST", "/api/users/me/password", { current_password, new_password }).then((d) => d.user),
  deleteAccount: (password: string) => request<void>("DELETE", "/api/users/me", { password }),

  config: () => request<AppConfig>("GET", "/api/config"),
  dashboard: () => request<Dashboard>("GET", "/api/dashboard"),

  // Playground
  chat: (body: { message: string; model: ModelId; temperature: number; top_k: number | null; session_id?: number }) =>
    request<ChatReply>("POST", "/api/chat", body),
  sessions: (page = 1) => paged<ChatSession>(`/api/chat/sessions${query({ page })}`),
  session: (id: number) =>
    request<{ session: ChatSession; messages: ChatMessage[] }>("GET", `/api/chat/sessions/${id}`),
  renameSession: (id: number, title: string) =>
    request<{ session: ChatSession }>("PATCH", `/api/chat/sessions/${id}`, { title }).then((d) => d.session),
  deleteSession: (id: number) => request<void>("DELETE", `/api/chat/sessions/${id}`),
  tokenize: (text: string) => request<Tokenized>("POST", "/api/tokenize", { text }),
  embeddings: (model: ModelId = "base") =>
    request<{ model: ModelId; points: EmbeddingPoint[] }>("GET", `/api/embeddings${query({ model })}`).then(
      (d) => d.points
    ),
  neighbors: (word: string, k = 5, model: ModelId = "base") =>
    request<{ word: string; neighbors: Neighbor[] }>("GET", `/api/embeddings/neighbors${query({ word, k, model })}`).then(
      (d) => d.neighbors
    ),

  // Dataset
  people: (params: Params) => paged<Person>(`/api/people${query(params)}`),
  facets: () => request<Facets>("GET", "/api/people/facets"),

  // Experiments
  experiments: (params: Params) => paged<Experiment>(`/api/experiments${query(params)}`),
  experiment: (id: number) =>
    request<{ experiment: Experiment; queue_position?: number }>("GET", `/api/experiments/${id}`),
  createExperiment: (settings: ExperimentSettings) =>
    request<{ experiment: Experiment }>("POST", "/api/experiments", settings).then((d) => d.experiment),
  updateExperiment: (id: number, changes: Partial<Pick<Experiment, "name" | "description" | "is_public">>) =>
    request<{ experiment: Experiment }>("PATCH", `/api/experiments/${id}`, changes).then((d) => d.experiment),
  deleteExperiment: (id: number) => request<void>("DELETE", `/api/experiments/${id}`),
  cancelExperiment: (id: number) =>
    request<{ experiment: Experiment }>("POST", `/api/experiments/${id}/cancel`).then((d) => d.experiment),
  metrics: (id: number, afterId = 0) =>
    requestFull<Metric[], MetricsPage["meta"]>("GET", `/api/experiments/${id}/metrics${query({ after_id: afterId })}`).then(
      ({ data, meta }): MetricsPage => ({ items: data, meta })
    ),
  runLog: (id: number) => request<{ lines: string[] }>("GET", `/api/experiments/${id}/log`).then((d) => d.lines),
  exportUrl: (id: number) => `/api/experiments/${id}/export.csv`,
  compare: (ids: number[]) =>
    request<{ experiments: Experiment[]; metrics: Record<string, Metric[]> }>(
      "GET",
      `/api/experiments/compare${query({ ids: ids.join(",") })}`
    ),

  // Activity
  activity: (params: Params) =>
    requestFull<ActivityEvent[], PageMeta & { unread: number }>("GET", `/api/activity${query(params)}`).then(
      ({ data, meta }) => ({ items: data, meta })
    ),
  markRead: (ids?: number[]) =>
    request<{ marked: number; unread: number }>("POST", "/api/activity/read", ids ? { ids } : {}),
}
