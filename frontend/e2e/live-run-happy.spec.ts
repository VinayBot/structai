import { expect, test } from '@playwright/test'
import { seedAuthedSession, watchPageHealth } from './helpers'

const PIPELINE_NODES = [
  'jwt_auth',
  'request_validation',
  'rate_limiter',
  'injection_screen',
  'pii_redaction',
  'schema_builder',
  'router',
  'validator_retry',
  'output_guardrails',
]

// Needs a reachable gateway (local Ollama and/or Groq) behind the fallback chain -
// same live-model dependency as eval.spec.ts.
test('a demo Live Run passes through every pipeline stage in order', async ({ page }) => {
  await seedAuthedSession(page)
  const health = watchPageHealth(page)

  await page.goto('/app/architecture')

  await page.getByRole('button', { name: 'Expand Test scenarios' }).click()
  await page.getByRole('button', { name: 'Live Run', exact: true }).click()
  await page.getByRole('button', { name: 'Demo: run', exact: true }).click()

  await page.screenshot({ path: '../docs/assets/live-run-happy-running.png' })

  // A real model call (with retries) can take a little while. Scope to the
  // final-result Chip specifically - a Recent-runs history row from a prior run in
  // this same browser context can also render the literal text "Passed".
  const resultChip = page.locator('span').filter({ hasText: /^Passed$/ })
  await expect(resultChip).toBeVisible({ timeout: 120_000 })

  for (const nodeId of PIPELINE_NODES) {
    const rows = page.locator('ol li').filter({ hasText: nodeId })
    await expect(rows.last()).toContainText('passed')
  }

  await expect(page.locator('[data-id="output_guardrails"] [aria-label^="status:"]')).toHaveAttribute(
    'aria-label',
    'status: ok',
  )

  await page.screenshot({ path: '../docs/assets/live-run-happy-passed.png' })

  // The Inspector auto-expands on Live Run start; its default "Token" tab shows the
  // real decoded access/refresh token claims.
  await expect(page.getByText('Access token', { exact: true })).toBeVisible()
  await expect(page.getByText('Signature is never decoded or displayed.').first()).toBeVisible()

  await page.getByRole('button', { name: 'Output', exact: true }).click()
  // Scoped to the Inspector's own <section> - the Live Run panel on the left
  // renders the same final result (and the same "Copy result JSON" button) too.
  const inspectorSection = page.locator('section')
  await expect(inspectorSection.getByRole('button', { name: 'Copy result JSON' })).toBeVisible()

  await page.screenshot({ path: '../docs/assets/live-run-happy-inspector-output.png' })

  health.assertHealthy()
})
