import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ApiError, getAccessToken, schemaApi, streamArchLiveRun, usageApi } from '../../lib/api'
import { formatMs } from '../../lib/format'
import { useCountdown } from '../../hooks/useCountdown'
import {
  loadLiveRunHistory,
  pushLiveRunHistory,
  saveLiveRunHistory,
  type LiveRunHistoryEntry,
} from '../../lib/liveRunHistory'
import { DEMO_ATTACK_PRESET, DEMO_PII_PRESET, DEMO_RUN_PRESET } from './livePresets'
import type {
  ArchLiveRunEvent,
  ArchLiveRunProvider,
  ArchLiveRunRequest,
  ArchPiiMode,
  ArchStatusResponse,
  SchemaDef,
  Tier,
  UsageResponse,
} from '../../lib/types'
import { emptyField, SchemaBuilder } from '../../features/schema-builder/SchemaBuilder'
import { Button } from '../ui/Button'
import { Chip } from '../ui/Chip'
import { Select } from '../ui/Select'
import { Spinner } from '../ui/Spinner'
import { Textarea } from '../ui/Input'

const SCHEMA_VALIDATE_DEBOUNCE_MS = 400

export function buildLiveRunCurl(body: ArchLiveRunRequest): string {
  const origin = window.location.origin
  const hasToken = Boolean(getAccessToken())
  const lines = [
    `curl -N -X POST "${origin}/arch/live-run" \\`,
    `  -H "Authorization: Bearer ${hasToken ? '<your-access-token>' : '<access-token>'}" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '${JSON.stringify(body)}'`,
  ]
  return lines.join('\n')
}

function isSuccessStatus(status: ArchLiveRunEvent['status']): boolean {
  return status === 'passed' || status === 'modified'
}

