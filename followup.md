# Followup

## Status

Branch `main`, in sync with `origin/main`. **Phase 0 complete. Phase 1 complete end-to-end** — auth backend + frontend auth views + username-enumeration timing fix + Telegram link-code surface (web side). Developer-experience tooling includes a real-browser e2e layer (ADR-0006), a fully autonomous pre-merge review loop with agent-authored auto-merge on clean `approve` (ADR-0007), a mandatory Playwright spec on every task including backend-only (ADR-0008), a pinned-ruff invariant across pre-commit + CI + pyproject, a compose-aware vite dev proxy, a registry-safe `smoke-tester` agent description, a dedicated CI `e2e` job running Playwright on every push/PR, and — post-#67 — an optional `backend/.env.local` override that pydantic-settings loads after `.env` so host-shell tools (pre-push pytest, local uvicorn) reach the compose-published Postgres port at `localhost:5432` without the old `DATABASE__URL=... git push ...` env prefix.

**70-issue queue in progress**. Issue 68 is next — the `--no-verify` block on pure-non-docs diffs — now unblocked because #67 removed the legitimate reason for hosts to need `--no-verify` in the first place.

Merged to `main` (recent — earlier history in `git log`):
- Issue 67 / PR (pending merge) — `backend/.env.local` override loaded after `.env` by pydantic-settings; compose `env_file` untouched (`backend/.env` stays compose-shaped with `@postgres:5432/...`); `.env.local.example` template tracked; README + `CLAUDE.md → implementer.md` canonical-fix note updated; mandatory smoke spec `frontend/tests/e2e/api/health.spec.ts` added (Playwright `request` context, no browser). Pre-push pytest now passes on the host shell without the `DATABASE__URL=... git push` prefix.
- **DX pre-loop readiness pass** (direct-to-main) — widened reviewer smoke gate to "any behavior change"; added Playwright mandate + env workaround + `followup.md` prune rule to implementer; added `/loop` mode issue-pickup rules to `CLAUDE.md`; kept `docs/loop.md` in sync; pointer from `tasks/todo.md` Phase 2 to the issue queue; ADRs 0006 / 0007 / 0008 filed retroactively for decisions that previously shipped without one.
- DX issue 26 / PR 45 — `e2e` CI job (postgres + redis services, host-side uvicorn + vite, cached chromium, failure artifacts). First-run green (6/6 specs, 5.6s). Not yet in branch-protection required checks.
- DX issue 43 / PR 44 — `smoke-tester` agent description trimmed 445 → 268 chars so it re-registers.
- DX issue 25 / PR 42 — compose-aware vite dev proxy (`VITE_API_PROXY_TARGET` env var).
- DX issue 40 / PR 41 — `docs/loop.md` quick-reference.
- DX issue 38 / PR 39 — fully autonomous loop: auto-merge on clean approve, nits are bugs, user-visible features require Playwright spec, smoke-fail routes to implementer.
- DX issue 33 / PR 37 — pinned ruff to 0.15.11 across pre-commit + CI + pyproject.
- DX issue 32 / PR 34 — reviewer `should-fix` is non-negotiable.
- DX issue 29 / PR 30 — autonomous pre-merge review loop codified.
- DX issue 24 / PR 27 — smoke-tester subagent + Playwright e2e baseline.
- Phase 1 issue 20 / PR 31 — Telegram link-code endpoint + Profile "Link Telegram" UI.
- Phase 1 issue 23 — username-enumeration timing leak closed (dummy argon2 verify, timing-parity test).
- Phase 1 issues 1-4 — `User` + `TgLinkCode` models, auth endpoints (ADR-0005 rotating refresh tokens), Vue Login/Register/Profile, 17-test suite with 99% coverage on `auth_service`.

Full pre-Phase-2 history in `git log`.

ADRs in force: 0001 (api+bot split with shared services), 0002 (Redis pub/sub realtime bus), 0003 (Telegram linking via one-time code), 0004 (float position for task ordering), 0005 (opaque rotating refresh tokens), 0006 (Playwright e2e + smoke-tester agent), 0007 (autonomous pre-merge review loop), 0008 (Playwright spec mandatory on every task).

**Convention reminder**: write bare issue references like "issue 23" in `followup.md` rather than `#23` — GitHub's keyword scanner interprets literal `#NN` in merge commits as closing references, which previously auto-closed issue 23 without a fix. PR bodies use `#N`; `followup.md` uses bare numbers.

## Next

1. **Loop auto-picks issue 68** (`chore(dx): pre-push hook blocks --no-verify to main unless diff is pure docs`). Now unblocked: the legitimate host-env reason to reach for `--no-verify` is gone post-#67, so the hook can safely tighten. Expected loop: implementer → smoke-tester (api spec) → reviewer → auto-merge.

2. **After 68 closes, loop continues to issue 36** (Phase 2 models: `Board`, `Column`, `Task`, `Label`, `TaskLabel` + migration). First real Phase 2 work; every following endpoint PR depends on these models landing.

3. **Then issues 69 and 70** — `POST /api/boards` (create board, owner auto-membership) and `GET /api/boards` (list member's boards). Phase 2 REST begins.

4. **Deferred user actions** (none gate the loop):
   - Flip `e2e` CI job to branch-protection required check after 2-3 more green runs: `gh api -X PATCH repos/vaporphd/scrumban/branches/main/protection/required_status_checks -F 'strict=true' -f 'contexts[]=backend' -f 'contexts[]=frontend' -f 'contexts[]=e2e'`.
   - Consider an architectural-review checkpoint after each Tier completion (~5-10 PRs) if cross-PR drift becomes a concern.
