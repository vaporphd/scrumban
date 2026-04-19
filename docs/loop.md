# Pre-merge review loop — quick reference

How an issue becomes a merged PR under the autonomous loop. Read `CLAUDE.md` "Pre-merge review loop" for the canonical rules with authorizations and edge-case handling.

## Flow

```
"do #N"  OR  /loop auto-pick (lowest-numbered open issue)
  → implementer (branch, code, tests, Playwright spec per issue body, push, PR)
  → smoke-tester (if PR has Playwright spec — per 2026-04-19 that's every non-pure-infra PR)
      OR reviewer (pure infra / pure docs / agent-description / CI-only)
  → on smoke green → reviewer
  → on smoke fail → implementer (same branch, trace diagnosis, fix) → smoke-tester re-run
  → on reviewer approve (zero findings) → auto-merge
  → on reviewer changes-requested (any finding any severity) → implementer → reviewer re-run
  → DONE (no user question in the normal flow)
  → /loop mode: main session auto-picks next issue, repeats
```

## Metric

User input per PR in the normal flow: 1 word (the issue number / "go"). Down from ~3 questions per PR at session start.

## Key terms

- **Playwright spec mandate (2026-04-19)**: every PR — backend, frontend, full-stack — ships a Playwright spec. Backend uses `request` context under `frontend/tests/e2e/api/*.spec.ts`; frontend uses `page` context under `frontend/tests/e2e/*.spec.ts`. Rationale in `tasks/lessons.md`. Widens the smoke gate from "user-visible feature" to "any behavior change".
- **pure infra / docs**: CI workflows, Dockerfiles, pre-commit configs, agent descriptions, markdown docs, pure-test-only refactors. Only these are exempt from the smoke gate.
- **any finding**: one or more must-fix, should-fix, or nit in the reviewer's report. All three severities route identically (authorization 2026-04-17: "suggestions should be treated as a bug").
- **auto-merge**: `gh pr merge N --auto --squash --delete-branch`. GitHub waits for CI green and merges. Issue auto-closes via `Closes #N` in PR body.
- **/loop mode**: main session auto-picks the lowest-numbered open issue instead of waiting for `do #N`. See `CLAUDE.md` → "Automated /loop mode — issue pickup".

## Trigger phrases

The main session recognizes these as loop invocations without an explicit `/loop` slash command:

| You say                                    | Loop does                                         |
|--------------------------------------------|---------------------------------------------------|
| `do next task` / `take the next one`       | 1 PR end-to-end, then stop                        |
| `do next N tasks` / `take next 5`          | N PRs, N counts merged (not attempted)            |
| `do all next tasks` / `drain the queue`    | unbounded, stop only on queue-drain / blocker / interrupt |
| `/loop` (slash skill)                      | unbounded dynamic mode, self-pacing across wakeups |

Progress contract during a multi-PR run: one-line confirmation at start, one-line update between merges, explicit stop message with reason. No narration. See `CLAUDE.md` → "Trigger phrases" for canonical rules and edge cases.

## Exception paths

- **Pre-existing smoke fail** (not caused by this PR's diff): implementer escalates to `bug-hunter`; this PR pauses pending the pre-existing fix landing separately.
- **External PRs** (dependabot, outside contributors once team grows): auto-merge does NOT apply; user merge authorization still required.
- **Unresolvable rebase conflict**: escalate to user.

## Cross-references

- `CLAUDE.md` "Pre-merge review loop" — canonical rules.
- `.claude/agents/implementer.md` — agent that drives steps 1, 2 of the flow and handles re-engagement on findings.
- `.claude/agents/smoke-tester.md` — agent that drives the smoke-test step.
- `.claude/agents/reviewer.md` — agent that emits the verdict.
- `.claude/agents/bug-hunter.md` — exception-path agent for pre-existing regressions.
