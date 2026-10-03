import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { LiveRunPanel } from './LiveRunPanel'

const { streamArchLiveRun, usageGet, schemaValidate } = vi.hoisted(() => ({
  streamArchLiveRun: vi.fn(),
  usageGet: vi.fn(),
  schemaValidate: vi.fn(),
}))

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api')>('../../lib/api')
  return {
    ...actual,
    getAccessToken: () => null,
    streamArchLiveRun,
    usageApi: { get: usageGet },
    schemaApi: { validate: schemaValidate },
  }
})

function noop() {}

async function fillAndRun(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText('Ask anything...'), 'hi')
  await user.type(screen.getByPlaceholderText('field_name'), 'answer')
  const runButton = screen.getByRole('button', { name: 'Run' })
  await waitFor(() => expect(runButton).toBeEnabled(), { timeout: 2000 })
  await user.click(runButton)
}

describe('LiveRunPanel error handling', () => {
  beforeEach(() => {
    schemaValidate.mockResolvedValue({ valid: true, json_schema: {} })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('shows a friendly message, a live countdown, and details for a 429', async () => {
    usageGet.mockResolvedValue({
      user_count_today: 1,
      user_limit: 10,
    })
    streamArchLiveRun.mockRejectedValue(new ApiError(429, 'rate_limited', 'slow down', 'req-1', 5))

    const user = userEvent.setup()
    render(<LiveRunPanel status={null} onStart={noop} onEvent={noop} onDone={noop} />)
    await fillAndRun(user)

    expect(await screen.findByText(/rate limit reached/i)).toBeInTheDocument()
    expect(screen.getByText(/try again in 5s/i)).toBeInTheDocument()

    await user.click(screen.getByText('Details'))
    expect(screen.getByText(/status: 429/)).toBeInTheDocument()
    expect(screen.getByText(/request id: req-1/)).toBeInTheDocument()
  })

  it('shows a generic connection message for a non-ApiError failure', async () => {
    usageGet.mockResolvedValue({
      user_count_today: 1,
      user_limit: 10,
    })
    streamArchLiveRun.mockRejectedValue(new TypeError('Failed to fetch'))

    const user = userEvent.setup()
    render(<LiveRunPanel status={null} onStart={noop} onEvent={noop} onDone={noop} />)
    await fillAndRun(user)

    expect(await screen.findByText(/could not reach the api/i)).toBeInTheDocument()
    expect(screen.queryByText('Details')).not.toBeInTheDocument()
  })

  it('maps a 401 to a session-expired message', async () => {
    usageGet.mockResolvedValue({
      user_count_today: 1,
      user_limit: 10,
    })
    streamArchLiveRun.mockRejectedValue(new ApiError(401, 'unauthorized', 'token invalid', null, null))

    const user = userEvent.setup()
    render(<LiveRunPanel status={null} onStart={noop} onEvent={noop} onDone={noop} />)
    await fillAndRun(user)

    expect(await screen.findByText(/session expired/i)).toBeInTheDocument()
    expect(screen.queryByText(/try again in/i)).not.toBeInTheDocument()
  })
})

describe('LiveRunPanel schema validate gating', () => {
  beforeEach(() => {
    usageGet.mockResolvedValue({
      user_count_today: 1,
      user_limit: 10,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('keeps Run disabled while schema validation is in flight, then enables it once valid', async () => {
    let resolveValidate: (value: { valid: boolean; json_schema: Record<string, unknown> }) => void = () => {}
    schemaValidate.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveValidate = resolve
        }),
    )

    const user = userEvent.setup()
    render(<LiveRunPanel status={null} onStart={noop} onEvent={noop} onDone={noop} />)
    await user.type(screen.getByPlaceholderText('Ask anything...'), 'hi')
    await user.type(screen.getByPlaceholderText('field_name'), 'answer')

    await waitFor(() => expect(schemaValidate).toHaveBeenCalled(), { timeout: 2000 })
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled()

    resolveValidate({ valid: true, json_schema: {} })

    await waitFor(() => expect(screen.getByRole('button', { name: 'Run' })).toBeEnabled(), { timeout: 2000 })
  })

  it('disables Run when schema validation reports the schema invalid', async () => {
    schemaValidate.mockResolvedValue({ valid: false, json_schema: {} })

    const user = userEvent.setup()
    render(<LiveRunPanel status={null} onStart={noop} onEvent={noop} onDone={noop} />)
    await user.type(screen.getByPlaceholderText('Ask anything...'), 'hi')
    await user.type(screen.getByPlaceholderText('field_name'), 'answer')

    await waitFor(() => expect(schemaValidate).toHaveBeenCalled(), { timeout: 2000 })
    await new Promise((r) => setTimeout(r, 50))
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled()
  })
})

describe('LiveRunPanel demo presets', () => {
  beforeEach(() => {
    schemaValidate.mockResolvedValue({ valid: true, json_schema: {} })
    usageGet.mockResolvedValue({
      user_count_today: 0,
      user_limit: 10,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('runs the demo attack preset against a scripted gateway and reports an injection block', async () => {
    streamArchLiveRun.mockImplementation(async (_body, onEvent) => {
      onEvent({
        node_id: 'injection_screen',
        status: 'failed',
        latency_ms: 2,
        input_summary: 'blocked',
        output_summary: 'prompt injection detected',
        http_status: 400,
        error_code: 'guardrail_blocked',
        retry_after_seconds: null,
        trace_id: null,
        span_id: null,
        data: null,
        provider: null,
        model: null,
        attempts: null,
      })
    })

    const user = userEvent.setup()
    render(<LiveRunPanel status={null} onStart={noop} onEvent={noop} onDone={noop} />)

    await user.click(screen.getByRole('button', { name: 'Demo: attack' }))

    await waitFor(() => expect(streamArchLiveRun).toHaveBeenCalled())
    const [body] = streamArchLiveRun.mock.calls[0]
    expect(body.prompt).toMatch(/ignore previous instructions/i)

    await waitFor(() => {
      expect(screen.getAllByText(/prompt injection detected/i).length).toBeGreaterThan(0)
    })
  })
})
