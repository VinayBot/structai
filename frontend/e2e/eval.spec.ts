import { expect, test } from '@playwright/test'
import { seedAuthedSession, watchPageHealth } from './helpers'

// Needs a reachable gateway (local Ollama and/or Groq) behind the fallback chain -
// same live-model dependency as the rest of the real-model specs in this suite.
test('running 3 golden cases streams live progress and populates the dashboard', async ({ page }) => {
  await seedAuthedSession(page)
  const health = watchPageHealth(page)

  await page.goto('/app/evaluation')

  const caseCheckboxes = page.locator('ul.max-h-80 li input[type="checkbox"]')
  await expect(caseCheckboxes.first()).toBeVisible()

  // All golden cases are selected by default ("select all" starts checked) - clear
  // that first so checking 3 boxes actually lands at exactly 3, not a no-op.
  await page.getByLabel('select all').uncheck()
  for (let i = 0; i < 3; i++) {
    await caseCheckboxes.nth(i).check()
  }

  const runButton = page.getByRole('button', { name: 'Run 3 case(s)' })
  await expect(runButton).toBeEnabled()

  // Scope to the Leaderboard card specifically - the page has a second table
  // (Head-to-head) whose row count never changes, which would make a
  // page-wide `table tbody tr` count insensitive to whether this run landed.
  const leaderboardTable = page.locator('.eval-card', { has: page.getByText('Leaderboard', { exact: true }) }).locator('table')
  async function totalLeaderboardRuns(): Promise<number> {
    const cells = await leaderboardTable.locator('tbody tr td:nth-child(3)').allTextContents()
    return cells.reduce((sum, text) => sum + Number(text), 0)
  }
  const totalRunsBefore = await totalLeaderboardRuns()

  await page.screenshot({ path: '../docs/assets/eval-before-run.png' })
  await runButton.click()

  // 3 real model calls (with retries) can comfortably take a couple of minutes.
  // "Pass rate" also appears in the persistent Dashboard KPI grid below, so match
  // the Report card by a label that's unique to it.
  await expect(page.getByText('Report', { exact: true })).toBeVisible({ timeout: 180_000 })
  await expect(page.getByText('Passed / total', { exact: true })).toBeVisible()

  await page.screenshot({ path: '../docs/assets/eval-report.png' })

  // The leaderboard is grouped by provider/model and tracks all-time stats
  // (app/services/eval_service.py::_build_leaderboard) - a run under a
  // provider/model pairing that's already on the board updates its existing
  // row's "Runs" count rather than adding a new row, so this must assert on
  // the total run count moving by exactly one, not on the row count growing.
  await expect(async () => {
    const totalRunsAfter = await totalLeaderboardRuns()
    expect(totalRunsAfter).toBe(totalRunsBefore + 1)
  }).toPass({ timeout: 15_000 })

  await page.screenshot({ path: '../docs/assets/eval-dashboard.png' })

  health.assertHealthy()
})
