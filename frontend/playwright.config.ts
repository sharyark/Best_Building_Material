import { defineConfig } from '@playwright/test'

/** End-to-end smoke tests. They need the API (seeded demo data) and the Vite dev server running: see README. */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'desktop', use: { viewport: { width: 1366, height: 800 } } }],
})
