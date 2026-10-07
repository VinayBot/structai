import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { configDefaults, defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Every versioned route lives under this one prefix now - see
      // app/main.py::create_app() for the include_router(..., prefix="/api/v1") calls.
      '/api': 'http://localhost:8000',
      '/openapi': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    // e2e/ holds Playwright specs, which define test() themselves - vitest's
    // default glob matches *.spec.ts regardless of directory, so without this
    // it tries (and fails) to collect Playwright's tests as if they were its own.
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
})
