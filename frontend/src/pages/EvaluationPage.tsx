import type { ReactNode } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { evalApi, streamEvalRun } from '../lib/api'
import type {
  CaseResult,
  EvalCaseResultOut,
  EvalDashboardResponse,
  EvalProvider,
  EvalReport,
  EvalRunDetail,
  EvalRunSummary,
  GoldenCase,
} from '../lib/types'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Chip } from '../components/ui/Chip'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Spinner } from '../components/ui/Spinner'
import { CaseDetailDrawer } from '../components/eval/CaseDetailDrawer'
import { FirstTryGauge } from '../components/eval/FirstTryGauge'
import { GroupedLatencyBars } from '../components/eval/GroupedLatencyBars'
import { HeadToHeadTable } from '../components/eval/HeadToHeadTable'
import { LeaderboardCard } from '../components/eval/LeaderboardCard'
import { OutcomeDonut } from '../components/eval/OutcomeDonut'
import { PassRateOverTimeChart } from '../components/eval/PassRateOverTimeChart'
import { RadarCategoryChart } from '../components/eval/RadarCategoryChart'
import { EVAL_PALETTE, loadEvalTheme, saveEvalTheme, type EvalPalette, type EvalThemeMode } from '../lib/evalTheme'
import { formatMs } from '../lib/format'

function providerColor(provider: string, palette: EvalPalette): string {
  if (provider === 'ollama') return palette.primary
  if (provider === 'groq') return palette.secondary
  return palette.tertiary
}

function avgLatencyByCategory(results: EvalCaseResultOut[]): Record<string, number> {
  const sums: Record<string, { sum: number; n: number }> = {}
  for (const r of results) {
    const bucket = sums[r.category] ?? { sum: 0, n: 0 }
    bucket.sum += r.latency_ms
    bucket.n += 1
    sums[r.category] = bucket
  }
  const out: Record<string, number> = {}
  for (const [category, { sum, n }] of Object.entries(sums)) out[category] = sum / n
  return out
}

function latestRunIdByProvider(history: EvalRunSummary[]): Record<string, string> {
  const map: Record<string, string> = {}
  for (const run of history) {
    if (!(run.provider in map)) map[run.provider] = run.id
  }
  return map
}

function firstTryPassRate(detail: EvalRunDetail | undefined): number | null {
  if (!detail || detail.results.length === 0) return null
  const firstTry = detail.results.filter((r) => r.attempts === 1 && r.passed).length
  return firstTry / detail.results.length
}

interface DeltaDisplay {
  text: string
  tone: 'success' | 'danger' | 'neutral'
}

function formatDelta(
  value: number | undefined | null,
  opts: { suffix?: string; lowerIsBetter?: boolean; percentagePoints?: boolean } = {},
): DeltaDisplay {
  if (value === undefined || value === null || Number.isNaN(value)) return { text: 'n/a', tone: 'neutral' }
  const display = opts.percentagePoints ? value * 100 : value
  if (Math.abs(display) < 0.05) return { text: '±0', tone: 'neutral' }
  const improved = opts.lowerIsBetter ? display < 0 : display > 0
  const sign = display > 0 ? '+' : ''
  return { text: `${sign}${display.toFixed(1)}${opts.suffix ?? ''}`, tone: improved ? 'success' : 'danger' }
}

function reportToMarkdown(report: EvalReport): string {
  const lines = [
    '# Evaluation report',
    '',
    '| Metric | Value |',
    '| --- | --- |',
    `| Pass rate | ${(report.pass_rate * 100).toFixed(0)}% |`,
    `| Passed / total | ${report.passed} / ${report.total} |`,
    `| Avg latency | ${formatMs(report.avg_latency_ms)} |`,
    `| P95 latency | ${formatMs(report.p95_latency_ms)} |`,
    `| Avg attempts | ${report.avg_attempts.toFixed(2)} |`,
    `| Concurrency | ${report.concurrency} |`,
    '',
    '## By category',
    '',
    '| Category | Passed / total |',
    '| --- | --- |',
    ...Object.entries(report.by_category).map(([category, summary]) => `| ${category} | ${summary.passed} / ${summary.total} |`),
  ]
  return lines.join('\n')
}

function reportToCsv(report: EvalReport): string {
  const header = 'case_id,category,passed,provider,model,attempts,latency_ms,trace_id'
  const rows = report.results.map((r) =>
    [r.case_id, r.category, r.passed, r.provider ?? '', r.model ?? '', r.attempts ?? '', r.latency_ms, r.trace_id ?? ''].join(','),
  )
  return [header, ...rows].join('\n')
}

