import { isTokenNearExpiry } from './jwt'
import { extractSseEvents } from './sse'
import type {
  ApiErrorBody,
  ArchGraphResponse,
  ArchLiveRunEvent,
  ArchLiveRunRequest,
  ArchScenarioId,
  ArchStatusResponse,
  ArchTestRunResponse,
  Chat,
  ChatDetail,
  EmailCheckResponse,
  EvalDashboardResponse,
  EvalReport,
  EvalRunDetail,
  EvalRunRequest,
  EvalRunSummary,
  EvalStreamEvent,
  FileAttachment,
  GoldenCase,
  HealthResponse,
  Message,
  MetricsSummaryResponse,
  OpenApiDoc,
  Page,
  Project,
  SchemaDef,
  SchemaValidateResponse,
  Span,
  StreamEvent,
  StructuredAnswerRequest,
  StructuredAnswerResponse,
  Tier,
  TokenResponse,
  UsageResponse,
  User,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

const ACCESS_TOKEN_KEY = 'structai_access_token'
const REFRESH_TOKEN_KEY = 'structai_refresh_token'

export class ApiError extends Error {
  code: string
  status: number
  requestId: string | null
  retryAfterSeconds: number | null
  suggestion: string | null

  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null,
    retryAfterSeconds: number | null = null,
    suggestion: string | null = null,
  ) {
    super(message)
    this.status = status
    this.code = code
    this.requestId = requestId
    this.retryAfterSeconds = retryAfterSeconds
    this.suggestion = suggestion
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(tokens: TokenResponse): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody
    return new ApiError(
      res.status,
      body.error.code,
      body.error.message,
      body.error.request_id,
      body.error.retry_after_seconds ?? null,
      body.error.suggestion ?? null,
    )
  } catch {
    return new ApiError(res.status, 'unknown_error', res.statusText, null)
  }
}

interface FetchOptions {
  method?: string
  body?: unknown
  auth?: boolean
  skipRefresh?: boolean
}

function buildHeaders(auth: boolean, hasBody: boolean): Record<string, string> {
  const headers: Record<string, string> = {}
  if (hasBody) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  return headers
}

/** Proactively refreshes the access token if it's near expiry, so a long-lived SSE
 * connection doesn't start on a token that will expire mid-stream. Best-effort: a
 * failed refresh here just leaves the existing (possibly-401) token in place, and the
 * normal 401-retry path below still catches it. */
async function ensureFreshToken(): Promise<void> {
  const token = getAccessToken()
  if (token && isTokenNearExpiry(token)) {
    await tryRefresh()
  }
}

async function request<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, skipRefresh = false } = opts

  const headers = buildHeaders(auth, body !== undefined)
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && auth && !skipRefresh && path !== '/api/v1/auth/refresh') {
    const refreshed = await tryRefresh()
    if (refreshed) return request<T>(path, { ...opts, skipRefresh: true })
  }

  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false
  try {
    const tokens = await request<TokenResponse>('/api/v1/auth/refresh', {
      method: 'POST',
      body: { refresh_token: refreshToken },
      auth: false,
    })
    setTokens(tokens)
    return true
  } catch {
    clearTokens()
    return false
  }
}

export const authApi = {
  register: (email: string, password: string) =>
    request<User>('/api/v1/auth/register', { method: 'POST', body: { email, password }, auth: false }),
  checkEmail: (email: string) =>
    request<EmailCheckResponse>('/api/v1/auth/check-email', {
      method: 'POST',
      body: { email },
      auth: false,
    }),
  login: (email: string, password: string) =>
    request<TokenResponse>('/api/v1/auth/login', { method: 'POST', body: { email, password }, auth: false }),
  me: () => request<User>('/api/v1/auth/me'),
  logout: (refreshToken: string) =>
    request<void>('/api/v1/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } }),
}

export const schemaApi = {
  validate: (schema: SchemaDef) =>
    request<SchemaValidateResponse>('/api/v1/schemas/validate', { method: 'POST', body: schema }),
}

export const structuredApi = {
  answer: (body: StructuredAnswerRequest) =>
    request<StructuredAnswerResponse>('/api/v1/structured/answer', { method: 'POST', body }),
}

export const projectsApi = {
  list: () => request<Page<Project>>('/api/v1/projects'),
  create: (name: string) => request<Project>('/api/v1/projects', { method: 'POST', body: { name } }),
  remove: (id: string) => request<void>(`/api/v1/projects/${id}`, { method: 'DELETE' }),
}

export const chatsApi = {
  list: (projectId?: string) =>
    request<Page<Chat>>(`/api/v1/chats${projectId ? `?project_id=${projectId}` : ''}`),
  create: (title: string, projectId?: string | null) =>
    request<Chat>('/api/v1/chats', { method: 'POST', body: { title, project_id: projectId ?? null } }),
  get: (id: string) => request<ChatDetail>(`/api/v1/chats/${id}`),
  remove: (id: string) => request<void>(`/api/v1/chats/${id}`, { method: 'DELETE' }),
  addMessage: (
    chatId: string,
    message: {
      role: 'user' | 'assistant'
      content: string
      structured_data?: Record<string, unknown> | null
      provider?: string | null
      model?: string | null
    },
  ) => request<Message>(`/api/v1/chats/${chatId}/messages`, { method: 'POST', body: message }),
}

export const evalApi = {
  cases: () => request<GoldenCase[]>('/api/v1/eval/cases'),
  /** Non-streaming run — unused by EvaluationPage (which uses streamEvalRun below) but kept for parity with the route. */
  runSync: (body: EvalRunRequest) => request<EvalReport>('/api/v1/eval/run', { method: 'POST', body }),
  runs: (limit?: number) =>
    request<Page<EvalRunSummary>>(`/api/v1/eval/runs${limit !== undefined ? `?limit=${limit}` : ''}`),
  runDetail: (id: string) => request<EvalRunDetail>(`/api/v1/eval/runs/${id}`),
  dashboard: () => request<EvalDashboardResponse>('/api/v1/eval/dashboard'),
}

export const tracesApi = {
  list: (limit = 100) => request<Span[]>(`/api/v1/traces?limit=${limit}`),
}

export const metricsApi = {
  raw: async (): Promise<string> => {
    const res = await fetch(`${API_BASE}/metrics`)
    if (!res.ok) throw await parseError(res)
    return res.text()
  },
  summary: () => request<MetricsSummaryResponse>('/metrics/summary'),
}

async function fetchAuthedBlob(path: string): Promise<Blob> {
  const headers: Record<string, string> = {}
  const token = getAccessToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { headers })
  if (!res.ok) throw await parseError(res)
  return res.blob()
}

