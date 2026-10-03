import { useEffect, useState } from 'react'
import { metricsApi } from '../lib/api'
import { parsePrometheusText } from '../lib/metrics'
import type { MetricFamily } from '../lib/metrics'
import type { MetricsSummaryResponse } from '../lib/types'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Spinner } from '../components/ui/Spinner'
import { MetricsSummaryTab } from '../components/metrics/MetricsSummaryTab'
import { MetricsSkeleton } from '../components/metrics/MetricsSkeleton'

const APP_METRIC_PREFIX = 'structai_'
const SUMMARY_POLL_MS = 10000

type Tab = 'summary' | 'raw'

function labelText(labels: Record<string, string>): string {
  const entries = Object.entries(labels)
  if (entries.length === 0) return '(no labels)'
  return entries.map(([k, v]) => `${k}=${v}`).join(', ')
}

function MetricCard({ family }: { family: MetricFamily }) {
  return (
    <Card>
      <p className="mb-2 font-mono text-sm font-medium text-text">{family.name}</p>
      <table className="w-full text-xs">
        <tbody>
          {family.samples.map((sample, i) => (
            <tr key={i} className="border-t border-border first:border-t-0">
              <td className="py-1.5 pr-3 text-text-dim">{labelText(sample.labels)}</td>
              <td className="py-1.5 text-right font-mono text-text">{sample.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function RawMetricsTab() {
  const [families, setFamilies] = useState<MetricFamily[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [showAll, setShowAll] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      setFamilies(parsePrometheusText(await metricsApi.raw()))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const visible = (families ?? []).filter(
    (f) => showAll || f.name.startsWith(APP_METRIC_PREFIX),
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-text-dim">
          Parsed client-side from the raw Prometheus text at <code>GET /metrics</code>.
        </p>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-sm text-text-dim">
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
            show process/runtime metrics
          </label>
          <Button variant="secondary" onClick={() => void refresh()} disabled={loading}>
            {loading ? <Spinner className="h-3 w-3" /> : 'Refresh'}
          </Button>
        </div>
      </div>

      {families === null ? (
        <p className="text-sm text-text-dim">Loading…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {visible.map((family) => (
            <MetricCard key={family.name} family={family} />
          ))}
        </div>
      )}
    </div>
  )
}

export function MetricsPage() {
  const [tab, setTab] = useState<Tab>('summary')
  const [summary, setSummary] = useState<MetricsSummaryResponse | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [summaryError, setSummaryError] = useState<string | null>(null)

  async function refreshSummary() {
    setSummaryLoading(true)
    try {
      setSummary(await metricsApi.summary())
      setSummaryError(null)
    } catch (err) {
      setSummaryError(err instanceof Error ? err.message : 'Failed to load metrics')
    } finally {
      setSummaryLoading(false)
    }
  }

  useEffect(() => {
    if (tab !== 'summary') return
    void refreshSummary()
    const interval = setInterval(() => void refreshSummary(), SUMMARY_POLL_MS)
    return () => clearInterval(interval)
  }, [tab])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text">Metrics</h1>
        <div className="inline-flex rounded-lg border border-border bg-surface p-1">
          {(['summary', 'raw'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`rounded-md px-3 py-1 text-sm font-medium capitalize transition-colors ${
                tab === t ? 'bg-accent/15 text-accent' : 'text-text-dim hover:text-text'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {tab === 'summary' ? (
        summary === null ? (
          summaryError ? (
            <p className="text-sm text-danger">{summaryError}</p>
          ) : (
            <MetricsSkeleton />
          )
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-text-dim">
              <span>
                Generated at {new Date(summary.generated_at).toLocaleTimeString()} · auto-refreshes
                every 10s
              </span>
              <Button variant="secondary" onClick={() => void refreshSummary()} disabled={summaryLoading}>
                {summaryLoading ? <Spinner className="h-3 w-3" /> : 'Refresh now'}
              </Button>
            </div>
            <MetricsSummaryTab summary={summary} />
          </div>
        )
      ) : (
        <RawMetricsTab />
      )}
    </div>
  )
}
