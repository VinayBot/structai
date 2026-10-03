import { useState } from 'react'
import type { MetricsSummaryResponse } from '../../lib/types'
import { Card } from '../ui/Card'
import { Chip } from '../ui/Chip'
import { JsonView } from '../ui/JsonView'
import { RequestsTimeseriesChart } from './RequestsTimeseriesChart'
import { StatusDonutChart } from './StatusDonutChart'

function StatCard({ label, value, tone = 'text' }: { label: string; value: string; tone?: 'text' | 'danger' }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-text-dim">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${tone === 'danger' ? 'text-danger' : 'text-text'}`}>
        {value}
      </p>
    </Card>
  )
}

function formatMs(ms: number): string {
  return `${ms.toFixed(1)}ms`
}

function formatPct(fraction: number): string {
  return `${(fraction * 100).toFixed(1)}%`
}

function GuardrailsPanel({ guardrails }: { guardrails: MetricsSummaryResponse['guardrails'] }) {
  const rows: Array<[string, number, 'warning' | 'danger']> = [
    ['Injection blocks', guardrails.injection_blocks, 'danger'],
    ['PII redactions', guardrails.pii_redactions, 'warning'],
    ['Rate limit hits', guardrails.rate_limit_hits, 'warning'],
    ['Email blocks', guardrails.email_blocks, 'warning'],
  ]
  return (
    <Card className="space-y-3">
      <p className="text-sm font-medium text-text">Guardrails</p>
      <div className="flex flex-wrap gap-2">
        {rows.map(([label, count, tone]) => (
          <Chip key={label} tone={count > 0 ? tone : 'neutral'}>
            {label}: {count}
          </Chip>
        ))}
      </div>
    </Card>
  )
}

const FAILURE_REASON_LABELS: Record<string, string> = {
  gateway_error: 'Gateway exhausted',
  invalid_output: 'Invalid output',
  output_leak: 'Output leak blocked',
  output_pii: 'Output PII blocked',
}

function FailedRunsPanel({ failedRuns }: { failedRuns: MetricsSummaryResponse['failed_runs'] }) {
  return (
    <Card className="space-y-3">
      <p className="text-sm font-medium text-text">Failed structured-answer runs</p>
      <p className="text-xs text-text-dim">
        Runs that never produced a usable result (model/guardrail outcome, not HTTP status —
        the chat UI's streaming endpoint always answers 200, so this is the real failure count).
      </p>
      <div className="flex flex-wrap gap-2">
        {Object.entries(failedRuns.by_reason).map(([reason, count]) => (
          <Chip key={reason} tone={count > 0 ? 'danger' : 'neutral'}>
            {FAILURE_REASON_LABELS[reason] ?? reason}: {count}
          </Chip>
        ))}
      </div>
    </Card>
  )
}

function EndpointsTable({ endpoints }: { endpoints: MetricsSummaryResponse['by_endpoint'] }) {
  if (endpoints.length === 0) {
    return <p className="text-sm text-text-dim">No requests recorded yet.</p>
  }
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-left text-text-dim">
          <th className="pb-2 pr-3 font-medium">Endpoint</th>
          <th className="pb-2 pr-3 font-medium text-right">Count</th>
          <th className="pb-2 pr-3 font-medium text-right">Errors</th>
          <th className="pb-2 pr-3 font-medium text-right">p50</th>
          <th className="pb-2 font-medium text-right">p95</th>
        </tr>
      </thead>
      <tbody>
        {endpoints
          .slice()
          .sort((a, b) => b.count - a.count)
          .map((e) => (
            <tr key={`${e.method} ${e.path}`} className="border-t border-border">
              <td className="py-1.5 pr-3 font-mono text-text">
                {e.method} {e.path}
              </td>
              <td className="py-1.5 pr-3 text-right text-text">{e.count}</td>
              <td className="py-1.5 pr-3 text-right">
                <span className={e.error_count > 0 ? 'text-danger' : 'text-text-dim'}>
                  {e.error_count}
                </span>
              </td>
              <td className="py-1.5 pr-3 text-right text-text-dim">{formatMs(e.p50_ms)}</td>
              <td className="py-1.5 text-right text-text-dim">{formatMs(e.p95_ms)}</td>
            </tr>
          ))}
      </tbody>
    </table>
  )
}

