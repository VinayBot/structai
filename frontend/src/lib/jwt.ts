export interface JwtPayload {
  sub?: string
  exp?: number
  iat?: number
  [key: string]: unknown
}

function base64UrlDecode(input: string): string {
  const normalized = input.replace(/-/g, '+').replace(/_/g, '/')
  const padLength = (4 - (normalized.length % 4)) % 4
  return atob(normalized + '='.repeat(padLength))
}

export function decodeJwt(token: string): JwtPayload | null {
  const parts = token.split('.')
  if (parts.length !== 3) return null
  try {
    const json = base64UrlDecode(parts[1])
    return JSON.parse(json) as JwtPayload
  } catch {
    return null
  }
}

export function isTokenNearExpiry(token: string, thresholdSeconds = 60): boolean {
  const payload = decodeJwt(token)
  if (!payload || typeof payload.exp !== 'number') return false
  const nowSeconds = Date.now() / 1000
  return payload.exp - nowSeconds <= thresholdSeconds
}

export function maskToken(token: string): string {
  if (token.length <= 16) return token
  return `${token.slice(0, 8)}…${token.slice(-8)}`
}
