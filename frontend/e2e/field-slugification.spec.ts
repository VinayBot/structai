import { expect, test } from '@playwright/test'
import { seedAuthedSession, watchPageHealth } from './helpers'

test('a typed field name is slugified to snake_case on blur', async ({ page }) => {
  await seedAuthedSession(page)
  const health = watchPageHealth(page)

  await page.goto('/app/chat')

  const nameInput = page.getByPlaceholder('field_name')
  await expect(nameInput).toBeVisible()

  await nameInput.fill('First Name')
  await expect(page.getByText('will be saved as "first_name"', { exact: true })).toBeVisible()

  await page.screenshot({ path: '../docs/assets/field-slugification-hint.png' })

  await nameInput.blur()

  await expect(nameInput).toHaveValue('first_name')
  await expect(page.getByText('will be saved as "first_name"', { exact: true })).not.toBeVisible()

  await page.screenshot({ path: '../docs/assets/field-slugification-corrected.png' })

  health.assertHealthy()
})
