import { expect, test } from '@playwright/test'
import { seedAuthedSession, watchPageHealth } from './helpers'

const PASSED_BEFORE_INJECTION = ['jwt_auth', 'request_validation', 'rate_limiter']
const SKIPPED_AFTER_INJECTION = ['pii_redaction', 'schema_builder', 'router', 'validator_retry', 'output_guardrails']

// Needs a reachable gateway (local Ollama and/or Groq) - though a true prompt-
// injection attempt should never actually reach a provider, which is what this
// test proves.
test('a demo attack is blocked at the injection screen and never reaches the model', async ({ page }) => {
  await seedAuthedSession(page)
  const health = watchPageHealth(page)

  await page.goto('/app/architecture')

  await page.getByRole('button', { name: 'Expand Test scenarios' }).click()
  await page.getByRole('button', { name: 'Live Run', exact: true }).click()
  await page.getByRole('button', { name: 'Demo: attack', exact: true }).click()

  await page.screenshot({ path: '../docs/assets/live-run-attack-running.png' })

  await expect(page.getByText('Failed', { exact: true })).toBeVisible({ timeout: 60_000 })

  for (const nodeId of PASSED_BEFORE_INJECTION) {
    const rows = page.locator('ol li').filter({ hasText: nodeId })
    await expect(rows.last()).toContainText('passed')
  }

  const injectionRows = page.locator('ol li').filter({ hasText: 'injection_screen' })
  await expect(injectionRows.last()).toContainText('failed')

  for (const nodeId of SKIPPED_AFTER_INJECTION) {
    const rows = page.locator('ol li').filter({ hasText: nodeId })
    await expect(rows.last()).toContainText('skipped')
    // Zero provider calls happened: none of these downstream stages may ever show "passed".
    await expect(rows.filter({ hasText: 'passed' })).toHaveCount(0)
  }

  await expect(page.locator('[data-id="injection_screen"] [aria-label^="status:"]')).toHaveAttribute(
    'aria-label',
    'status: error',
  )

  await page.screenshot({ path: '../docs/assets/live-run-attack-failed.png' })

  health.assertHealthy()
})
