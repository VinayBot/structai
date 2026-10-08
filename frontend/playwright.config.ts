import { defineConfig, devices } from '@playwright/test'

/**
 * Both dev servers (backend on :8000, frontend on :5173) are started manually
 * via `make dev` — not auto-spawned here — since the backend needs a reachable
 * Ollama/Groq for the live-run specs, which Playwright's `webServer` can't arrange.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  // 'list' for a readable local terminal run; 'html' (never auto-opened) so CI has
  // an actual browsable report to upload as an artifact on failure.
  reporter: [['list'], ['html', { open: 'never' }]],
  // eval.spec.ts and the live-run specs wait on real model calls (with retries),
  // which can comfortably exceed Playwright's 30s default per-test timeout.
  timeout: 240_000,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
