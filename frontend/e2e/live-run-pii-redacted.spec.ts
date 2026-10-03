import { expect, test } from '@playwright/test'
import { seedAuthedSession, watchPageHealth } from './helpers'

const PIPELINE_NODES_BEFORE_OUTPUT = [
  'jwt_auth',
  'request_validation',
  'rate_limiter',
  'injection_screen',
  'pii_redaction',
  'schema_builder',
  'router',
  'validator_retry',
]

// Needs a reachable gateway (local Ollama and/or Groq) behind the fallback chain -
// same live-model dependency as live-run-happy.spec.ts. The prompt itself carries no
// PII (so pii_redaction passes through untouched); it asks the model to fabricate some
// in its own answer, exercising the output-side scan_pii_in_data path (app/guardrails/
// pii.py) that the input-side scan can never trigger on its own.
test('a demo PII run redacts model-fabricated PII and reports a modified status', async ({ page }) => {
  await seedAuthedSession(page)
  const health = watchPageHealth(page)

  await page.goto('/app/architecture')

  await page.getByRole('button', { name: 'Expand Test scenarios' }).click()
  await page.getByRole('button', { name: 'Live Run', exact: true }).click()
  await page.getByRole('button', { name: 'Demo: pii', exact: true }).click()

  await page.screenshot({ path: '../docs/assets/live-run-pii-running.png' })

  // A real model call (with retries) can take a little while. Scope to the
  // final-result Chip specifically - a Recent-runs history row from a prior run in
  // this same browser context can also render overlapping "Passed" text.
  const resultChip = page.locator('span').filter({ hasText: /^Passed \(redacted\)$/ })
  await expect(resultChip).toBeVisible({ timeout: 120_000 })

  for (const nodeId of PIPELINE_NODES_BEFORE_OUTPUT) {
    const rows = page.locator('ol li').filter({ hasText: nodeId })
    await expect(rows.last()).toContainText('passed')
  }

  const outputRows = page.locator('ol li').filter({ hasText: 'output_guardrails' })
  await expect(outputRows.last()).toContainText('modified')

  await expect(page.locator('[data-id="output_guardrails"] [aria-label^="status:"]')).toHaveAttribute(
    'aria-label',
    'status: modified',
  )

  // The warning line names which categories were redacted, e.g. "pii redacted (email, phone)".
  // This text legitimately appears more than once (event log row, final summary line,
  // possibly a toast) - scope to the first match rather than requiring exactly one.
  await expect(page.getByText(/pii redacted \(.+\)/).first()).toBeVisible()

  // The result JSON shows the redaction placeholder in place of the model's raw
  // fabricated PII - the actual proof that redaction happened, not just the label.
  await expect(page.getByText(/\[REDACTED_(EMAIL|PHONE)\]/).first()).toBeVisible()

  await page.screenshot({ path: '../docs/assets/live-run-pii-modified.png' })

  health.assertHealthy()
})
