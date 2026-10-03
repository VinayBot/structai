import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, clearTokens, getAccessToken, setTokens } from './api'

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

function sseResponse(lines: string[]) {
  const bytes = new TextEncoder().encode(lines.join(''))
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(bytes)
      controller.close()
    },
  })
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

function makeExpiredToken(): string {
  const payload = { sub: 'user-1', exp: Date.now() / 1000 - 100 }
  const b64 = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${b64({ alg: 'HS256' })}.${b64(payload)}.sig`
}

describe('api.ts auth-refresh behavior', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('request() retries once after a 401 by refreshing, then succeeds', async () => {
    setTokens({ access_token: 'stale-token', refresh_token: 'refresh-1', token_type: 'bearer' })

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'unauthorized', message: 'x', request_id: null } }))
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: 'fresh-token', refresh_token: 'refresh-2', token_type: 'bearer' }),
      )
      .mockResolvedValueOnce(jsonResponse(200, { id: 'user-1', email: 'a@b.com' }))
    vi.stubGlobal('fetch', fetchMock)

    const { authApi } = await import('./api')
    const user = await authApi.me()

    expect(user).toEqual({ id: 'user-1', email: 'a@b.com' })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(getAccessToken()).toBe('fresh-token')
  })

  it('request() clears tokens and throws when refresh itself fails', async () => {
    setTokens({ access_token: 'stale-token', refresh_token: 'refresh-1', token_type: 'bearer' })

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'unauthorized', message: 'x', request_id: null } }))
      .mockResolvedValueOnce(
        jsonResponse(401, { error: { code: 'unauthorized', message: 'bad refresh', request_id: null } }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const { authApi } = await import('./api')
    await expect(authApi.me()).rejects.toBeInstanceOf(ApiError)
    expect(getAccessToken()).toBeNull()
  })

  it('parseError carries retry_after_seconds from the response body', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(429, {
          error: { code: 'rate_limited', message: 'slow down', request_id: 'r1', retry_after_seconds: 12.5 },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const { usageApi } = await import('./api')
    const err = await usageApi.get().catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).retryAfterSeconds).toBe(12.5)
    expect((err as ApiError).status).toBe(429)
  })

  it('streamSse retries once after a 401 by refreshing, then streams events', async () => {
    setTokens({ access_token: 'stale-token', refresh_token: 'refresh-1', token_type: 'bearer' })

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'unauthorized', message: 'x', request_id: null } }))
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: 'fresh-token', refresh_token: 'refresh-2', token_type: 'bearer' }),
      )
      .mockResolvedValueOnce(sseResponse(['data: {"stage":"done"}\n\n']))
    vi.stubGlobal('fetch', fetchMock)

    const { streamStructuredAnswer } = await import('./api')
    const events: unknown[] = []
    await streamStructuredAnswer(
      'hi',
      { fields: [{ name: 'title', type: 'string', description: '', required: true }] },
      'fast',
      (e) => events.push(e),
    )

    expect(events).toEqual([{ stage: 'done' }])
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('streamSse proactively refreshes a near-expiry token before opening the connection', async () => {
    setTokens({ access_token: makeExpiredToken(), refresh_token: 'refresh-1', token_type: 'bearer' })

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: 'fresh-token', refresh_token: 'refresh-2', token_type: 'bearer' }),
      )
      .mockResolvedValueOnce(sseResponse(['data: {"stage":"done"}\n\n']))
    vi.stubGlobal('fetch', fetchMock)

    const { streamStructuredAnswer } = await import('./api')
    const events: unknown[] = []
    await streamStructuredAnswer(
      'hi',
      { fields: [{ name: 'title', type: 'string', description: '', required: true }] },
      'fast',
      (e) => events.push(e),
    )

    expect(events).toEqual([{ stage: 'done' }])
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const streamCall = fetchMock.mock.calls[1]
    const streamHeaders = streamCall[1].headers as Record<string, string>
    expect(streamHeaders.Authorization).toBe('Bearer fresh-token')
  })
})

describe('clearTokens', () => {
  it('removes both tokens', () => {
    setTokens({ access_token: 'a', refresh_token: 'b', token_type: 'bearer' })
    clearTokens()
    expect(getAccessToken()).toBeNull()
  })
})
