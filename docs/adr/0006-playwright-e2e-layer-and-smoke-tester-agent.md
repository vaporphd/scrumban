# ADR-0006: Playwright e2e layer + smoke-tester agent as the integration gate

**Status:** Accepted
**Date:** 2026-04-15

## Context

By end of Phase 1 the repo had backend pytest (unit + integration) and frontend vitest (unit) coverage. Neither exercises the actual user journey — a pytest-green backend can ship a broken API contract that the frontend silently misuses, and vitest never touches a real browser or the compose stack. We needed an integration layer that:

1. Drives a real browser against an actually-running stack (api + bot + postgres + redis + frontend vite).
2. Catches regressions before PRs merge, not after.
3. Produces forensic artifacts (screenshots, video, trace) on failure so the implementer has a one-shot reproduction.
4. Fits the autonomous agent workflow — not "developer runs it manually before pushing", but "an agent in the pre-merge loop runs it and hands off artifacts on failure".

## Decision

1. Adopt **Playwright** (`@playwright/test`) as the e2e framework, pinned to an exact version (currently 1.59.1) across `frontend/package.json`, CI cache keys, and the browser install step.

2. E2e specs live under `frontend/tests/e2e/*.spec.ts`. Playwright config at `frontend/playwright.config.ts` retains:
   - `screenshot: 'only-on-failure'`
   - `video: 'retain-on-failure'`
   - `trace: 'retain-on-failure'`
   - Artifacts written to `frontend/tests/e2e/artifacts/<run-id>/`
   - `webServer` **intentionally not configured** — the stack lifecycle is owned externally (the `smoke-tester` agent in the agent flow; GitHub Actions service containers + background processes in CI).

3. Introduce the **`smoke-tester` subagent** (`.claude/agents/smoke-tester.md`) as a first-class member of the pre-merge review loop. Its job:
   - Pull the PR branch.
   - Bring up the compose stack.
   - Run `npm run e2e`.
   - On all-pass → hand off to `reviewer`.
   - On any fail → cycle the stack, retry **once**. Single retry distinguishes real regressions from docker-startup flakes.
   - On reproduced fail → hand artifacts back to `implementer` on the same branch (the failing spec IS the reproducer; the fix belongs in this PR). ADR-0007 codifies this handoff as part of the autonomous loop.

4. **Stack-lifecycle invariant**: both the agent flow and the CI `e2e` job start api + vite as explicit external steps, never via Playwright's `webServer`. This keeps smoke-tester's retry-after-compose-cycle semantics possible and matches how the GH runner is structured.

5. A separate CI job `e2e` runs the suite on every push/PR (added in PR #45). Chromium browser binary cached keyed on the pinned Playwright version so cold-start cost is one-time per version bump.

## Reasoning

**Why Playwright over Cypress / Selenium?** Playwright's built-in trace viewer is the killer feature for the agent workflow — it produces DOM snapshots per action, network log, and console log that implementer can open with `npx playwright show-trace` and diagnose the regression without re-running. Selenium needs third-party wrappers for this; Cypress has its own trace but licensing and parallelism constraints made it less appealing for the agent-driven loop.

**Why a dedicated agent instead of embedding smoke-test steps in the implementer?** Separation of concerns — implementer owns code change, smoke-tester owns integration verification, reviewer owns pre-merge check. Each is a narrow role with its own tool whitelist and response format; conflating them made the implementer's responsibility surface too large.

**Why external-owned `webServer`?** Playwright's `webServer` spawns the stack when specs start and kills it when they end. For the agent loop this is wrong: we want stack-cycle granularity separate from test-run granularity (the "retry after compose down/up" pattern explicitly depends on this). Keeping `webServer` undefined pushed us to the right design; the comment at the top of `playwright.config.ts` is load-bearing.

**Alternatives rejected**: (a) "just run vitest + MSW mocks" — mocks drift from reality; (b) "developer runs e2e locally before pushing" — the autonomous loop can't rely on a human-in-the-loop step; (c) "skip e2e, rely on CI integration tests only" — no browser coverage, contract drift goes uncaught.

## Consequences

- Every frontend PR and (per ADR-0008) every backend PR must include a Playwright spec. Spec authorship is part of the implementer's responsibility per the 2026-04-19 rule.
- CI `e2e` job is the authoritative gate for regressions that pytest can't catch. When it fails, the PR doesn't merge (once the job is added to branch-protection required checks; current status: advisory, scheduled to be flipped after 2-3 green runs).
- Playwright version bumps are synchronised across three files (`package.json`, CI cache key, browser-install step). Drift here creates "CI pulls a newer chromium than specs were authored against" failures — `ci.yml` has a comment naming the bump points.
- The smoke-tester's retry-once-after-cycle pattern bans certain Playwright features: `retries` in config must stay at `0`, and `webServer` stays undefined. Changing either regresses the flake-signal semantics — treat both as architectural constraints, not implementation details.
- Running `npm run e2e` now requires the full compose stack up (including api + bot). Developers doing day-to-day frontend work on vitest unit tests are unaffected; the e2e layer is expected to be driven by either the agent or CI, not by hand.
