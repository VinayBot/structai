import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { archApi, getAccessToken } from '../../lib/api'
import type { ArchScenarioId, ArchScenarioInfo, ArchScenarioStep, ArchTestRunResponse } from '../../lib/types'
import { formatMs } from '../../lib/format'
import { Button } from '../ui/Button'
import { Select } from '../ui/Select'
import { Spinner } from '../ui/Spinner'
import { Chip } from '../ui/Chip'

const STEP_DELAY_MS = 450

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function buildTestRunCurl(scenarioId: ArchScenarioId): string {
  const origin = window.location.origin
  const hasToken = Boolean(getAccessToken())
  const lines = [
    `curl -X POST "${origin}/arch/test-run" \\`,
    `  -H "Authorization: Bearer ${hasToken ? '<your-access-token>' : '<access-token>'}" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '${JSON.stringify({ scenario_id: scenarioId })}'`,
  ]
  return lines.join('\n')
}

interface ScenarioRunnerProps {
  scenarios: ArchScenarioInfo[]
  onStart: () => void
  onStep: (step: ArchScenarioStep) => void
  onDone: (result: ArchTestRunResponse) => void
}

export function ScenarioRunner({ scenarios, onStart, onStep, onDone }: ScenarioRunnerProps) {
  const [activeId, setActiveId] = useState<ArchScenarioId | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<ArchTestRunResponse | null>(null)
  const [visibleSteps, setVisibleSteps] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    return () => {
      cancelledRef.current = true
    }
  }, [])

  async function run(scenarioId: ArchScenarioId) {
    if (running) return
    cancelledRef.current = false
    setActiveId(scenarioId)
    setRunning(true)
    setError(null)
    setResult(null)
    setVisibleSteps(0)
    onStart()

    try {
      const response = await archApi.testRun(scenarioId)
      if (cancelledRef.current) return
      setResult(response)

      for (let i = 0; i < response.steps.length; i += 1) {
        if (cancelledRef.current) return
        const step = response.steps[i]
        onStep(step)
        setVisibleSteps(i + 1)
        await sleep(STEP_DELAY_MS)
      }
      if (!cancelledRef.current) onDone(response)
    } catch {
      if (!cancelledRef.current) setError('Scenario run failed - check the API connection.')
    } finally {
      if (!cancelledRef.current) setRunning(false)
    }
  }

  async function copyText(key: string, text: string) {
    await navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 1500)
  }

  const primary = scenarios.filter((s) => s.primary)
  const more = scenarios.filter((s) => !s.primary)
  const activeInfo = scenarios.find((s) => s.id === activeId) ?? null

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
      <div className="flex flex-wrap gap-1.5">
        {primary.map((s) => (
          <Button
            key={s.id}
            variant={activeId === s.id ? 'primary' : 'secondary'}
            disabled={running}
            onClick={() => void run(s.id)}
            className="px-2.5 py-1.5 text-xs"
          >
            {running && activeId === s.id && <Spinner />}
            {s.label}
          </Button>
        ))}
      </div>

      {more.length > 0 && (
        <Select
          value=""
          disabled={running}
          aria-label="More scenarios"
          onChange={(e) => {
            const id = e.target.value as ArchScenarioId
            if (id) void run(id)
          }}
        >
          <option value="">More scenarios...</option>
          {more.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </Select>
      )}

      {activeInfo && <p className="text-xs text-text-dim">What this tests: {activeInfo.description}</p>}

      {error && <p className="text-xs text-danger">{error}</p>}

      {result && (
        <div className="flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone={result.passed ? 'success' : 'danger'}>{result.passed ? 'Passed' : 'Failed'}</Chip>
            <Chip tone={result.badge === 'real_call' ? 'accent' : 'warning'}>
              {result.badge === 'real_call' ? 'Real call' : 'Fault injection'}
            </Chip>
            <span className="text-xs text-text-dim">{formatMs(result.total_duration_ms)} total</span>
          </div>
          <p className="text-xs text-text-dim">{result.summary}</p>

          <div className="flex flex-wrap gap-1.5">
            <Button
              variant="secondary"
              className="px-2 py-1 text-xs"
              onClick={() => activeId && void copyText('curl', buildTestRunCurl(activeId))}
            >
              {copiedKey === 'curl' ? 'Copied!' : 'Copy as cURL'}
            </Button>
            <Button
              variant="secondary"
              className="px-2 py-1 text-xs"
              onClick={() => void copyText('result', JSON.stringify(result, null, 2))}
            >
              {copiedKey === 'result' ? 'Copied!' : 'Copy result JSON'}
            </Button>
            <Button
              variant="secondary"
              className="px-2 py-1 text-xs"
              disabled={running}
              onClick={() => activeId && void run(activeId)}
            >
              Re-run
            </Button>
          </div>

          <ol className="space-y-1.5">
            <AnimatePresence>
              {result.steps.slice(0, visibleSteps).map((step, idx) => (
                <motion.li
                  key={`${step.node_id}-${idx}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex items-start gap-2 rounded-lg bg-bg p-2 text-xs"
                >
                  <Chip
                    tone={
                      step.status === 'ok'
                        ? 'success'
                        : step.status === 'error'
                          ? 'danger'
                          : 'neutral'
                    }
                  >
                    {idx + 1}
                  </Chip>
                  <div className="min-w-0 flex-1">
                    <p className="text-text">{step.label}</p>
                    <p className="text-text-dim">{step.detail}</p>
                    {step.http_status && (
                      <p className="text-text-dim">
                        {step.http_status} {step.error_code}
                      </p>
                    )}
                    {(step.request || step.response) && (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-accent">Request / response</summary>
                        <div className="mt-1 space-y-1.5">
                          {step.request && (
                            <div>
                              <p className="text-text-dim">Request</p>
                              <pre className="whitespace-pre-wrap break-words rounded-lg bg-surface p-2 text-text-dim">
                                {JSON.stringify(step.request, null, 2)}
                              </pre>
                            </div>
                          )}
                          {step.response && (
                            <div>
                              <p className="text-text-dim">Response</p>
                              <pre className="whitespace-pre-wrap break-words rounded-lg bg-surface p-2 text-text-dim">
                                {JSON.stringify(step.response, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                  <span className="shrink-0 text-text-dim">{formatMs(step.duration_ms)}</span>
                </motion.li>
              ))}
            </AnimatePresence>
          </ol>

          {visibleSteps >= result.steps.length && (
            <>
              {result.assertions.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-text-dim">Assertions</p>
                  <ul className="space-y-1">
                    {result.assertions.map((a, idx) => (
                      <li key={idx} className="rounded-lg bg-bg p-2 text-xs">
                        <div className="flex items-start gap-1.5">
                          <span className={a.passed ? 'text-success' : 'text-danger'}>
                            {a.passed ? '✓' : '✗'}
                          </span>
                          <span className="text-text">{a.name}</span>
                        </div>
                        <p className="pl-4 text-text-dim">expected: {a.expected}</p>
                        <p className="pl-4 text-text-dim">actual: {a.actual}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="space-y-1">
                <p className="text-xs font-semibold text-text-dim">Contract check</p>
                <div className="rounded-lg bg-bg p-2 text-xs">
                  <div className="flex items-center gap-1.5">
                    <span className={result.contract.valid ? 'text-success' : 'text-danger'}>
                      {result.contract.valid ? '✓' : '✗'}
                    </span>
                    <span className="text-text">
                      {result.contract.valid
                        ? 'Response matches the real Pydantic model'
                        : 'Response does not match the real Pydantic model'}
                    </span>
                  </div>
                  {result.contract.errors.length > 0 && (
                    <ul className="mt-1 space-y-0.5 pl-4 text-danger">
                      {result.contract.errors.map((e, idx) => (
                        <li key={idx}>{e}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
