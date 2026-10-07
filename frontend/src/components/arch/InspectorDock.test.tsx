import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ArchGraphResponse, ArchLiveRunEvent, ArchLiveRunRequest } from '../../lib/types'
import { InspectorDock } from './InspectorDock'

const { getAccessToken, getRefreshToken, schemaValidate } = vi.hoisted(() => ({
  getAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
  schemaValidate: vi.fn(),
}))

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api')>('../../lib/api')
  return {
    ...actual,
    getAccessToken,
    getRefreshToken,
    schemaApi: { validate: schemaValidate },
  }
})

function base64Url(input: string): string {
  return btoa(input).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function makeJwt(payload: Record<string, unknown>): string {
  const header = base64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = base64Url(JSON.stringify(payload))
  return `${header}.${body}.fakesignature`
}

const ACCESS_TOKEN = makeJwt({
  sub: 'user-1',
  type: 'access',
  jti: 'jti-access',
  iat: 1000,
  exp: Math.floor(Date.now() / 1000) + 900,
})
const REFRESH_TOKEN = makeJwt({
  sub: 'user-1',
  type: 'refresh',
  jti: 'jti-refresh',
  iat: 1000,
  exp: Math.floor(Date.now() / 1000) + 86400,
})

const GRAPH: ArchGraphResponse = {
  nodes: [
    {
      id: 'jwt_auth',
      label: 'JWT Auth',
      kind: 'guardrail',
      group: 'auth_group',
      summary: 'Validates the bearer token.',
      contract: 'Rejects missing/expired/invalid tokens with 401.',
      code_path: 'app/core/security.py',
      icon: 'lock',
      visual_kind: 'tile',
      guardrails: [],
      telemetry: 'span: jwt_auth',
      status_key: null,
      tag: null,
      endpoints: [
        { method: 'POST', path: '/api/v1/arch/live-run', summary: '', auth_required: true, tags: [] },
      ],
      trace_spans: [],
      is_extra: false,
    },
    {
      id: 'router',
      label: 'Router',
      kind: 'gateway',
      group: 'gateway_group',
      summary: 'Picks a provider and calls it.',
      contract: 'Returns a successful completion or an aggregated error.',
      code_path: 'app/gateway/router.py',
      icon: 'route',
      visual_kind: 'tile',
      guardrails: [],
      telemetry: 'span: router',
      status_key: null,
      tag: null,
      endpoints: [],
      trace_spans: [],
      is_extra: false,
    },
  ],
  edges: [],
  groups: [],
  scenarios: [],
}

const EVENTS: ArchLiveRunEvent[] = [
  {
    node_id: 'jwt_auth',
    status: 'passed',
    latency_ms: 1.2,
    input_summary: 'token present',
    output_summary: 'valid',
    http_status: null,
    error_code: null,
    retry_after_seconds: null,
    trace_id: 'trace-1',
    span_id: 'span-1',
    data: null,
    provider: null,
    model: null,
    attempts: null,
    edge_ids: [],
  },
  {
    node_id: 'router',
    status: 'passed',
    latency_ms: 50,
    input_summary: 'routed',
    output_summary: 'ok',
    http_status: null,
    error_code: null,
    retry_after_seconds: null,
    trace_id: 'trace-1',
    span_id: 'span-2',
    data: null,
    provider: 'ollama',
    model: 'llama3',
    attempts: 1,
    edge_ids: [],
  },
  {
    node_id: 'output_guardrails',
    status: 'passed',
    latency_ms: 3,
    input_summary: null,
    output_summary: 'ok',
    http_status: null,
    error_code: null,
    retry_after_seconds: null,
    trace_id: 'trace-1',
    span_id: 'span-3',
    data: { title: 'hello' },
    provider: 'ollama',
    model: 'llama3',
    attempts: 1,
    edge_ids: [],
  },
]

const REQUEST_BODY: ArchLiveRunRequest = {
  prompt: 'say hi',
  schema_def: { fields: [{ name: 'title', type: 'string', description: '', required: true }] },
  tier: 'fast',
  provider: 'auto',
  model: null,
  strict_provider: false,
}

type DockProps = Parameters<typeof InspectorDock>[0]

function renderDock(overrides: Partial<DockProps> = {}) {
  const onActivateNode = vi.fn()
  const onHeightChange = vi.fn()
  const onCollapsedChange = vi.fn()
  const utils = render(
    <MemoryRouter>
      <InspectorDock
        collapsed={false}
        onCollapsedChange={onCollapsedChange}
        height={240}
        onHeightChange={onHeightChange}
        graph={GRAPH}
        events={[]}
        requestBody={null}
        onActivateNode={onActivateNode}
        {...overrides}
      />
    </MemoryRouter>,
  )
  return { ...utils, onActivateNode, onHeightChange, onCollapsedChange }
}

describe('InspectorDock', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getAccessToken.mockReturnValue(null)
    getRefreshToken.mockReturnValue(null)
    schemaValidate.mockResolvedValue({ valid: true, json_schema: {} })
  })

  it('renders a collapsed trigger when collapsed, instead of the tab bar', () => {
    renderDock({ collapsed: true })
    expect(screen.getByRole('button', { name: 'Expand Inspector' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Token' })).not.toBeInTheDocument()
  })

  it('TOKEN tab shows masked tokens and decoded claims, never the raw token', () => {
    getAccessToken.mockReturnValue(ACCESS_TOKEN)
    getRefreshToken.mockReturnValue(REFRESH_TOKEN)

    const { container } = renderDock()

    expect(screen.getByText('Access token')).toBeInTheDocument()
    expect(screen.getByText('Refresh token')).toBeInTheDocument()
    expect(container.textContent).toContain('"sub": "user-1"')
    expect(container.textContent).toContain('"type": "access"')
    expect(container.textContent).toContain('"type": "refresh"')
    expect(screen.getAllByText('Signature is never decoded or displayed.')).toHaveLength(2)

    expect(container.textContent).not.toContain(ACCESS_TOKEN)
    expect(container.textContent).not.toContain(REFRESH_TOKEN)
  })

  it('TOKEN tab shows an empty state when no token is present', () => {
    renderDock()
    expect(screen.getByText('No access token found in this browser.')).toBeInTheDocument()
    expect(screen.getByText('No refresh token found in this browser.')).toBeInTheDocument()
  })

  it('INPUT tab shows an empty state before any run', async () => {
    renderDock()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Input' }))
    expect(screen.getByText('Run a Live Run to see the exact request sent.')).toBeInTheDocument()
  })

  it('INPUT tab shows a masked cURL command, the request body, and the generated schema', async () => {
    getAccessToken.mockReturnValue(ACCESS_TOKEN)
    schemaValidate.mockResolvedValue({ valid: true, json_schema: { type: 'object' } })

    const { container } = renderDock({ requestBody: REQUEST_BODY })
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Input' }))

    expect(container.textContent).toContain('Authorization: Bearer <your-access-token>')
    expect(await screen.findByText('"object"')).toBeInTheDocument()
    expect(container.textContent).not.toContain(ACCESS_TOKEN)
  })

  it('STAGES tab lists each event and activates the node on click', async () => {
    const { onActivateNode } = renderDock({ events: EVENTS })
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Stages' }))

    expect(screen.getByText('jwt_auth')).toBeInTheDocument()
    expect(screen.getByText('router')).toBeInTheDocument()
    expect(screen.getByText('output_guardrails')).toBeInTheDocument()

    await user.click(screen.getByText('router'))
    expect(onActivateNode).toHaveBeenCalledWith('router')
  })

  it('STAGES tab shows an empty state before any run', async () => {
    renderDock()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Stages' }))
    expect(screen.getByText('Run a Live Run to see each pipeline stage here.')).toBeInTheDocument()
  })

  it('OUTPUT tab shows the final event, a trace link, and copy actions', async () => {
    renderDock({ events: EVENTS, requestBody: REQUEST_BODY })
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Output' }))

    expect(screen.getByText('Passed')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'view trace' })).toHaveAttribute(
      'href',
      '/app/traces?trace_id=trace-1',
    )
    expect(screen.getByRole('button', { name: 'Copy result JSON' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy as cURL' })).toBeInTheDocument()
  })

  it('OUTPUT tab shows an empty state before any run', async () => {
    renderDock()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Output' }))
    expect(screen.getByText('Run a Live Run to see its final output here.')).toBeInTheDocument()
  })

  it('API tab lists only the nodes touched by the run, derived from events', async () => {
    const { onActivateNode } = renderDock({ events: EVENTS })
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'API' }))

    expect(screen.getByText('JWT Auth')).toBeInTheDocument()
    expect(screen.getByText('Router')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Open' })[0])
    expect(onActivateNode).toHaveBeenCalledWith('jwt_auth')
  })

  it('API tab shows an empty-state pipeline description before any run', async () => {
    renderDock()
    await userEvent.setup().click(screen.getByRole('button', { name: 'API' }))
    expect(screen.getByText(/Run a Live Run to see which backend endpoints/)).toBeInTheDocument()
  })

  it('RAW tab renders the full collected event list as JSON', async () => {
    renderDock({ events: EVENTS })
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Raw' }))

    // each event renders as a collapsed entry (15 fields) until expanded
    expect(screen.getAllByText(/…15/)).toHaveLength(3)

    const [firstEventToggle] = screen.getAllByRole('button', { name: /\{/ })
    await user.click(firstEventToggle)
    expect(screen.getByText('"jwt_auth"')).toBeInTheDocument()
  })

  it('never renders a full unmasked token or signature on any tab', async () => {
    getAccessToken.mockReturnValue(ACCESS_TOKEN)
    getRefreshToken.mockReturnValue(REFRESH_TOKEN)
    schemaValidate.mockResolvedValue({ valid: true, json_schema: {} })

    const { container } = renderDock({ events: EVENTS, requestBody: REQUEST_BODY })
    const user = userEvent.setup()

    for (const label of ['Token', 'Input', 'Stages', 'Output', 'API', 'Raw']) {
      await user.click(screen.getByRole('button', { name: label }))
      expect(container.textContent).not.toContain(ACCESS_TOKEN)
      expect(container.textContent).not.toContain(REFRESH_TOKEN)
      expect(container.textContent).not.toContain('fakesignature')
    }
  })
})
