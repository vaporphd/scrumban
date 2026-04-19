# ADR-0007: Autonomous pre-merge review loop + agent-authored auto-merge

**Status:** Accepted
**Date:** 2026-04-17

## Context

Claude Code's default behavior is to ask the user for authorization before destructive actions — `gh pr merge`, `git push --force`, etc. For a solo-developer repo where each PR goes through implementer → smoke-tester → reviewer agent-delegation, that default produced 3-5 routine user questions per PR ("should I run reviewer?", "should I send these findings back?", "should I merge?"). This friction scaled linearly with PR count and made the agent flow less of an automation win and more of a ceremony.

The underlying goal: a PR should move from "issue filed" to "merged on main" through the agent chain without per-step user intervention, **only** pausing for genuine human judgment (pivots, blockers, scope questions).

Constraints:
- Safety: auto-merge must not bypass CI or introduce unreviewed code.
- Scope: authorization applies only to PRs produced through the internal agent flow. External PRs (dependabot, eventually outside contributors) retain the user-merge gate.
- Recoverability: if the loop hits an unresolvable blocker, it must stop + escalate, not improvise.

## Decision

Adopt a **fully autonomous pre-merge review loop**. The main session drives implementer → smoke-tester → reviewer → (possibly back to implementer) → `gh pr merge --auto` without routine user questions.

Key rules (canonical text in `CLAUDE.md` → "Pre-merge review loop", quick-reference at `docs/loop.md`):

1. **Verdict ↔ findings consistency (authorization 2026-04-17)**: every finding at every severity — must-fix, should-fix, nit — routes identically back to implementer. The old three-tier verdict (`approve` / `approve-with-suggestions` / `changes-requested`) collapses to a clean binary: `approve` (literally zero findings) or `changes-requested` (one or more findings, any severity). `approve-with-suggestions` is deprecated — reviewer must not emit it.

2. **Auto-merge on clean approve (authorization 2026-04-17)**: on `reviewer` verdict `approve` (zero findings), main session **immediately** runs `gh pr merge N --auto --squash --delete-branch`. No user question. GitHub waits for CI green and merges; the linked issue auto-closes via `Closes #N` in the PR body. Authorization scope: PRs produced through the implementer → reviewer agent loop. External PRs still require manual merge.

3. **Smoke-fail → implementer, not bug-hunter (authorization 2026-04-17)**: when smoke-tester reports `reproduced, handoff to implementer`, the main session routes the failing scenario + artifacts back to the same implementer on the same branch. The failing spec IS the reproducer; the fix belongs in this PR. No new issue is filed. **Exception**: if implementer determines the failure is pre-existing (not caused by this PR's diff, verified via `git diff origin/main..HEAD`), they escalate to `bug-hunter` themselves and pause the PR pending the pre-existing fix landing separately.

4. **Playwright specs are mandatory on user-visible features (authorization 2026-04-17, widened 2026-04-19 — see ADR-0008)**: reviewer blocks PRs lacking a Playwright spec under `frontend/tests/e2e/*.spec.ts` for any user-visible feature change. "real ui test with playwright. no exception."

5. **Loop termination**: the loop ends when either (a) auto-merge executes, or (b) an agent reports a blocker the main session can't resolve (escalate to user). The user can interrupt and pivot at any step.

## Reasoning

**Why auto-merge specifically on zero findings?** The reviewer's verdict is already a strict pass/fail binary under rule (1). If reviewer says `approve` (zero findings) and CI is green, the chain has produced a PR that satisfies every gate the repo defines. Asking the user "should I merge?" at that point is theatre — the answer is always yes, so making it an explicit step costs 1 question per PR without reducing risk.

**Why the authorization must be per-project, not default in Claude Code?** Auto-merging PRs is the kind of destructive action that Claude Code's base system correctly guards by default. The autonomy we want here depends on (a) an adversary-free environment (solo repo, no untrusted commits), (b) strong gates before the merge (CI + smoke + reviewer), and (c) narrow scope (agent-produced PRs only). The per-project CLAUDE.md authorization records the specific consent to override the default, which is the pattern for repo-specific policy deviations.

**Why collapse approve-with-suggestions?** In practice every PR shipped through the loop with an `approve-with-suggestions` verdict either (a) had the suggestions silently never acted on, introducing drift, or (b) triggered a back-and-forth about "are the nits blocking or not?" that burned cycles. Removing the middle verdict forces reviewers to decide explicitly: if a finding is worth writing, it's worth blocking on; if it isn't blocking, don't write it. This tightened reviewer discipline as a side effect.

**Why smoke-fail routes to implementer instead of bug-hunter by default?** Statistically, a smoke failure surfaced after an implementer's push is caused by that implementer's diff in the vast majority of cases (this is literally what the retry-after-cycle retry filters for — flake vs regression). Routing to bug-hunter by default would file a new issue every time and make the failing PR wait for a separate fix cycle, which is exactly the friction the loop exists to remove. Bug-hunter is the **exception path** for the rare pre-existing fail, invoked by the implementer when they verify via `git diff` that their change doesn't touch the failing code path.

**Alternatives rejected**: (a) "user merges manually" — per-PR user ceremony, defeats the automation; (b) "auto-merge on any reviewer verdict" — breaks rule 1, allows suggestions to rot; (c) "confine auto-merge to a specific label like `auto-merge-ok`" — adds manual step without meaningful safety gain when CI + reviewer are already gates.

## Consequences

- Every PR now has a single end-to-end path: `do #N` → implementer → smoke-tester → reviewer → merge. Zero questions in the happy path. Ceremony budget recovered, estimated ~60% reduction in per-PR user input.
- Reviewer's severity distinction is now about *which finding types exist*, not *whether they block* — all severities block equally. This led to explicit guidance in `reviewer.md` that reviewers must suppress nits they wouldn't route through implementer, rather than downgrading them in the verdict.
- Implementer owns the smoke-fail fix loop directly — they read Playwright traces, diagnose regression-vs-pre-existing, and fix on the same branch. This broadens implementer's required skill set slightly (trace-reading is new) but keeps the PR-as-atomic-unit invariant.
- `approve-with-suggestions` removed from reviewer response format. Any PR history that carries this verdict was reclassified before merge.
- External PRs (dependabot etc.) remain outside the authorization scope. When the team grows and external PRs appear, the user-merge-gate path is still codified.
- Loop breakage modes are now well-enumerated: CI red, conversation-resolution block, rebase conflict, pre-existing smoke fail, agent-reported blocker. Each has a documented escalation; in practice the loop has stalled only on the `postgres:5432` host DNS trap (pre-push hook false positive), which motivated issues #46/#47/#67 to close that gap.
- `docs/loop.md` is the grep-friendly quick-reference; `CLAUDE.md` "Pre-merge review loop" is canonical. Both must be kept in sync when the authorization scope changes.