export const filesApi = {
  upload: (file: File, chatId?: string | null) => {
    const headers: Record<string, string> = {}
    const token = getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`

    const form = new FormData()
    form.append('file', file)

    const query = chatId ? `?chat_id=${encodeURIComponent(chatId)}` : ''
    return fetch(`${API_BASE}/api/v1/files${query}`, { method: 'POST', headers, body: form }).then(
      async (res) => {
        if (!res.ok) throw await parseError(res)
        return (await res.json()) as FileAttachment
      },
    )
  },
  list: (chatId?: string) =>
    request<Page<FileAttachment>>(`/api/v1/files${chatId ? `?chat_id=${chatId}` : ''}`),
  get: (id: string) => request<FileAttachment>(`/api/v1/files/${id}`),
  remove: (id: string) => request<void>(`/api/v1/files/${id}`, { method: 'DELETE' }),
  contentBlobUrl: async (id: string): Promise<string> => {
    const blob = await fetchAuthedBlob(`/api/v1/files/${id}/content`)
    return URL.createObjectURL(blob)
  },
}

export const archApi = {
  graph: () => request<ArchGraphResponse>('/api/v1/arch/graph'),
  status: () => request<ArchStatusResponse>('/api/v1/arch/status'),
  testRun: (scenarioId: ArchScenarioId) =>
    request<ArchTestRunResponse>('/api/v1/arch/test-run', {
      method: 'POST',
      body: { scenario_id: scenarioId },
    }),
  openapi: () => request<OpenApiDoc>('/openapi.json', { auth: false }),
}

export const usageApi = {
  get: () => request<UsageResponse>('/api/v1/usage'),
}

export const healthApi = {
  get: () => request<HealthResponse>('/health', { auth: false }),
}

export interface TryItResult {
  status: number
  ok: boolean
  latencyMs: number
  headers: Record<string, string>
  body: unknown
}

/**
 * Issues a real authenticated call against any Architecture-tab endpoint for the
 * drawer's "Try it" tab. Deliberately bypasses `request()`'s 401-refresh/error-throw
 * behavior - a failed call is a result to display, not an exception to catch.
 */
export async function archTryIt(
  method: string,
  path: string,
  body: unknown,
  auth: boolean,
): Promise<TryItResult> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const start = performance.now()
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const latencyMs = performance.now() - start

  const responseHeaders: Record<string, string> = {}
  res.headers.forEach((value, key) => {
    responseHeaders[key] = value
  })

  let parsedBody: unknown = null
  const text = await res.text()
  if (text) {
    try {
      parsedBody = JSON.parse(text)
    } catch {
      parsedBody = text
    }
  }

  return { status: res.status, ok: res.ok, latencyMs, headers: responseHeaders, body: parsedBody }
}

/**
 * Streams a POST SSE endpoint by hand (EventSource can't send POST bodies or
 * custom headers), buffering raw chunks into complete JSON events. Mirrors
 * request()'s 401-refresh-then-retry-once behavior, since a stream that opens right
 * as the access token expires would otherwise fail with no way to recover mid-flight.
 */
async function streamSse<T>(
  path: string,
  body: unknown,
  onEvent: (event: T) => void,
  signal?: AbortSignal,
  skipRefresh = false,
): Promise<void> {
  if (!skipRefresh) await ensureFreshToken()

  const headers = buildHeaders(true, true)
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal,
  })

  if (res.status === 401 && !skipRefresh) {
    const refreshed = await tryRefresh()
    if (refreshed) return streamSse<T>(path, body, onEvent, signal, true)
  }

  if (!res.ok || !res.body) throw await parseError(res)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const { events, rest } = extractSseEvents<T>(buffer)
    buffer = rest
    for (const event of events) onEvent(event)
  }
}

export function streamStructuredAnswer(
  prompt: string,
  schema: SchemaDef,
  tier: Tier,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse<StreamEvent>(
    '/api/v1/structured/answer/stream',
    { prompt, schema_def: schema, tier },
    onEvent,
    signal,
  )
}

export function streamEvalRun(
  body: EvalRunRequest,
  onEvent: (event: EvalStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse<EvalStreamEvent>('/api/v1/eval/run/stream', body, onEvent, signal)
}

export function streamArchLiveRun(
  body: ArchLiveRunRequest,
  onEvent: (event: ArchLiveRunEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse<ArchLiveRunEvent>('/api/v1/arch/live-run', body, onEvent, signal)
}