function statusTone(
  status: ArchLiveRunEvent['status'],
): 'success' | 'danger' | 'neutral' | 'accent' | 'warning' {
  if (status === 'passed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'accent'
  if (status === 'modified') return 'warning'
  return 'neutral'
}

function friendlyMessage(err: ApiError): string {
  switch (err.status) {
    case 401:
      return 'Your session expired and could not be refreshed. Log in again to continue.'
    case 403:
      return "You don't have permission to run this."
    case 409:
      return err.message || 'Conflict with existing state - try again.'
    case 422:
      return err.message || 'The request was rejected as invalid.'
    case 429:
      return 'Rate limit reached - the run was stopped before calling a model.'
    case 502:
      return 'The model provider failed to generate a usable response.'
    case 504:
      return 'The request timed out waiting for a response.'
    default:
      return err.message || `Request failed with status ${err.status}.`
  }
}

interface LiveRunPanelProps {
  status: ArchStatusResponse | null
  onStart: (body: ArchLiveRunRequest) => void
  onEvent: (event: ArchLiveRunEvent) => void
  onDone: (passed: boolean, finalEvent: ArchLiveRunEvent | null) => void
}

export function LiveRunPanel({ status, onStart, onEvent, onDone }: LiveRunPanelProps) {
  const [prompt, setPrompt] = useState('')
  const [schema, setSchema] = useState<SchemaDef>({ fields: [emptyField()] })
  const [tier, setTier] = useState<Tier>('fast')
  const [provider, setProvider] = useState<ArchLiveRunProvider>('auto')
  const [model, setModel] = useState('')
  const [strictProvider, setStrictProvider] = useState(false)
  const [piiMode, setPiiMode] = useState<ArchPiiMode | ''>('')
  const [showRawOutput, setShowRawOutput] = useState(false)

  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<ArchLiveRunEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const [errorDetail, setErrorDetail] = useState<ApiError | null>(null)
  const [retryDeadline, setRetryDeadline] = useState<number | null>(null)
  const [usage, setUsage] = useState<UsageResponse | null>(null)
  const [history, setHistory] = useState<LiveRunHistoryEntry[]>(loadLiveRunHistory)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [schemaValid, setSchemaValid] = useState(false)
  const [schemaValidating, setSchemaValidating] = useState(false)
  const [schemaValidateError, setSchemaValidateError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)

  const hasEmptyFieldName = schema.fields.some((f) => !f.name.trim())

  useEffect(() => {
    if (hasEmptyFieldName) {
      setSchemaValid(false)
      setSchemaValidating(false)
      setSchemaValidateError(null)
      return
    }

    let cancelled = false
    setSchemaValidating(true)
    const timer = setTimeout(() => {
      schemaApi
        .validate(schema)
        .then((res) => {
          if (cancelled) return
          setSchemaValid(res.valid)
          setSchemaValidateError(null)
        })
        .catch((err) => {
          if (cancelled) return
          setSchemaValid(false)
          setSchemaValidateError(err instanceof ApiError ? err.message : 'Could not validate schema.')
        })
        .finally(() => {
          if (!cancelled) setSchemaValidating(false)
        })
    }, SCHEMA_VALIDATE_DEBOUNCE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [schema, hasEmptyFieldName])

  const retryCountdown = useCountdown(retryDeadline)

  useEffect(() => {
    usageApi
      .get()
      .then(setUsage)
      .catch(() => {
        // quota warning is best-effort only
      })
  }, [])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  async function copyText(key: string, text: string) {
    await navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 1500)
  }

  function buildBody(): ArchLiveRunRequest {
    return {
      prompt,
      schema_def: schema,
      tier,
      provider,
      model: model.trim() ? model.trim() : null,
      strict_provider: strictProvider,
      pii_mode: piiMode || null,
    }
  }

  async function run(body: ArchLiveRunRequest) {
    if (running) return
    const ac = new AbortController()
    abortRef.current = ac
    setRunning(true)
    setEvents([])
    setError(null)
    setErrorDetail(null)
    setRetryDeadline(null)
    onStart(body)

    const collected: ArchLiveRunEvent[] = []
    try {
      await streamArchLiveRun(
        body,
        (event) => {
          collected.push(event)
          setEvents((prev) => [...prev, event])
          onEvent(event)
        },
        ac.signal,
      )
      const final = collected.length > 0 ? collected[collected.length - 1] : null
      const passed = final !== null && final.node_id === 'output_guardrails' && isSuccessStatus(final.status)
      onDone(passed, final)
      const entry: LiveRunHistoryEntry = {
        id: crypto.randomUUID(),
        ranAt: new Date().toISOString(),
        request: body,
        passed,
        summary: passed ? 'Passed' : final?.output_summary ?? 'Run failed',
        finalEvent: final,
      }
      setHistory((prev) => {
        const next = pushLiveRunHistory(prev, entry)
        saveLiveRunHistory(next)
        return next
      })
    } catch (err) {
      if (ac.signal.aborted) {
        // user-initiated stop, not an error
      } else if (err instanceof ApiError) {
        setError(friendlyMessage(err))
        setErrorDetail(err)
        if (err.status === 429 && err.retryAfterSeconds != null) {
          setRetryDeadline(Date.now() + err.retryAfterSeconds * 1000)
        } else {
          setRetryDeadline(null)
        }
      } else {
        setError('Could not reach the API - check your connection and that the backend is running.')
        setErrorDetail(null)
        setRetryDeadline(null)
      }
    } finally {
      setRunning(false)
    }
  }

  function handleRerun(entry: LiveRunHistoryEntry) {
    setPrompt(entry.request.prompt)
    setSchema(entry.request.schema_def)
    setTier(entry.request.tier)
    setProvider(entry.request.provider)
    setModel(entry.request.model ?? '')
    setStrictProvider(entry.request.strict_provider)
    setPiiMode(entry.request.pii_mode ?? '')
    void run(entry.request)
  }

  function applyPreset(preset: ArchLiveRunRequest) {
    setPrompt(preset.prompt)
    setSchema(preset.schema_def)
    setTier(preset.tier)
    setProvider(preset.provider)
    setModel(preset.model ?? '')
    setStrictProvider(preset.strict_provider)
    setPiiMode(preset.pii_mode ?? '')
    void run(preset)
  }

  const modelsForProvider =
    provider === 'ollama' ? status?.ollama.models ?? [] : provider === 'groq' ? status?.groq.models ?? [] : []

  const strictNeedsPinnedProvider = strictProvider && provider === 'auto'
  const canRun =
    Boolean(prompt.trim()) && !hasEmptyFieldName && !strictNeedsPinnedProvider && !running && schemaValid

  const quotaExhausted = usage !== null && usage.user_count_today >= usage.user_limit
  const final = events.length > 0 ? events[events.length - 1] : null
  const finalPassed =
    final !== null && final.node_id === 'output_guardrails' && isSuccessStatus(final.status)
  const finalModified = finalPassed && final?.status === 'modified'
  const maxLatency = Math.max(1, ...events.map((e) => e.latency_ms ?? 0))

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
      <div>
        <label className="mb-1 block text-xs font-medium text-text-dim">Prompt</label>
        <Textarea
          rows={3}
          placeholder="Ask anything..."
          value={prompt}
          disabled={running}
          onChange={(e) => setPrompt(e.target.value)}
        />
      </div>

      <div>
        <p className="mb-1 text-xs font-medium text-text-dim">Output schema</p>
        <SchemaBuilder schema={schema} onChange={setSchema} />
        {!hasEmptyFieldName && schemaValidating && (
          <p className="mt-1 text-xs text-text-dim">Validating schema...</p>
        )}
        {!hasEmptyFieldName && !schemaValidating && schemaValidateError && (
          <p className="mt-1 text-xs text-danger">{schemaValidateError}</p>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <Select
          aria-label="Tier"
          value={tier}
          disabled={running}
          onChange={(e) => setTier(e.target.value as Tier)}
          className="w-28"
        >
          <option value="fast">fast</option>
          <option value="smart">smart</option>
        </Select>
        <Select
          aria-label="Provider"
          value={provider}
          disabled={running}
          onChange={(e) => {
            setProvider(e.target.value as ArchLiveRunProvider)
            setModel('')
          }}
          className="w-28"
        >
          <option value="auto">auto</option>
          <option value="ollama">ollama</option>
          <option value="groq">groq</option>
        </Select>
        <Select
          aria-label="Model"
          value={model}
          disabled={running || provider === 'auto'}
          onChange={(e) => setModel(e.target.value)}
          className="min-w-40 flex-1"
        >
          <option value="">(default for tier)</option>
          {modelsForProvider.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </Select>
        <Select
          aria-label="PII mode override"
          value={piiMode}
          disabled={running}
          onChange={(e) => setPiiMode(e.target.value as ArchPiiMode | '')}
          className="w-40"
        >
          <option value="">PII mode: default</option>
          <option value="redact">PII mode: redact</option>
          <option value="block">PII mode: block</option>
        </Select>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-text-dim">
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={strictProvider}
            disabled={running}
            onChange={(e) => setStrictProvider(e.target.checked)}
          />
          strict provider (no fallback)
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={showRawOutput}
            onChange={(e) => setShowRawOutput(e.target.checked)}
          />
          show raw event stream
        </label>
      </div>

      {strictNeedsPinnedProvider && (
        <p className="text-xs text-danger">Strict provider requires pinning "ollama" or "groq", not "auto".</p>
      )}

      {usage && (
        <p className={`text-xs ${quotaExhausted ? 'text-danger' : 'text-text-dim'}`}>
          Usage today: {usage.user_count_today}/{usage.user_limit} requests
          {quotaExhausted
            ? " - today's quota is reached, this run will likely fail at the rate limiter step."
            : ''}
        </p>
      )}

      <div className="flex gap-1.5">
        <Button onClick={() => void run(buildBody())} disabled={!canRun} className="px-3 py-1.5 text-xs">
          {running && <Spinner />}
          Run
        </Button>
        <Button
          variant="secondary"
          disabled={!running}
          onClick={() => abortRef.current?.abort()}
          className="px-3 py-1.5 text-xs"
        >
          Stop
        </Button>
        <Button
          variant="secondary"
          onClick={() => void copyText('curl', buildLiveRunCurl(buildBody()))}
          className="px-3 py-1.5 text-xs"
        >
          {copiedKey === 'curl' ? 'Copied!' : 'Copy as cURL'}
        </Button>
      </div>

      <div className="flex gap-1.5">
        <Button
          variant="secondary"
          disabled={running}
          onClick={() => applyPreset(DEMO_RUN_PRESET)}
          className="px-3 py-1.5 text-xs"
        >
          Demo: run
        </Button>
        <Button
          variant="secondary"
          disabled={running}
          onClick={() => applyPreset(DEMO_ATTACK_PRESET)}
          className="px-3 py-1.5 text-xs"
        >
          Demo: attack
        </Button>
        <Button
          variant="secondary"
          disabled={running}
          onClick={() => applyPreset(DEMO_PII_PRESET)}
          className="px-3 py-1.5 text-xs"
        >
          Demo: pii
        </Button>
      </div>

      {error && (
        <div className="space-y-1.5 rounded-lg border border-danger/30 bg-danger/5 p-2">
          <p className="text-xs text-danger">{error}</p>
          {retryCountdown !== null && (
            <p className="text-xs text-text-dim">
              {retryCountdown > 0 ? `Try again in ${retryCountdown}s` : 'You can try again now.'}
            </p>
          )}
          {errorDetail && (
            <details className="text-xs">
              <summary className="cursor-pointer text-text-dim">Details</summary>
              <dl className="mt-1 space-y-0.5 text-text-dim">
                <div>status: {errorDetail.status}</div>
                <div>code: {errorDetail.code}</div>
                {errorDetail.requestId && <div>request id: {errorDetail.requestId}</div>}
                {errorDetail.retryAfterSeconds != null && (
                  <div>retry after: {errorDetail.retryAfterSeconds}s</div>
                )}
                <div>message: {errorDetail.message}</div>
              </dl>
            </details>
          )}
          <Button
            variant="secondary"
            className="px-2 py-1 text-xs"
            onClick={() =>
              void copyText(
                'debug',
                JSON.stringify(
                  {
                    status: errorDetail?.status ?? null,
                    code: errorDetail?.code ?? null,
                    message: error,
                    request_id: errorDetail?.requestId ?? null,
                    retry_after_seconds: errorDetail?.retryAfterSeconds ?? null,
                    occurred_at: new Date().toISOString(),
                  },
                  null,
                  2,
                ),
              )
            }
          >
            {copiedKey === 'debug' ? 'Copied!' : 'Copy debug info'}
          </Button>
        </div>
      )}

      {events.length > 0 && (
        <div className="flex-1 space-y-3">
          <ol className="space-y-1.5">
            <AnimatePresence>
              {events.map((event, idx) => (
                <motion.li
                  key={`${event.node_id}-${idx}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex items-start gap-2 rounded-lg bg-bg p-2 text-xs"
                >
                  <Chip tone={statusTone(event.status)}>{event.status}</Chip>
                  <div className="min-w-0 flex-1">
                    <p className="text-text">{event.node_id}</p>
                    {event.input_summary && <p className="text-text-dim">in: {event.input_summary}</p>}
                    {event.output_summary && <p className="text-text-dim">out: {event.output_summary}</p>}
                    {event.http_status && (
                      <p className="text-text-dim">
                        {event.http_status} {event.error_code}
                      </p>
                    )}
                  </div>
                  {event.latency_ms != null && (
                    <span className="shrink-0 text-text-dim">{formatMs(event.latency_ms)}</span>
                  )}
                </motion.li>
              ))}
            </AnimatePresence>
          </ol>

          {!running && final && (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={finalPassed ? (finalModified ? 'warning' : 'success') : 'danger'}>
                  {finalPassed ? (finalModified ? 'Passed (redacted)' : 'Passed') : 'Failed'}
                </Chip>
                {final.provider && <Chip tone="accent">{final.provider} / {final.model}</Chip>}
                {final.attempts != null && (
                  <span className="text-xs text-text-dim">{final.attempts} attempt(s)</span>
                )}
              </div>

              {finalModified && (
                <p className="text-xs text-warning">{final.output_summary}</p>
              )}

              {finalPassed && final.data && (
                <details open>
                  <summary className="cursor-pointer text-xs text-accent">Result data</summary>
                  <pre className="mt-1 whitespace-pre-wrap break-words rounded-lg bg-surface p-2 text-xs text-text-dim">
                    {JSON.stringify(final.data, null, 2)}
                  </pre>
                </details>
              )}

              {!finalPassed && <p className="text-xs text-danger">{final.output_summary}</p>}

              <div className="space-y-1">
                <p className="text-xs font-semibold text-text-dim">Timing</p>
                {events
                  .filter((e) => e.latency_ms != null)
                  .map((e, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-xs">
                      <span className="w-32 shrink-0 truncate text-text-dim">{e.node_id}</span>
                      <div className="h-1.5 flex-1 rounded bg-surface-raised">
                        <div
                          className="h-1.5 rounded bg-accent"
                          style={{ width: `${((e.latency_ms ?? 0) / maxLatency) * 100}%` }}
                        />
                      </div>
                      <span className="w-16 shrink-0 text-right text-text-dim">{formatMs(e.latency_ms ?? 0)}</span>
                    </div>
                  ))}
              </div>

              {final.trace_id && <p className="text-xs text-text-dim">trace: {final.trace_id}</p>}

              {showRawOutput && (
                <details>
                  <summary className="cursor-pointer text-xs text-accent">Raw event stream</summary>
                  <pre className="mt-1 whitespace-pre-wrap break-words rounded-lg bg-surface p-2 text-xs text-text-dim">
                    {JSON.stringify(events, null, 2)}
                  </pre>
                </details>
              )}

              <div className="flex flex-wrap gap-1.5">
                <Button
                  variant="secondary"
                  className="px-2 py-1 text-xs"
                  onClick={() => void copyText('output', JSON.stringify(final.data ?? {}, null, 2))}
                >
                  {copiedKey === 'output' ? 'Copied!' : 'Copy result JSON'}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {history.length > 0 && (
        <div className="space-y-1.5 border-t border-border pt-3">
          <p className="text-xs font-semibold text-text-dim">Recent runs</p>
          <ul className="space-y-1">
            {history.map((entry) => (
              <li
                key={entry.id}
                className="flex items-center justify-between gap-2 rounded-lg bg-bg p-2 text-xs"
              >
                <div className="min-w-0 flex-1">
                  <p className={entry.passed ? 'text-success' : 'text-danger'}>{entry.summary}</p>
                  <p className="truncate text-text-dim">{entry.request.prompt}</p>
                </div>
                <Button
                  variant="secondary"
                  disabled={running}
                  className="shrink-0 px-2 py-1 text-xs"
                  onClick={() => handleRerun(entry)}
                >
                  Re-run
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
