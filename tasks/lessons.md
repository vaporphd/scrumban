# Lessons (session-to-session corrections)

## 2026-04-19 — Every task ships a Playwright spec

**Correction**: When planning Phase 2 / Phase 3, I proposed 28 backend-only issues whose smoke requirement was "full e2e suite stays green — no new spec needed." Alex rejected this: *"I want you to add smoke test via playwright even if change is on backend. it can easily break frontend too. so smoke is mandatory."*

**Rule going forward**:
- Every PR — backend, frontend, full-stack, migration, endpoint-only — ships a Playwright spec as part of acceptance criteria.
- Backend-only changes use Playwright's `request` context (no browser) under `frontend/tests/e2e/api/<endpoint>.spec.ts`.
- Frontend changes use `page`-driven specs.
- The reviewer.md "Smoke-test coverage gate" trigger widens from "user-visible feature" to "any behavior change."

**Exception list (narrow)**:
- Tooling-only PRs (CI, pre-commit, agent config, hooks): no new spec required, but the existing `npm run e2e` must pass post-merge.
- Pure docs PRs: no spec required.

**Why this matters**: pytest-green is not UI-safe. Contract drift, new 4xx codes, and response-shape changes break the frontend without pytest noticing. Playwright is the only gate that catches the end-to-end regression.

**Enforcement point**: pre-commit the spec file name in every issue body at issue-creation time. Name the scenario. Do not leave this to implementer judgment at PR review.
