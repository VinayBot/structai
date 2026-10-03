import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EvaluationPage } from './EvaluationPage'
import type { EvalDashboardResponse, EvalRunDetail, GoldenCase } from '../lib/types'
import { EVAL_THEME_STORAGE_KEY } from '../lib/evalTheme'

const { cases, dashboard, runDetail } = vi.hoisted(() => ({
  cases: vi.fn(),
  dashboard: vi.fn(),
  runDetail: vi.fn(),
}))

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    evalApi: { ...actual.evalApi, cases, dashboard, runDetail },
  }
})

const CASES_FIXTURE: GoldenCase[] = [
  { id: 'c1', category: 'structured', prompt: 'Extract the invoice total', schema_def: { fields: [] }, tier: 'fast', checks: [] },
]

const DASHBOARD_FIXTURE: EvalDashboardResponse = {
  latest: {
    id: 'run-2',
    provider: 'ollama',
    model: 'llama3',
    tier: 'fast',
    source: 'api',
    created_at: '2026-10-02T12:00:00+00:00',
    total: 10,
    passed: 8,
    failed: 2,
    pass_rate: 0.8,
    avg_latency_ms: 120.5,
    p95_latency_ms: 200.1,
    avg_attempts: 1.2,
  },
  history: [
    {
      id: 'run-2',
      provider: 'ollama',
      model: 'llama3',
      tier: 'fast',
      source: 'api',
      created_at: '2026-10-02T12:00:00+00:00',
      total: 10,
      passed: 8,
      failed: 2,
      pass_rate: 0.8,
      avg_latency_ms: 120.5,
      p95_latency_ms: 200.1,
      avg_attempts: 1.2,
    },
    {
      id: 'run-1',
      provider: 'ollama',
      model: 'llama3',
      tier: 'fast',
      source: 'api',
      created_at: '2026-10-01T12:00:00+00:00',
      total: 10,
      passed: 6,
      failed: 4,
      pass_rate: 0.6,
      avg_latency_ms: 140,
      p95_latency_ms: 220,
      avg_attempts: 1.5,
    },
  ],
  leaderboard: [{ provider: 'ollama', model: 'llama3', runs: 2, avg_pass_rate: 0.7, avg_latency_ms: 130.25 }],
  deltas: { pass_rate_delta: 0.2, avg_latency_ms_delta: -19.5, p95_latency_ms_delta: -19.9 },
}

const RUN_DETAIL_FIXTURE: EvalRunDetail = {
  ...DASHBOARD_FIXTURE.history[0],
  by_category: { structured: { total: 10, passed: 8 } },
  results: [
    {
      case_id: 'c1',
      category: 'structured',
      prompt: 'Extract the invoice total',
      schema_def: { fields: [] },
      passed: true,
      reason: null,
      provider: 'ollama',
      model: 'llama3',
      attempts: 1,
      latency_ms: 100,
      data: { total: 42 },
      trace_id: 't1',
    },
  ],
}

describe('EvaluationPage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders KPI cards using the server-computed deltas', async () => {
    cases.mockResolvedValue(CASES_FIXTURE)
    dashboard.mockResolvedValue(DASHBOARD_FIXTURE)
    runDetail.mockResolvedValue(RUN_DETAIL_FIXTURE)

    render(<EvaluationPage />)

    expect((await screen.findAllByText('80%')).length).toBeGreaterThan(0)
    expect(screen.getByText('+20.0pp')).toBeInTheDocument()
    expect(screen.getByText('120.5ms')).toBeInTheDocument()
    expect(screen.getByText('-19.5ms')).toBeInTheDocument()
  })

  it('shows the empty-state call-to-action when there are no runs yet', async () => {
    cases.mockResolvedValue(CASES_FIXTURE)
    dashboard.mockResolvedValue({ latest: null, history: [], leaderboard: [], deltas: null })
    runDetail.mockResolvedValue(RUN_DETAIL_FIXTURE)

    render(<EvaluationPage />)

    expect(await screen.findByText('No evaluation runs yet')).toBeInTheDocument()
  })

  it('toggles the eval theme and persists the choice to localStorage', async () => {
    cases.mockResolvedValue(CASES_FIXTURE)
    dashboard.mockResolvedValue(DASHBOARD_FIXTURE)
    runDetail.mockResolvedValue(RUN_DETAIL_FIXTURE)

    const user = userEvent.setup()
    const { container } = render(<EvaluationPage />)
    await screen.findAllByText('80%')

    const themedDiv = container.querySelector('[data-eval-theme]')
    expect(themedDiv).toHaveAttribute('data-eval-theme', 'dark')

    await user.click(screen.getByRole('button', { name: /dark/i }))

    expect(themedDiv).toHaveAttribute('data-eval-theme', 'light')
    expect(localStorage.getItem(EVAL_THEME_STORAGE_KEY)).toBe('light')
  })
})
