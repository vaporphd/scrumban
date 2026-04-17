import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Dev proxy target. Defaults to localhost:8000 for host-side `npm run dev`.
// Override in compose (see deploy/docker-compose.yml) with
// `VITE_API_PROXY_TARGET=http://api:8000` so the browser's /api and /ws calls
// reach the api service via Docker DNS instead of the frontend container itself.
const API_PROXY_TARGET = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'
// ws:// vs http:// — vite accepts http(s) targets for websocket proxying when
// `ws: true` is set, but swapping the scheme keeps intent explicit and matches
// the previous config shape.
const WS_PROXY_TARGET = API_PROXY_TARGET.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: API_PROXY_TARGET,
        changeOrigin: true,
      },
      '/ws': {
        target: WS_PROXY_TARGET,
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // Playwright e2e specs live under tests/e2e/. Vitest's default include picks
    // up `**/*.spec.ts`, which would try (and fail) to import @playwright/test.
    // Run e2e via `npm run e2e`, not `npm test`.
    exclude: ['**/node_modules/**', '**/dist/**', 'tests/e2e/**'],
  },
})