function ProvidersTable({ providers }: { providers: MetricsSummaryResponse['providers'] }) {
  if (providers.length === 0) {
    return <p className="text-sm text-text-dim">No gateway calls recorded yet.</p>
  }
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-left text-text-dim">
          <th className="pb-2 pr-3 font-medium">Provider</th>
          <th className="pb-2 pr-3 font-medium">Model</th>
          <th className="pb-2 pr-3 font-medium text-right">Calls</th>
          <th className="pb-2 pr-3 font-medium text-right">Failures</th>
          <th className="pb-2 pr-3 font-medium text-right">Fallbacks</th>
          <th className="pb-2 font-medium text-right">Avg latency</th>
        </tr>
      </thead>
      <tbody>
        {providers.map((p) => (
          <tr key={`${p.provider} ${p.model}`} className="border-t border-border">
            <td className="py-1.5 pr-3 text-text">{p.provider}</td>
            <td className="py-1.5 pr-3 font-mono text-text-dim">{p.model}</td>
            <td className="py-1.5 pr-3 text-right text-text">{p.calls}</td>
            <td className="py-1.5 pr-3 text-right">
              <span className={p.failures > 0 ? 'text-danger' : 'text-text-dim'}>{p.failures}</span>
            </td>
            <td className="py-1.5 pr-3 text-right">
              <span className={p.fallbacks > 0 ? 'text-warning' : 'text-text-dim'}>{p.fallbacks}</span>
            </td>
            <td className="py-1.5 text-right text-text-dim">{formatMs(p.avg_latency_ms)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function StructuredPanel({ structured }: { structured: MetricsSummaryResponse['structured'] }) {
  const buckets = Object.entries(structured.attempts_histogram)
  const maxCount = Math.max(1, ...buckets.map(([, count]) => count))
  return (
    <Card className="space-y-3">
      <p className="text-sm font-medium text-text">Structured answer attempts</p>
      <div className="flex gap-6 text-xs text-text-dim">
        <span>
          Retry rate: <span className="text-text">{formatPct(structured.retry_rate)}</span>
        </span>
        <span>
          First-try valid: <span className="text-text">{formatPct(structured.first_try_valid_pct / 100)}</span>
        </span>
      </div>
      {buckets.length === 0 ? (
        <p className="text-xs text-text-dim">No structured calls recorded yet.</p>
      ) : (
        <div className="space-y-1.5">
          {buckets.map(([attempts, count]) => (
            <div key={attempts} className="flex items-center gap-2 text-xs">
              <span className="w-10 shrink-0 text-text-dim">{attempts} try</span>
              <div className="h-3 flex-1 overflow-hidden rounded bg-surface-raised">
                <div
                  className="h-full rounded bg-accent"
                  style={{ width: `${(count / maxCount) * 100}%` }}
                />
              </div>
              <span className="w-6 shrink-0 text-right text-text-dim">{count}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

export function MetricsSummaryTab({ summary }: { summary: MetricsSummaryResponse }) {
  const [showRawJson, setShowRawJson] = useState(false)
  const { totals, by_status, by_endpoint, guardrails, providers, structured, failed_runs, timeseries } = summary

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Requests" value={String(totals.requests)} />
        <StatCard label="Server errors" value={String(totals.errors)} tone={totals.errors > 0 ? 'danger' : 'text'} />
        <StatCard label="Error rate" value={formatPct(totals.error_rate)} tone={totals.error_rate > 0 ? 'danger' : 'text'} />
        <StatCard label="Failed runs" value={String(failed_runs.total)} tone={failed_runs.total > 0 ? 'danger' : 'text'} />
        <StatCard label="p50 latency" value={formatMs(totals.p50_ms)} />
        <StatCard label="p95 latency" value={formatMs(totals.p95_ms)} />
      </div>

      <Card>
        <p className="mb-3 text-sm font-medium text-text">Requests &amp; errors — last 60 minutes</p>
        <RequestsTimeseriesChart points={timeseries} />
      </Card>

      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card>
          <p className="mb-1 text-sm font-medium text-text">Status breakdown</p>
          <StatusDonutChart byStatus={by_status} />
          <div className="flex flex-wrap justify-center gap-2">
            <Chip tone={totals.client_errors > 0 ? 'warning' : 'neutral'}>
              Client errors (4xx): {totals.client_errors}
            </Chip>
            {Object.entries(by_status.by_code).map(([code, count]) => (
              <Chip key={code} tone={code.startsWith('2') ? 'success' : code.startsWith('4') ? 'warning' : 'danger'}>
                {code}: {count}
              </Chip>
            ))}
          </div>
        </Card>
        <GuardrailsPanel guardrails={guardrails} />
      </div>

      <Card>
        <p className="mb-3 text-sm font-medium text-text">By endpoint</p>
        <EndpointsTable endpoints={by_endpoint} />
      </Card>

      <Card>
        <p className="mb-3 text-sm font-medium text-text">Gateway providers</p>
        <ProvidersTable providers={providers} />
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <StructuredPanel structured={structured} />
        <FailedRunsPanel failedRuns={failed_runs} />
      </div>

      <Card>
        <button
          type="button"
          onClick={() => setShowRawJson((v) => !v)}
          className="text-sm font-medium text-text-dim hover:text-text"
        >
          {showRawJson ? '▾' : '▸'} Raw JSON
        </button>
        {showRawJson && (
          <div className="mt-3">
            <JsonView data={summary} defaultExpanded />
          </div>
        )}
      </Card>
    </div>
  )
}
