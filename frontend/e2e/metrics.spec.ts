import { expect, test } from '@playwright/test'
import { seedAuthedSession, watchPageHealth } from './helpers'

test('metrics page shows KPI stat cards, the raw tab, and the summary JSON toggle', async ({ page }) => {
  await seedAuthedSession(page)
  const health = watchPageHealth(page)

  await page.goto('/app/metrics')

  // Scoped to <p> KPI-card labels specifically - a breakdown table on the same page
  // has a "<th>Errors</th>" column header that would otherwise collide.
  for (const label of ['Requests', 'Server errors', 'Error rate', 'Failed runs', 'p50 latency', 'p95 latency']) {
    await expect(page.getByRole('paragraph').filter({ hasText: new RegExp(`^${label}$`) })).toBeVisible()
  }

  await page.screenshot({ path: '../docs/assets/metrics-summary.png' })

  const rawJsonToggle = page.getByRole('button', { name: /Raw JSON/ })
  await rawJsonToggle.click()
  await expect(page.getByText('generated_at:', { exact: false })).toBeVisible()

  await page.getByRole('button', { name: 'raw', exact: true }).click()
  await expect(page.getByRole('checkbox', { name: /process\/runtime metrics/i })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Refresh' })).toBeVisible()

  await page.screenshot({ path: '../docs/assets/metrics-raw.png' })

  health.assertHealthy()
})
