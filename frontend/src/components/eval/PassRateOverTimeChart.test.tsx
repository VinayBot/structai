import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EVAL_PALETTE } from '../../lib/evalTheme'
import type { EvalRunSummary } from '../../lib/types'
import { PassRateOverTimeChart } from './PassRateOverTimeChart'

function run(overrides: Partial<EvalRunSummary>): EvalRunSummary {
  return {
    id: 'run-1',
    provider: 'ollama',
    model: 'llama3',
    tier: 'free',
    source: 'api',
    created_at: '2026-10-01T12:00:00+00:00',
    total: 10,
    passed: 8,
    failed: 2,
    pass_rate: 0.8,
    avg_latency_ms: 120,
    p95_latency_ms: 200,
    avg_attempts: 1.2,
    ...overrides,
  }
}

describe('PassRateOverTimeChart', () => {
  it('shows an empty state with no history', () => {
    render(<PassRateOverTimeChart history={[]} palette={EVAL_PALETTE.dark} />)
    expect(screen.getByText('No runs yet')).toBeInTheDocument()
  })

  it('renders one line per provider without crashing', () => {
    const { container } = render(
      <PassRateOverTimeChart
        history={[
          run({ id: 'run-2', provider: 'groq', created_at: '2026-10-02T12:00:00+00:00' }),
          run({ id: 'run-1', provider: 'ollama', created_at: '2026-10-01T12:00:00+00:00' }),
        ]}
        palette={EVAL_PALETTE.dark}
      />,
    )
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
  })
})