function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // clipboard access may be unavailable (e.g. insecure context); best-effort only
  }
}

export function EvaluationPage() {
  const [cases, setCases] = useState<GoldenCase[] | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [provider, setProvider] = useState<EvalProvider>('gateway')
  const [concurrency, setConcurrency] = useState(5)
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<CaseResult[]>([])
  const [report, setReport] = useState<EvalReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const [theme, setTheme] = useState<EvalThemeMode>(() => loadEvalTheme())
  const [dashboard, setDashboard] = useState<EvalDashboardResponse | null>(null)
  const [runDetails, setRunDetails] = useState<Record<string, EvalRunDetail>>({})
  const [drawerCaseId, setDrawerCaseId] = useState<string | null>(null)

  const palette = EVAL_PALETTE[theme]

  useEffect(() => {
    evalApi.cases().then((loaded) => {
      setCases(loaded)
      setSelected(new Set(loaded.map((c) => c.id)))
    })
  }, [])

  const refreshDashboard = useCallback(() => {
    evalApi.dashboard().then(setDashboard).catch(() => undefined)
  }, [])

  useEffect(() => {
    refreshDashboard()
  }, [refreshDashboard])

  useEffect(() => {
    saveEvalTheme(theme)
  }, [theme])

  useEffect(() => {
    if (!dashboard) return
    const ids = new Set(Object.values(latestRunIdByProvider(dashboard.history)))
    if (dashboard.latest) ids.add(dashboard.latest.id)
    const missing = [...ids].filter((id) => !(id in runDetails))
    if (missing.length === 0) return
    let cancelled = false
    Promise.all(missing.map((id) => evalApi.runDetail(id).then((detail) => [id, detail] as const)))
      .then((pairs) => {
        if (cancelled) return
        setRunDetails((prev) => {
          const next = { ...prev }
          for (const [id, detail] of pairs) next[id] = detail
          return next
        })
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [dashboard, runDetails])

  const total = cases?.length ?? 0
  const allSelected = selected.size === total && total > 0

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(cases?.map((c) => c.id) ?? []))
  }

  async function run() {
    setRunning(true)
    setResults([])
    setReport(null)
    setError(null)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      await streamEvalRun(
        {
          case_ids: cases && selected.size === cases.length ? null : [...selected],
          provider,
          concurrency,
        },
        (event) => {
          if (event.stage === 'case_done') {
            setResults((prev) => [...prev, event.result])
          } else {
            setReport(event.report)
          }
        },
        controller.signal,
      )
      refreshDashboard()
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : 'Evaluation run failed')
      }
    } finally {
      setRunning(false)
      abortRef.current = null
    }
  }

  function cancel() {
    abortRef.current?.abort()
  }

  const byCategory = useMemo(() => Object.entries(report?.by_category ?? {}), [report])

  const combinedSeries = useMemo(() => {
    if (!dashboard) return []
    const ids = latestRunIdByProvider(dashboard.history)
    return Object.entries(ids)
      .map(([prov, id]) => {
        const detail = runDetails[id]
        if (!detail) return null
        return {
          label: prov,
          color: providerColor(prov, palette),
          byCategory: detail.by_category,
          avgLatencyByCategory: avgLatencyByCategory(detail.results),
        }
      })
      .filter((s): s is NonNullable<typeof s> => s !== null)
  }, [dashboard, runDetails, palette])

  const latestDetail = dashboard?.latest ? runDetails[dashboard.latest.id] : undefined
  const firstTryRate = firstTryPassRate(latestDetail)

  const deltas = dashboard?.deltas
  const passRateDelta = formatDelta(deltas?.pass_rate_delta, { suffix: 'pp', percentagePoints: true })
  const avgLatencyDelta = formatDelta(deltas?.avg_latency_ms_delta, { suffix: 'ms', lowerIsBetter: true })
  const p95LatencyDelta = formatDelta(deltas?.p95_latency_ms_delta, { suffix: 'ms', lowerIsBetter: true })

  const drawerCase = cases?.find((c) => c.id === drawerCaseId) ?? null
  const drawerResult = results.find((r) => r.case_id === drawerCaseId) ?? null

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-text">Evaluation</h1>
      <p className="text-sm text-text-dim">
        Run the golden-case scenario suite against a live gateway and watch results stream in.
      </p>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-text-dim">
            Provider
            <Select
              value={provider}
              onChange={(e) => setProvider(e.target.value as EvalProvider)}
              disabled={running}
            >
              <option value="gateway">gateway (fallback chain)</option>
              <option value="ollama">ollama only</option>
              <option value="groq">groq only</option>
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-text-dim">
            Concurrency
            <Input
              type="number"
              min={1}
              max={20}
              value={concurrency}
              onChange={(e) => setConcurrency(Number(e.target.value))}
              disabled={running}
              className="w-24"
            />
          </label>
          <Button onClick={() => void run()} disabled={running || selected.size === 0}>
            {running ? <Spinner className="h-3 w-3" /> : `Run ${selected.size} case(s)`}
          </Button>
          {running && (
            <Button variant="secondary" onClick={cancel}>
              Cancel
            </Button>
          )}
        </div>
        {error && <p className="text-xs text-danger">{error}</p>}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-medium text-text">Golden cases</p>
          <label className="flex items-center gap-1.5 text-xs text-text-dim">
            <input type="checkbox" checked={allSelected} onChange={toggleAll} disabled={running} />
            select all
          </label>
        </div>
        {cases === null ? (
          <p className="text-sm text-text-dim">Loading…</p>
        ) : (
          <ul className="max-h-80 space-y-1 overflow-y-auto">
            {cases.map((c) => {
              const result = results.find((r) => r.case_id === c.id)
              return (
                <li
                  key={c.id}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-raised"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(c.id)}
                    onChange={() => toggle(c.id)}
                    disabled={running}
                  />
                  <button
                    type="button"
                    onClick={() => setDrawerCaseId(c.id)}
                    className="flex-1 truncate text-left text-xs text-text"
                  >
                    <span className="font-medium">{c.id}</span>{' '}
                    <span className="text-text-dim">· {c.category} · {c.prompt}</span>
                  </button>
                  {result && (
                    <>
                      <span className="text-xs text-text-dim">{formatMs(result.latency_ms)}</span>
                      <Chip tone={result.passed ? 'success' : 'danger'}>
                        {result.passed ? 'pass' : 'fail'}
                      </Chip>
                    </>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      {report && (
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-text">Report</p>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => void copyText(reportToMarkdown(report))}>
                Copy as Markdown
              </Button>
              <Button
                variant="secondary"
                onClick={() => downloadText(`eval-report-${report.started_at}.json`, JSON.stringify(report, null, 2), 'application/json')}
              >
                Export JSON
              </Button>
              <Button
                variant="secondary"
                onClick={() => downloadText(`eval-report-${report.started_at}.csv`, reportToCsv(report), 'text/csv')}
              >
                Export CSV
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Pass rate" value={`${(report.pass_rate * 100).toFixed(0)}%`} />
            <Stat label="Passed / total" value={`${report.passed} / ${report.total}`} />
            <Stat label="Avg latency" value={formatMs(report.avg_latency_ms)} />
            <Stat label="P95 latency" value={formatMs(report.p95_latency_ms)} />
            <Stat label="Avg attempts" value={report.avg_attempts.toFixed(2)} />
            <Stat label="Concurrency" value={String(report.concurrency)} />
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-text-dim">By category</p>
            <ul className="space-y-1">
              {byCategory.map(([category, summary]) => (
                <li key={category} className="flex items-center justify-between text-xs">
                  <span className="text-text">{category}</span>
                  <span className="text-text-dim">
                    {summary.passed} / {summary.total}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      )}

      <div data-eval-theme={theme} className="space-y-4 rounded-xl p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold" style={{ color: 'var(--eval-text)' }}>
            Dashboard
          </h2>
          <button
            type="button"
            onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
            className="eval-border rounded-full border px-3 py-1 text-xs"
            style={{ color: 'var(--eval-text)' }}
          >
            {theme === 'dark' ? '☾ Dark' : '☀ Light'}
          </button>
        </div>

        {dashboard && dashboard.history.length === 0 && (
          <div className="eval-card eval-card-raised flex flex-col items-center gap-3 py-10 text-center">
            <p className="text-sm font-medium" style={{ color: 'var(--eval-text)' }}>
              No evaluation runs yet
            </p>
            <p className="eval-text-dim text-xs">Run the golden-case suite above to populate this dashboard.</p>
            {/* Same action as the toolbar's "Run N case(s)" button above - deliberately
                different, static text. Both render at once whenever history is empty, and
                two buttons with an identical accessible name on one page is a real
                ambiguity (for assistive tech and for Playwright's getByRole alike), not
                just a test-matching inconvenience. */}
            <Button onClick={() => void run()} disabled={running || selected.size === 0}>
              Run now
            </Button>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <KpiCard
            label="Pass rate"
            value={dashboard?.latest ? `${(dashboard.latest.pass_rate * 100).toFixed(0)}%` : '—'}
            delta={dashboard?.latest ? passRateDelta : undefined}
          />
          <KpiCard
            label="Avg latency"
            value={dashboard?.latest ? formatMs(dashboard.latest.avg_latency_ms) : '—'}
            delta={dashboard?.latest ? avgLatencyDelta : undefined}
          />
          <KpiCard
            label="P95 latency"
            value={dashboard?.latest ? formatMs(dashboard.latest.p95_latency_ms) : '—'}
            delta={dashboard?.latest ? p95LatencyDelta : undefined}
          />
          <KpiCard
            label="Avg attempts"
            value={dashboard?.latest ? dashboard.latest.avg_attempts.toFixed(2) : '—'}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <EvalPanel title="Outcome" description="Pass vs fail split for the most recent run.">
            <OutcomeDonut passed={dashboard?.latest?.passed ?? 0} failed={dashboard?.latest?.failed ?? 0} palette={palette} />
          </EvalPanel>
          <EvalPanel title="First-try pass rate" description="Share of cases that passed with no retry.">
            <FirstTryGauge firstTryRate={firstTryRate} palette={palette} />
          </EvalPanel>
          <EvalPanel title="Pass rate over time" description="Pass rate of each run, per provider, oldest to newest.">
            <PassRateOverTimeChart history={dashboard?.history ?? []} palette={palette} />
          </EvalPanel>
          <EvalPanel title="Category coverage" description="Pass rate per category for the latest run of each provider.">
            <RadarCategoryChart series={combinedSeries} palette={palette} />
          </EvalPanel>
          <EvalPanel title="Latency by category" description="Average latency per category for the latest run of each provider.">
            <GroupedLatencyBars series={combinedSeries} palette={palette} />
          </EvalPanel>
          <EvalPanel title="Leaderboard" description="All-time average pass rate and latency per provider/model.">
            <LeaderboardCard entries={dashboard?.leaderboard ?? []} />
          </EvalPanel>
        </div>

        <EvalPanel title="Head-to-head" description="Pass rate and latency per category, side by side.">
          <HeadToHeadTable series={combinedSeries} />
        </EvalPanel>

        <div className="eval-card">
          <details>
            <summary className="cursor-pointer text-sm font-medium" style={{ color: 'var(--eval-text)' }}>
              How to read this dashboard
            </summary>
            <div className="eval-text-dim mt-3 space-y-2 text-xs">
              <p>
                <strong>Outcome</strong> — the pass/fail split of the most recent run.
              </p>
              <p>
                <strong>First-try pass rate</strong> — share of cases that passed on attempt 1, with no retry needed.
              </p>
              <p>
                <strong>Pass rate over time</strong> — each run&apos;s pass rate, one line per provider, oldest to newest.
              </p>
              <p>
                <strong>Category coverage</strong> — per-category pass rate for the latest run of each provider, overlaid.
              </p>
              <p>
                <strong>Latency by category</strong> — average latency per category for the latest run of each provider.
              </p>
              <p>
                <strong>Leaderboard</strong> — all-time average pass rate and latency, grouped by provider/model.
              </p>
              <p>
                <strong>Head-to-head</strong> — the same category data as a table, for side-by-side comparison.
              </p>
            </div>
          </details>
        </div>
      </div>

      <CaseDetailDrawer goldenCase={drawerCase} result={drawerResult} onClose={() => setDrawerCaseId(null)} />
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-raised p-3">
      <p className="text-xs text-text-dim">{label}</p>
      <p className="text-lg font-semibold text-text">{value}</p>
    </div>
  )
}

function KpiCard({ label, value, delta }: { label: string; value: string; delta?: DeltaDisplay }) {
  return (
    <div className="eval-card">
      <p className="eval-text-dim text-xs">{label}</p>
      <div className="flex items-baseline gap-2">
        <p className="text-lg font-semibold" style={{ color: 'var(--eval-text)' }}>
          {value}
        </p>
        {delta && <Chip tone={delta.tone}>{delta.text}</Chip>}
      </div>
    </div>
  )
}

function EvalPanel({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <div className="eval-card space-y-2">
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--eval-text)' }}>
          {title}
        </p>
        {description && <p className="eval-text-dim text-xs">{description}</p>}
      </div>
      {children}
    </div>
  )
}
