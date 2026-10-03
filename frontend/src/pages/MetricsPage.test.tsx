import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MetricsPage } from './MetricsPage'

const { summary, raw } = vi.hoisted(() => ({
  summary: vi.fn(),
  raw: vi.fn(),
}))

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    metricsApi: { summary, raw },
  }
})

const FIXTURE = {
  generated_at: '2026-10-02T12:00:00+00:00',
  totals: { requests: 42, errors: 2, error_rate: 0.047619, client_errors: 0, p50_ms: 12.5, p95_ms: 88.1 },
  by_endpoint: [
    { method: 'GET', path: '/health', count: 40, error_count: 0, p50_ms: 1.2, p95_ms: 2.1 },
    { method: 'POST', path: '/structured/answer', count: 2, error_count: 2, p50_ms: 500, p95_ms: 900 },
  ],
  by_status: { '2xx': 40, '4xx': 0, '5xx': 2, by_code: { '200': 40, '500': 2 } },
  guardrails: {
    injection_blocks: 1,
    pii_redactions: 3,
    rate_limit_hits: 0,
    email_blocks: 0,
  },
  providers: [
    { provider: 'ollama', model: 'llama3', calls: 10, failures: 1, fallbacks: 1, avg_latency_ms: 120.4 },
  ],
  structured: { attempts_histogram: { '1': 8, '2': 2 }, retry_rate: 0.2, first_try_valid_pct: 80 },
  failed_runs: {
    total: 1,
    by_reason: { gateway_error: 1, invalid_output: 0, output_leak: 0, output_pii: 0 },
  },
  timeseries: Array.from({ length: 60 }, (_, i) => ({
    minute: `12:${String(i).padStart(2, '0')}`,
    requests: i % 3,
    errors: 0,
  })),
}

describe('MetricsPage', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('shows the summary dashboard by default', async () => {
    summary.mockResolvedValue(FIXTURE)
    render(<MetricsPage />)

    expect(await screen.findByText('42')).toBeInTheDocument()
    expect(screen.getByText('4.8%')).toBeInTheDocument()
    expect(screen.getByText('GET /health')).toBeInTheDocument()
    expect(screen.getByText('ollama')).toBeInTheDocument()
  })

  it('switches to the raw Prometheus tab without re-calling the summary endpoint', async () => {
    summary.mockResolvedValue(FIXTURE)
    raw.mockResolvedValue('structai_http_requests_total{method="GET"} 42\n')

    const user = userEvent.setup()
    render(<MetricsPage />)
    await screen.findByText('42')

    await user.click(screen.getByRole('button', { name: 'raw' }))

    expect(await screen.findByText('structai_http_requests_total')).toBeInTheDocument()
    expect(raw).toHaveBeenCalledTimes(1)
    expect(summary).toHaveBeenCalledTimes(1)
  })

  it('shows an error message when the summary request fails', async () => {
    summary.mockRejectedValue(new Error('boom'))
    render(<MetricsPage />)

    expect(await screen.findByText('boom')).toBeInTheDocument()
  })
})
