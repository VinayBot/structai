import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { tracesApi } from '../lib/api'
import { groupSpansByTrace } from '../lib/traces'
import type { Span } from '../lib/types'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Chip } from '../components/ui/Chip'
import { Spinner } from '../components/ui/Spinner'

function formatTime(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleTimeString()
}

function SpanRow({ span, indent = false }: { span: Span; indent?: boolean }) {
  const attrEntries = Object.entries(span.attributes)
  return (
    <div className={`rounded-lg border border-border bg-surface-raised p-3 ${indent ? 'ml-6' : ''}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-text">{span.name}</span>
        <div className="flex items-center gap-2">
          <Chip tone={span.status === 'ok' ? 'success' : 'danger'}>{span.status}</Chip>
          <span className="text-xs text-text-dim">
            {span.duration_ms !== null ? `${span.duration_ms.toFixed(1)}ms` : '—'}
          </span>
        </div>
      </div>
      {attrEntries.length > 0 && (
        <dl className="mt-2 grid grid-cols-2 gap-1 text-xs text-text-dim">
          {attrEntries.map(([key, value]) => (
            <div key={key} className="truncate">
              <span className="text-text-dim/70">{key}:</span> {String(value)}
            </div>
          ))}
        </dl>
      )}
      {span.error && <p className="mt-2 text-xs text-danger">{span.error}</p>}
    </div>
  )
}

export function TracesPage() {
  const [searchParams] = useSearchParams()
  const [spans, setSpans] = useState<Span[] | null>(null)
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(() => searchParams.get('trace_id'))
  const [loading, setLoading] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      setSpans(await tracesApi.list(200))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  useEffect(() => {
    const traceId = searchParams.get('trace_id')
    if (traceId) setSelectedTraceId(traceId)
  }, [searchParams])

  const groups = groupSpansByTrace(spans ?? [])
  const selected = groups.find((g) => g.traceId === selectedTraceId) ?? groups[0] ?? null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text">Traces</h1>
        <Button variant="secondary" onClick={() => void refresh()} disabled={loading}>
          {loading ? <Spinner className="h-3 w-3" /> : 'Refresh'}
        </Button>
      </div>

      {spans === null ? (
        <p className="text-sm text-text-dim">Loading…</p>
      ) : groups.length === 0 ? (
        <p className="text-sm text-text-dim">
          No traces yet. Ask a question on the Chat page, then come back here.
        </p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <ul className="space-y-2">
            {groups.map((group) => (
              <li key={group.traceId}>
                <Card
                  className={`cursor-pointer ${selected?.traceId === group.traceId ? 'border-accent' : ''}`}
                  onClick={() => setSelectedTraceId(group.traceId)}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-text">{group.root.name}</span>
                    <Chip tone={group.root.status === 'ok' ? 'success' : 'danger'}>
                      {group.root.status}
                    </Chip>
                  </div>
                  <p className="mt-1 text-xs text-text-dim">
                    {formatTime(group.root.start_time)} · {group.children.length} child span
                    {group.children.length === 1 ? '' : 's'} · trace {group.traceId.slice(0, 8)}
                  </p>
                </Card>
              </li>
            ))}
          </ul>

          {selected && (
            <Card className="space-y-3">
              <p className="text-xs font-medium text-text-dim">
                Trace {selected.traceId} · started {formatTime(selected.root.start_time)}
              </p>
              <SpanRow span={selected.root} />
              {selected.children.map((child) => (
                <SpanRow key={child.span_id} span={child} indent />
              ))}
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
