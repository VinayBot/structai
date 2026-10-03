import { describe, expect, it } from 'vitest'
import { decodeJwt, isTokenNearExpiry, maskToken } from './jwt'

function base64UrlEncode(obj: unknown): string {
  const json = JSON.stringify(obj)
  const base64 = btoa(json)
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function makeToken(payload: Record<string, unknown>): string {
  const header = base64UrlEncode({ alg: 'HS256', typ: 'JWT' })
  const body = base64UrlEncode(payload)
  return `${header}.${body}.fake-signature`
}

describe('decodeJwt', () => {
  it('decodes a well-formed token payload', () => {
    const token = makeToken({ sub: 'user-1', exp: 1234567890 })
    expect(decodeJwt(token)).toEqual({ sub: 'user-1', exp: 1234567890 })
  })

  it('returns null for a token with the wrong number of segments', () => {
    expect(decodeJwt('not-a-jwt')).toBeNull()
    expect(decodeJwt('a.b')).toBeNull()
  })

  it('returns null when the payload segment is not valid base64/JSON', () => {
    expect(decodeJwt('a.not-valid-base64!!!.c')).toBeNull()
  })
})

describe('isTokenNearExpiry', () => {
  it('is true when exp is in the past', () => {
    const token = makeToken({ exp: Date.now() / 1000 - 100 })
    expect(isTokenNearExpiry(token)).toBe(true)
  })

  it('is true when exp is within the default 60s threshold', () => {
    const token = makeToken({ exp: Date.now() / 1000 + 30 })
    expect(isTokenNearExpiry(token)).toBe(true)
  })

  it('is false when exp is well beyond the threshold', () => {
    const token = makeToken({ exp: Date.now() / 1000 + 3600 })
    expect(isTokenNearExpiry(token)).toBe(false)
  })

  it('respects a custom threshold', () => {
    const token = makeToken({ exp: Date.now() / 1000 + 120 })
    expect(isTokenNearExpiry(token, 60)).toBe(false)
    expect(isTokenNearExpiry(token, 180)).toBe(true)
  })

  it('is false for an undecodable token', () => {
    expect(isTokenNearExpiry('garbage')).toBe(false)
  })

  it('is false when the payload has no exp field', () => {
    const token = makeToken({ sub: 'user-1' })
    expect(isTokenNearExpiry(token)).toBe(false)
  })
})

describe('maskToken', () => {
  it('leaves short tokens untouched', () => {
    expect(maskToken('short')).toBe('short')
  })

  it('masks the middle of a long token', () => {
    const token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEifQ.signature-bytes-here'
    const masked = maskToken(token)
    expect(masked.startsWith('eyJhbGci')).toBe(true)
    expect(masked.endsWith('tes-here')).toBe(true)
    expect(masked).toContain('…')
    expect(masked.length).toBeLessThan(token.length)
  })
})
