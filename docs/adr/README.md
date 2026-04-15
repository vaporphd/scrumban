# Architecture Decision Records

One file per decision. Sequential numbering, never reused. Status is `Proposed` → `Accepted` → `Superseded by NNNN`.

When a decision is reversed, don't delete — add a new ADR and mark the old one `Superseded`.

Format:

```md
# ADR-NNNN: Short title

**Status:** Proposed | Accepted | Superseded by NNNN
**Date:** YYYY-MM-DD

## Context
What problem are we solving? What constraints matter?

## Decision
The chosen answer, stated clearly.

## Reasoning
Why this and not the alternatives. List the alternatives you considered.

## Consequences
What does this decision force on us later? What breaks if we change it?
```

Write an ADR when a PR introduces a new subsystem, a new external dependency, or an architectural constraint that future contributors need to know about. See the `Hard gate` section in `CLAUDE.md`.
