import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/auth': 'http://localhost:8000',
      '/arch': 'http://localhost:8000',
      '/structured': 'http://localhost:8000',
      '/schemas': 'http://localhost:8000',
      '/projects': 'http://localhost:8000',
      '/chats': 'http://localhost:8000',
      '/files': 'http://localhost:8000',
      '/usage': 'http://localhost:8000',
      '/openapi': 'http://localhost:8000',
      '/search': 'http://localhost:8000',
      '/traces': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/eval': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
