# Pre-merge review loop — quick reference

How an issue becomes a merged PR under the autonomous loop. Read `CLAUDE.md` "Pre-merge review loop" for the canonical rules with authorizations and edge-case handling.

## Flow

```
"do #N"
  → implementer (branch, code, tests, push, PR)
  → smoke-tester (if user-visible feature) OR reviewer (if pure infra/docs)
  → on smoke green → reviewer
  → on smoke fail → implementer (same branch, trace diagnosis, fix) → smoke-tester re-run
  → on reviewer approve (zero findings) → auto-merge
  → on reviewer changes-requested (any finding any severity) → implementer → reviewer re-run
  → DONE (no user question in the normal flow)
```

## Metric

User input per PR in the normal flow: 1 word (the issue number / "go"). Down from ~3 questions per PR at session start.

## Key terms

- **user-visible feature**: new frontend view/route, new endpoint surfaced in the UI, new button/flow/state, new bot command visible to a user. Quick heuristic from `reviewer.md` "Smoke-test coverage gate": "could a regression here be caught by Playwright in a real browser?"
- **pure infra/docs**: pre-commit configs, CI workflows, Dockerfiles, markdown, backend-internal refactors with zero user observability. Exempt from the smoke-tester gate.
- **any finding**: one or more must-fix, should-fix, or nit in the reviewer's report. All three severities route identically through the loop (authorization 2026-04-17: "suggestions should be treated as a bug").
- **auto-merge**: `gh pr merge N --auto --squash --delete-branch`. GitHub waits for CI green and merges. Issue auto-closes via `Closes #N` in PR body.

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
