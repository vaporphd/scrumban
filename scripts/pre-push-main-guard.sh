#!/usr/bin/env bash
# pre-push-main-guard.sh — refuse direct pushes to `main` unless the diff is
# pure docs.
#
# Background: Alex's solo-admin privilege lets direct-to-main pushes bypass
# branch protection. That's occasionally useful for one-line doc fixes but
# dangerous for code — it skips PR review, smoke-tester, and the reviewer
# loop. This hook narrows the hole to docs-only diffs. Everything else has
# to go through a PR.
#
# Note on `--no-verify`: git's `--no-verify` skips client-side hooks
# entirely, so no hook can "block --no-verify". This hook enforces the
# policy on ordinary pushes; `--no-verify` remains the user's authorized
# emergency override (CLAUDE.md: "Bypass via `--no-verify` is for
# emergencies"). Branch-protection rulesets on GitHub are the only place
# to enforce this server-side — out of scope here.
#
# Input contract (pre-commit pre-push hook env vars):
#   PRE_COMMIT_REMOTE_BRANCH — remote ref being pushed to (e.g.
#                              refs/heads/main)
#   PRE_COMMIT_FROM_REF      — remote SHA (what's currently on the remote
#                              for this ref; 0{40} if new branch)
#   PRE_COMMIT_TO_REF        — local SHA being pushed
#
# Exit:
#   0 — push allowed (not targeting main, OR diff is docs-only)
#   1 — push refused (code-change push to main)
#
# Docs-only means every changed path matches one of:
#   - docs/**
#   - thoughts/**           (gitignored today, but belt-and-braces)
#   - *.md at repo root     (README.md, followup.md, CLAUDE.md, …)
#   - tasks/**              (plan + lessons files)

set -euo pipefail

remote_branch="${PRE_COMMIT_REMOTE_BRANCH:-}"
from_ref="${PRE_COMMIT_FROM_REF:-}"
to_ref="${PRE_COMMIT_TO_REF:-}"

# Pushing somewhere other than main — not our concern.
if [[ "${remote_branch}" != "refs/heads/main" ]]; then
  exit 0
fi

# Brand-new `main` on a fresh remote — nothing to diff against. Don't
# block; this is first-push territory and the repo already exists.
zero_sha="0000000000000000000000000000000000000000"
if [[ "${from_ref}" == "${zero_sha}" || -z "${from_ref}" ]]; then
  exit 0
fi

# List paths changed between the remote tip and the local tip.
changed_paths="$(git diff --name-only "${from_ref}..${to_ref}")"

# Empty diff = no-op push (force-push of same tip, etc.). Allow.
if [[ -z "${changed_paths}" ]]; then
  exit 0
fi

# Path predicate: docs-only allow-list.
is_docs_path() {
  local path="$1"
  case "${path}" in
    docs/*)     return 0 ;;
    thoughts/*) return 0 ;;
    tasks/*)    return 0 ;;
    *.md)       # only if there are NO slashes, i.e. repo root
      [[ "${path}" != */* ]] && return 0
      return 1
      ;;
  esac
  return 1
}

offenders=()
while IFS= read -r path; do
  [[ -z "${path}" ]] && continue
  if ! is_docs_path "${path}"; then
    offenders+=("${path}")
  fi
done <<< "${changed_paths}"

if (( ${#offenders[@]} > 0 )); then
  {
    echo
    echo "pre-push-main-guard: direct push to main refused."
    echo
    echo "The following files are outside the docs-only allow-list"
    echo "(docs/, thoughts/, tasks/, *.md at repo root):"
    echo
    for p in "${offenders[@]}"; do
      echo "  - ${p}"
    done
    echo
    echo "Code changes to main must go through a PR so they get smoke-tester +"
    echo "reviewer coverage. Push to a feature branch instead:"
    echo
    echo "    git checkout -b issue-N-<slug>"
    echo "    git push -u origin issue-N-<slug>"
    echo "    gh pr create"
    echo
    echo "If this is a genuine emergency and you need to bypass, git's own"
    echo "--no-verify flag skips all client hooks. Use sparingly; CLAUDE.md"
    echo "calls that out as emergencies-only."
    echo
  } >&2
  exit 1
fi

exit 0
