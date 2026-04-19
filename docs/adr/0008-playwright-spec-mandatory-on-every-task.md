# ADR-0008: Playwright spec mandatory on every task (widen smoke gate beyond user-visible features)

**Status:** Accepted
**Date:** 2026-04-19

## Context

ADR-0007 established auto-merge on `approve` and made Playwright specs mandatory for **user-visible features**. Over the next few PRs it became clear the "user-visible" boundary was too narrow:

- Backend-only PRs (new endpoint, endpoint patch, response-shape change) could merge without any e2e coverage because they didn't add a new frontend surface.
- Contract drift — a backend PR silently changing a response field name, adding a new 4xx code, or tightening validation — broke frontend flows that pytest never exercised. The smoke layer saw nothing because smoke-tester only ran on "user-visible" PRs.
- When the user started planning the 70-issue Phase 2 + Phase 3 queue, the initial plan declared ~28 backend-only issues as "no Playwright spec needed, full e2e suite stays green". This preserved the old gap at scale.

The user's correction (2026-04-19, verbatim): *"I want you to add smoke test via playwright even if change is on backend. it can easily break frontend too. so smoke is mandatory"*.

Two questions had to be resolved:

1. **What does a Playwright spec look like for a backend-only PR that has no UI consumer yet?**
2. **Where does the rule live so every agent sees it?**

## Decision

Widen the Smoke-test coverage gate in `reviewer.md` from "user-visible feature" to **"any behavior change"**. Every PR — backend, frontend, full-stack, migration, endpoint change, bot handler — must ship a Playwright spec as part of acceptance criteria.

Implementation specifics:

1. **Backend-only PRs** write specs under `frontend/tests/e2e/api/<name>.spec.ts` using Playwright's `request` fixture (no browser). The `request` context runs raw HTTP assertions against the compose stack's api service in the same `npm run e2e` invocation as browser specs. Example shape:
   ```ts
   test('POST /api/boards creates', async ({ request }) => {
     const r = await request.post('/api/boards', { data: { name: 'x' } })
     expect(r.status()).toBe(201)
   })
   ```

2. **Frontend / full-stack PRs** continue to use the `page` context under `frontend/tests/e2e/*.spec.ts` for real-browser coverage.

3. **Every issue body pre-commits the spec file and scenario** at issue-creation time. Reviewer checks that the PR adds exactly what the issue body named. This removes the "does this really need a spec?" debate at review.

4. **Exemptions, narrow**:
   - Pure infra (CI workflows, Dockerfiles, pre-commit configs, agent descriptions).
   - Pure docs (`.md` files, ADRs).
   - Pure test-only refactors (pytest fixtures without behavior change).
   - Everything else gets a spec. Service-layer refactors get a spec. Repo-layer changes that back an endpoint get a spec. Migrations get a spec that hits an affected endpoint post-migration.

5. **Rule storage**: canonical text lives in `tasks/lessons.md` (durable session-to-session) and `reviewer.md` "Smoke-test coverage gate" (enforced at review). `implementer.md` MUST list says "every PR ships a Playwright spec per issue body — follow it". Quick-reference at `docs/loop.md`.

## Reasoning

**Why widen to backend?** Pytest-green is not UI-safe. Pytest exercises Python code paths through mock FastAPI clients; it never boots the vite dev server, never loads a real component tree, never posts real HTTP from a browser. A backend change that renames `task.due_date` to `task.due_at` in the JSON response passes pytest (pytest asserts on parsed dicts it controls) but breaks every component that binds to `due_date`. Playwright with `request` context is the cheapest mechanism that catches this class of regression: it exercises the same HTTP boundary the browser does.

**Why `request` context rather than full browser for backend?** Browser-based smoke for backend-only PRs would either (a) require a full UI flow built first — dependency order collapses; or (b) forcibly instantiate a browser, navigate, and poke the DOM in ways that don't exercise the actual change. `request` hits the HTTP boundary directly — fast, no UI dependency, and still catches contract drift. Playwright's `request` is the right tool for this tier.

**Why every issue pre-commits the spec file?** Deferring spec authorship to "implementer figures out what to write" produced two failure modes at scale: (a) the spec skipped entirely ("I'll add it when the UI lands"), (b) the spec written against the wrong scope (the wrong endpoint, the wrong flow). Naming the file + scenario in the issue body at creation time eliminates both.

**Why keep a narrow exemption list?** Pure infra and docs genuinely cannot break a user-facing flow in a way Playwright would detect. The cost of mandating specs on CI config changes is higher than the signal — reviewer would be asked to judge "does this spec make sense?" on every tooling PR. Narrow, named exemptions cap this. Pure test-only refactors are the tightest exception; a gray-area test-refactor that also touches a fixture affecting production code paths should still get a spec.

**Why this ADR specifically?** ADR-0007 defined the loop and said specs were mandatory for user-visible features. The widening on 2026-04-19 is a distinct architectural decision affecting every PR, retroactively widening the smoke boundary. Without an ADR this would be a floating rule in `lessons.md` that agents might miss on compaction; with an ADR, it's anchored in the decision history that reviewer's architectural gate checks on every subsequent subsystem PR.

**Alternatives rejected**:
- **Keep the old user-visible boundary and rely on pytest** — the problem this ADR solves.
- **Require full browser smoke on backend PRs too** — dependency nightmare, breaks the "one issue, one PR" principle.
- **Gate on `gh pr view --json files` heuristic (e.g. "touches `backend/app/api/`" → require spec)** — brittle; service refactors touch `backend/app/services/` not `api/` but still need specs. The "any behavior change" rule is stricter and simpler.

## Consequences

- The 70-issue Phase 2 + Phase 3 queue was re-filed with every issue naming its Playwright spec explicitly — `frontend/tests/e2e/api/*.spec.ts` for backend, `frontend/tests/e2e/*.spec.ts` for frontend.
- Reviewer's gate text in `reviewer.md` "Smoke-test coverage gate" says "every task" with the 2026-04-19 authorization timestamp.
- Implementer's responsibility surface grows by one item: "write the Playwright spec named in the issue body". For backend endpoints this is a 20-line `request`-context spec per endpoint — modest overhead against the safety gain.
- CI `e2e` job (ADR-0006) now exercises `tests/e2e/api/*.spec.ts` alongside browser specs automatically — Playwright's `testDir: './tests/e2e'` already auto-discovers nested directories, no config change needed.
- Approximate runtime per PR: backend specs are ~100-500ms each (raw HTTP, no browser); browser specs are ~500ms-3s each. Full suite cost grows roughly linearly with PR count but stays well under the CI job budget on current runners (observed 5.6s for 6 specs on PR #45).
- The smoke layer is now the authoritative integration gate for every kind of change. If a PR doesn't have a spec and isn't on the narrow exemption list, reviewer blocks. No backend-only slip-through.
- `tasks/lessons.md` captures the rationale in compact form for session-to-session memory; this ADR captures it for long-term architectural memory. Both kept in sync on future tightening.
