#!/usr/bin/env bash
# test-no-verify-guard.sh — black-box test for scripts/pre-push-main-guard.sh.
#
# Builds a throwaway git repo in a temp dir, crafts two commits, and invokes
# the guard directly with synthetic env vars (the ones pre-commit exports
# for pre-push hooks). Asserts:
#
#   1. Docs-only diff targeting refs/heads/main → exit 0 (allowed).
#   2. Code-change diff targeting refs/heads/main → exit 1 (blocked).
#   3. Code-change diff targeting a feature branch → exit 0 (unrelated).
#   4. Mixed docs + code diff targeting main → exit 1 (blocked, hostile).
#   5. New-branch push (from_ref all zeros) targeting main → exit 0 (noop).
#
# This script is the regression gate for the guard's policy. Run manually
# or from CI. It does NOT require pre-commit or the main repo's venv — it
# only needs `git` and `bash` on PATH. By design it never touches the real
# working tree.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GUARD="${REPO_ROOT}/scripts/pre-push-main-guard.sh"

if [[ ! -x "${GUARD}" ]]; then
  echo "FAIL: guard script not executable at ${GUARD}" >&2
  exit 2
fi

TMP="$(mktemp -d -t pre-push-guard-test.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

cd "${TMP}"
git init -q -b main .
git -c user.email=t@t -c user.name=t commit -q --allow-empty -m "root"

# Seed a "remote" tip that later rounds compare against.
git -c user.email=t@t -c user.name=t commit -q --allow-empty -m "remote-tip"
remote_sha="$(git rev-parse HEAD)"

pass=0
fail=0

# Run the guard with specific env. Capture exit code without set -e tripping.
run_guard() {
  local remote_branch="$1" from_ref="$2" to_ref="$3"
  set +e
  PRE_COMMIT_REMOTE_BRANCH="${remote_branch}" \
  PRE_COMMIT_FROM_REF="${from_ref}" \
  PRE_COMMIT_TO_REF="${to_ref}" \
    bash "${GUARD}" >/dev/null 2>&1
  local rc=$?
  set -e
  echo "${rc}"
}

assert_exit() {
  local label="$1" expected="$2" got="$3"
  if [[ "${got}" == "${expected}" ]]; then
    echo "PASS: ${label}"
    pass=$((pass + 1))
  else
    echo "FAIL: ${label} — expected exit ${expected}, got ${got}" >&2
    fail=$((fail + 1))
  fi
}

# ─ Case 1: docs-only diff targeting main → allowed ──────────────────────
mkdir -p docs
echo "doc content" > docs/note.md
echo "root-level doc" > README.md
git add docs/note.md README.md
git -c user.email=t@t -c user.name=t commit -q -m "docs-only"
docs_sha="$(git rev-parse HEAD)"
got="$(run_guard "refs/heads/main" "${remote_sha}" "${docs_sha}")"
assert_exit "docs-only push to main allowed" "0" "${got}"

git reset -q --hard "${remote_sha}"

# ─ Case 2: code-change diff targeting main → blocked ────────────────────
mkdir -p backend/app
echo "print('hi')" > backend/app/thing.py
git add backend/app/thing.py
git -c user.email=t@t -c user.name=t commit -q -m "code change"
code_sha="$(git rev-parse HEAD)"
got="$(run_guard "refs/heads/main" "${remote_sha}" "${code_sha}")"
assert_exit "code push to main blocked" "1" "${got}"

git reset -q --hard "${remote_sha}"

# ─ Case 3: code-change diff targeting a feature branch → allowed ────────
mkdir -p backend/app
echo "print('bye')" > backend/app/thing2.py
git add backend/app/thing2.py
git -c user.email=t@t -c user.name=t commit -q -m "feature code"
feat_sha="$(git rev-parse HEAD)"
got="$(run_guard "refs/heads/issue-68-pre-push-main-docs-only" "${remote_sha}" "${feat_sha}")"
assert_exit "code push to feature branch allowed" "0" "${got}"

git reset -q --hard "${remote_sha}"

# ─ Case 4: mixed docs + code diff targeting main → blocked ──────────────
mkdir -p backend/app docs
echo "new doc" > docs/another.md
echo "def f(): pass" > backend/app/mixed.py
git add docs/another.md backend/app/mixed.py
git -c user.email=t@t -c user.name=t commit -q -m "mixed"
mixed_sha="$(git rev-parse HEAD)"
got="$(run_guard "refs/heads/main" "${remote_sha}" "${mixed_sha}")"
assert_exit "mixed docs+code push to main blocked" "1" "${got}"

git reset -q --hard "${remote_sha}"

# ─ Case 5: new-branch push (from_ref all zeros) to main → allowed ───────
zero="0000000000000000000000000000000000000000"
got="$(run_guard "refs/heads/main" "${zero}" "${remote_sha}")"
assert_exit "brand-new main ref push allowed (no diff base)" "0" "${got}"

# ─ Summary ──────────────────────────────────────────────────────────────
echo
echo "results: ${pass} passed, ${fail} failed"
if (( fail > 0 )); then
  exit 1
fi
exit 0
