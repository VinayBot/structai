import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, getAccessToken, getRefreshToken, schemaApi } from '../../lib/api'
import { decodeJwt, maskToken } from '../../lib/jwt'
import { useCountdown } from '../../hooks/useCountdown'
import { formatMs } from '../../lib/format'
import type {
  ArchGraphResponse,
  ArchLiveRunEvent,
  ArchLiveRunRequest,
  SchemaValidateResponse,
} from '../../lib/types'
import { buildLiveRunCurl } from './LiveRunPanel'
import { Button } from '../ui/Button'
import { Chip } from '../ui/Chip'
import { JsonView } from '../ui/JsonView'

export const INSPECTOR_MIN_HEIGHT = 160
export const INSPECTOR_MAX_HEIGHT = 480
export const INSPECTOR_DEFAULT_HEIGHT = 240

const TABS = ['token', 'input', 'stages', 'output', 'api', 'raw'] as const
type InspectorTab = (typeof TABS)[number]

const TAB_LABELS: Record<InspectorTab, string> = {
  token: 'Token',
  input: 'Input',
  stages: 'Stages',
  output: 'Output',
  api: 'API',
  raw: 'Raw',
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

function TokenCard({ title, token }: { title: string; token: string | null }) {
  const payload = token ? decodeJwt(token) : null
  const expMs = payload && typeof payload.exp === 'number' ? payload.exp * 1000 : null
  const secondsLeft = useCountdown(expMs)
  const [copied, setCopied] = useState(false)

  async function copy() {
    if (!token) return
    await navigator.clipboard.writeText(token)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="flex-1 space-y-2 rounded-lg border border-border bg-surface-raised p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-text-dim">{title}</p>
        {secondsLeft !== null && (
          <Chip tone={secondsLeft > 60 ? 'success' : secondsLeft > 0 ? 'warning' : 'danger'}>
            {secondsLeft > 0 ? `expires in ${secondsLeft}s` : 'expired'}
          </Chip>
        )}
      </div>
      {token ? (
        <>
          <p className="font-mono text-xs text-text-dim">{maskToken(token)}</p>
          {payload ? (
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-bg p-2 text-xs text-text-dim">
              {JSON.stringify(payload, null, 2)}
            </pre>
          ) : (
            <p className="text-xs text-danger">Could not decode token.</p>
          )}
          <p className="text-xs text-text-dim">Signature is never decoded or displayed.</p>
          <Button variant="secondary" className="px-2 py-1 text-xs" onClick={() => void copy()}>
            {copied ? 'Copied!' : 'Copy raw token'}
          </Button>
        </>
      ) : (
        <p className="text-xs text-text-dim">No {title.toLowerCase()} found in this browser.</p>
      )}
    </div>
  )
}

interface InspectorDockProps {
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
  height: number
  onHeightChange: (height: number) => void
  graph: ArchGraphResponse
  events: ArchLiveRunEvent[]
  requestBody: ArchLiveRunRequest | null
  onActivateNode: (id: string) => void
}

/**
 * Bottom dock showing TOKEN/INPUT/STAGES/OUTPUT/API/RAW views of the current
 * Live Run session. Independent collapse/resize state from the side `SideDock`;
 * `ArchitecturePage` auto-expands it on Live Run start or a node click.
 */
export function InspectorDock({
  collapsed,
  onCollapsedChange,
  height,
  onHeightChange,
  graph,
  events,
  requestBody,
  onActivateNode,
}: InspectorDockProps) {
  const [activeTab, setActiveTab] = useState<InspectorTab>('token')
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [schemaResult, setSchemaResult] = useState<SchemaValidateResponse | null>(null)
  const [schemaError, setSchemaError] = useState<string | null>(null)

  const dragState = useRef<{ startY: number; startHeight: number } | null>(null)

  useEffect(() => {
    if (!requestBody) {
      setSchemaResult(null)
      setSchemaError(null)
      return
    }
    let cancelled = false
    schemaApi
      .validate(requestBody.schema_def)
      .then((res) => {
        if (cancelled) return
        setSchemaResult(res)
        setSchemaError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setSchemaResult(null)
        setSchemaError(err instanceof ApiError ? err.message : 'Could not validate schema.')
      })
    return () => {
      cancelled = true
    }
  }, [requestBody])

  async function copyText(key: string, text: string) {
    await navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 1500)
  }

  function handleResizeStart(event: React.PointerEvent<HTMLDivElement>) {
    event.preventDefault()
    dragState.current = { startY: event.clientY, startHeight: height }

    function handleMove(moveEvent: PointerEvent) {
      const drag = dragState.current
      if (!drag) return
      const delta = drag.startY - moveEvent.clientY
      const next = Math.min(INSPECTOR_MAX_HEIGHT, Math.max(INSPECTOR_MIN_HEIGHT, drag.startHeight + delta))
      onHeightChange(next)
    }
    function handleUp() {
      dragState.current = null
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
    }
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
  }

  if (collapsed) {
    return (
      <button
        type="button"
        aria-label="Expand Inspector"
        onClick={() => onCollapsedChange(false)}
        className="flex w-full shrink-0 items-center justify-center gap-2 border-t border-border bg-surface px-4 py-2 text-xs font-medium text-text-dim hover:text-text"
      >
        Inspector
      </button>
    )
  }

  const final = events.length > 0 ? events[events.length - 1] : null
  const finalPassed =
    final !== null && final.node_id === 'output_guardrails' && isSuccessStatus(final.status)
  const finalModified = finalPassed && final?.status === 'modified'
  const touchedNodeIds = Array.from(new Set(events.map((e) => e.node_id)))

  return (
    <section
      style={{ '--inspector-height': `${height}px` } as React.CSSProperties}
      className="relative flex h-[var(--inspector-height)] w-full shrink-0 flex-col border-t border-border bg-surface"
    >
      <div
        role="separator"
        aria-orientation="horizontal"
        aria-label="Resize Inspector"
        onPointerDown={handleResizeStart}
        className="absolute inset-x-0 top-0 h-1.5 -translate-y-1/2 cursor-row-resize touch-none hover:bg-accent/40"
      />
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div className="flex gap-1 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`shrink-0 rounded px-2 py-1 text-xs font-medium ${
                activeTab === tab ? 'bg-accent/15 text-accent' : 'text-text-dim hover:text-text'
              }`}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>
        <button
          type="button"
          aria-label="Collapse Inspector"
          onClick={() => onCollapsedChange(true)}
          className="shrink-0 rounded px-1.5 py-0.5 text-xs text-text-dim hover:bg-surface-raised hover:text-text"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {activeTab === 'token' && (
          <div className="flex flex-col gap-2 md:flex-row">
            <TokenCard title="Access token" token={getAccessToken()} />
            <TokenCard title="Refresh token" token={getRefreshToken()} />
          </div>
        )}

        {activeTab === 'input' && (
          <div className="space-y-3">
            {!requestBody ? (
              <p className="text-xs text-text-dim">Run a Live Run to see the exact request sent.</p>
            ) : (
              <>
                <div>
                  <p className="mb-1 text-xs font-semibold text-text-dim">cURL (Authorization masked)</p>
                  <pre className="whitespace-pre-wrap break-words rounded-lg bg-bg p-2 text-xs text-text-dim">
                    {buildLiveRunCurl(requestBody)}
                  </pre>
                  <Button
                    variant="secondary"
                    className="mt-1 px-2 py-1 text-xs"
                    onClick={() => void copyText('input-curl', buildLiveRunCurl(requestBody))}
                  >
                    {copiedKey === 'input-curl' ? 'Copied!' : 'Copy as cURL'}
                  </Button>
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold text-text-dim">Request body</p>
                  <JsonView data={requestBody} />
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold text-text-dim">Generated JSON Schema</p>
                  {schemaError ? (
                    <p className="text-xs text-danger">{schemaError}</p>
                  ) : schemaResult ? (
                    <JsonView data={schemaResult.json_schema} />
                  ) : (
                    <p className="text-xs text-text-dim">Validating...</p>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'stages' && (
          <div className="space-y-1.5">
            {events.length === 0 ? (
              <p className="text-xs text-text-dim">Run a Live Run to see each pipeline stage here.</p>
            ) : (
              events.map((event, idx) => (
                <button
                  key={`${event.node_id}-${idx}`}
                  type="button"
                  onClick={() => onActivateNode(event.node_id)}
                  className="flex w-full items-start gap-2 rounded-lg bg-bg p-2 text-left text-xs hover:bg-surface-raised"
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
                </button>
              ))
            )}
          </div>
        )}

        {activeTab === 'output' && (
          <div className="space-y-2">
            {!final ? (
              <p className="text-xs text-text-dim">Run a Live Run to see its final output here.</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone={finalPassed ? (finalModified ? 'warning' : 'success') : 'danger'}>
                    {finalPassed ? (finalModified ? 'Passed (redacted)' : 'Passed') : 'Failed'}
                  </Chip>
                  {final.provider && (
                    <Chip tone="accent">
                      {final.provider} / {final.model}
                    </Chip>
                  )}
                  {final.attempts != null && (
                    <span className="text-xs text-text-dim">{final.attempts} attempt(s)</span>
                  )}
                  {final.trace_id && (
                    <Link
                      to={`/app/traces?trace_id=${final.trace_id}`}
                      className="text-xs text-accent hover:underline"
                    >
                      view trace
                    </Link>
                  )}
                </div>
                <JsonView data={final.data ?? {}} />
                <div className="flex flex-wrap gap-1.5">
                  <Button
                    variant="secondary"
                    className="px-2 py-1 text-xs"
                    onClick={() => void copyText('output', JSON.stringify(final.data ?? {}, null, 2))}
                  >
                    {copiedKey === 'output' ? 'Copied!' : 'Copy result JSON'}
                  </Button>
                  {requestBody && (
                    <Button
                      variant="secondary"
                      className="px-2 py-1 text-xs"
                      onClick={() => void copyText('output-curl', buildLiveRunCurl(requestBody))}
                    >
                      {copiedKey === 'output-curl' ? 'Copied!' : 'Copy as cURL'}
                    </Button>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'api' && (
          <div className="space-y-1.5">
            {touchedNodeIds.length === 0 ? (
              <p className="text-xs text-text-dim">
                Run a Live Run to see which backend endpoints and modules this request touches. A run flows
                through authentication, request validation, rate limiting, prompt-injection screening, PII
                redaction, schema building, model routing, output validation/retry, and output guardrails, in
                that order.
              </p>
            ) : (
              touchedNodeIds.map((id) => {
                const node = graph.nodes.find((n) => n.id === id)
                if (!node) return null
                return (
                  <div key={id} className="rounded-lg bg-bg p-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-text">{node.label}</p>
                      <Button
                        variant="secondary"
                        className="px-2 py-0.5 text-xs"
                        onClick={() => onActivateNode(node.id)}
                      >
                        Open
                      </Button>
                    </div>
                    <p className="text-text-dim">{node.code_path}</p>
                    {node.endpoints.length > 0 && (
                      <ul className="mt-1 space-y-0.5">
                        {node.endpoints.map((ep) => (
                          <li key={`${ep.method}-${ep.path}`} className="text-text-dim">
                            <code className="text-text">{ep.method}</code> {ep.path}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )
              })
            )}
          </div>
        )}

        {activeTab === 'raw' && <JsonView data={events} />}
      </div>
    </section>
  )
}
