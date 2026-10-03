import { randomUUID } from 'node:crypto'
import { expect, type Page } from '@playwright/test'

const ACCESS_TOKEN_KEY = 'structai_access_token'
const REFRESH_TOKEN_KEY = 'structai_refresh_token'

/**
 * Attaches console/network listeners before any navigation. Call `assertHealthy()`
 * at the end of a test to fail it if anything logged a console error or any request
 * failed outright (DNS/abort/etc - not merely a non-2xx HTTP response).
 */
export function watchPageHealth(page: Page) {
  const consoleErrors: string[] = []
  const failedRequests: string[] = []

  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.method()} ${request.url()} :: ${request.failure()?.errorText ?? 'unknown'}`)
  })

  return {
    assertHealthy() {
      expect(consoleErrors, `unexpected console errors:\n${consoleErrors.join('\n')}`).toEqual([])
      expect(failedRequests, `unexpected failed requests:\n${failedRequests.join('\n')}`).toEqual([])
    },
  }
}

export interface SeededSession {
  email: string
  password: string
  accessToken: string
  refreshToken: string
}

/**
 * Registers + logs in a fresh user over the real API (bypassing the login UI) and
 * pre-seeds localStorage via addInitScript, so the test's first page.goto() lands
 * already authenticated. Must be called before that first goto().
 */
export async function seedAuthedSession(page: Page): Promise<SeededSession> {
  const email = `e2e-${randomUUID()}@example.com`
  const password = 'password1'

  const registerResp = await page.request.post('/auth/register', {
    data: { email, password },
  })
  if (!registerResp.ok()) {
    throw new Error(`register failed: ${registerResp.status()} ${await registerResp.text()}`)
  }

  const loginResp = await page.request.post('/auth/login', {
    data: { email, password },
  })
  if (!loginResp.ok()) {
    throw new Error(`login failed: ${loginResp.status()} ${await loginResp.text()}`)
  }
  const tokens = (await loginResp.json()) as { access_token: string; refresh_token: string }

  await page.addInitScript(
    (seed: { accessToken: string; refreshToken: string }) => {
      window.localStorage.setItem('structai_access_token', seed.accessToken)
      window.localStorage.setItem('structai_refresh_token', seed.refreshToken)
    },
    { accessToken: tokens.access_token, refreshToken: tokens.refresh_token },
  )

  return { email, password, accessToken: tokens.access_token, refreshToken: tokens.refresh_token }
}

// Re-export the key names so a spec that needs to assert directly against
// localStorage (rather than just relying on seedAuthedSession) doesn't have to
// duplicate the string literals.
export const STORAGE_KEYS = {
  accessToken: ACCESS_TOKEN_KEY,
  refreshToken: REFRESH_TOKEN_KEY,
}
