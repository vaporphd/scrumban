# Frontend e2e (Playwright)

Real-browser smoke specs that exercise the assembled stack — frontend dev server, FastAPI, Postgres, Redis — end to end. Owned by the `smoke-tester` agent (see `.claude/agents/smoke-tester.md`); run locally before opening a PR that touches `frontend/`.

## First-time setup

Once per machine:

```sh
cd frontend
npm install
npx playwright install --with-deps chromium
```

`--with-deps` pulls system libraries the headless Chromium needs (skip the flag if you already have them — Playwright will tell you).

## Running

The agent is responsible for the stack lifecycle, but to run the suite by hand:

```sh
# 1. Bring up the full stack from the repo root.
cd deploy && docker compose up -d postgres redis minio api bot frontend
# 2. Wait for both endpoints to respond.
curl -fsS http://localhost:8000/api/health
curl -fsSI http://localhost:5173 | head -1
# 3. Run the specs.
cd frontend && npm run e2e
```

The compose `frontend` service sets `VITE_API_PROXY_TARGET=http://api:8000` so vite's dev proxy reaches the api service over Docker's bridge network (see issue 25). Running `npm run dev` on the host still works — the env var defaults to `http://localhost:8000` — useful when iterating on the Vue app without rebuilding the compose frontend container.

Artifacts (screenshots, videos, traces) land under `frontend/tests/e2e/artifacts/` on failure; the HTML report lands under `frontend/playwright-report/`. Both directories are gitignored — never commit them.

## Adding a spec

Every PR that touches `frontend/` adds or updates **one** spec for the user-visible behavior it ships. New specs live next to the existing five, named `<scenario>.spec.ts`, and stay under ~50 lines each. Keep each spec self-contained: register a fresh user with `randomUsername()` from `helpers.ts` so specs do not depend on shared DB rows or each other's order.

Selectors, in order of preference: `getByRole` (the `Sign in` button, the `Profile` heading), then `autocomplete` attributes (`input[autocomplete="username"]`), then text content via `getByText`. Avoid CSS-class selectors and avoid adding `data-testid` for the sake of tests — the existing roles + autocomplete + text are stable enough.

## Failure handling (also encoded in the smoke-tester agent)

The agent runs this ordering on every invocation; the manual operator should mirror it:

1. **Always**: capture screenshots + video + trace to `tests/e2e/artifacts/{run-id}/`. Playwright does this automatically per `playwright.config.ts` (`trace: retain-on-failure`, `video: retain-on-failure`, `screenshot: only-on-failure`).
2. **Always**: block the workflow on the first red and surface the verdict.
3. **On first fail**: re-run only the failing scenario(s) once, after a `docker compose down && docker compose up -d` cycle. Single retry, no artifact deletion.
4. **On second fail (reproduced)**: file a GitHub issue with `type/fix, area/frontend`, link the artifacts, and hand off to `bug-hunter`.
5. **On second pass (transient flake)**: report `transient, recovered` to the main session and skip the auto-file.

Do not edit a failing spec to make it pass. If a spec exposes a real frontend bug, stop and report — the spec is doing its job.
