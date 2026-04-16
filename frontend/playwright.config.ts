// Playwright config for scrumban e2e smoke specs.
//
// The `smoke-tester` agent (see .claude/agents/smoke-tester.md) owns the stack
// lifecycle via `docker compose up/down` — that is why `webServer` is intentionally
// NOT configured here. Encoding `npm run dev` into Playwright would clash with the
// agent's retry-after-compose-cycle flow and bypass the real api + bot services
// the specs are meant to exercise.
//
// Retries=0 for the same reason: the agent performs a single deliberate retry
// after tearing the stack down; Playwright re-running silently would mask the
// flake signal the agent is specifically looking for.

import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  // Parallel-safe: every spec mints its own user via `randomUsername()` (see
  // tests/e2e/helpers.ts), so concurrent workers never collide on the shared DB.
  fullyParallel: true,
  retries: 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  outputDir: './tests/e2e/artifacts',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
