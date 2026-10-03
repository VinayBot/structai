import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import { watchPageHealth } from './helpers'

// The one spec that drives the real register -> login -> landing UI flow by hand,
// rather than using helpers.seedAuthedSession's API-based shortcut every other spec uses.
test('a new user can register, then log in, and land on the chat page', async ({ page }) => {
  const health = watchPageHealth(page)
  const email = `e2e-${randomUUID()}@example.com`
  const password = 'password1'

  await page.goto('/register')
  await page.getByPlaceholder('you@example.com').fill(email)
  await page.getByPlaceholder('password (8+ chars, at least one digit)').fill(password)
  await page.getByRole('button', { name: 'Sign up', exact: true }).click()

  await expect(page).toHaveURL(/\/app\/chat$/)

  await page.screenshot({ path: '../docs/assets/login-after-register.png' })

  // register() auto-logs-in (AuthContext.register calls login() internally), so clear
  // storage here to independently exercise the login form against the same account.
  await page.evaluate(() => window.localStorage.clear())
  await page.goto('/login')
  await page.getByPlaceholder('you@example.com').fill(email)
  await page.getByPlaceholder('password').fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()

  await expect(page).toHaveURL(/\/app\/chat$/)
  await expect(page.getByPlaceholder('Ask anything…')).toBeVisible()

  await page.screenshot({ path: '../docs/assets/login-after-login.png' })

  health.assertHealthy()
})

test('an unknown route redirects to the landing page', async ({ page }) => {
  await page.goto('/this-route-does-not-exist')
  await expect(page).toHaveURL('/')
})

test('visiting a protected route while logged out redirects to login', async ({ page }) => {
  await page.goto('/app/chat')
  await expect(page).toHaveURL(/\/login$/)
})
