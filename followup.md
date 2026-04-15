# Followup

## Status

Branch `main` green through Phase 1 issue #2: auth endpoints
(`POST /api/auth/{register,login,refresh}`, `GET /api/me`) + argon2
password hashing + HS256 JWT access tokens + opaque rotating refresh
tokens (ADR-0005) with transactional rotation and chain-revoke on
replay. Migration `fcecc869fd60` adds `refresh_tokens`. Minimum-viable
sanity tests cover happy paths and replay; full suite tracked in #4.

Phase 0 + Phase 1 issue #1 (User + TgLinkCode models, migration
`5130146827ca`) already merged. Quality-gate epic #11 (pre-commit +
pre-push + hardened CI + branch protection) in place. Agent
infrastructure (#13, #15) landed.

## Next

1. **Phase 1 — issue #3**: frontend Login/Register/Profile + Pinia auth
   store + 401-refresh interceptor. Consumes the endpoints from #2.
2. **Phase 1 — issue #4**: full auth test suite against the live
   Postgres CI service — transactional-refresh concurrency, expiry
   edges, 401-distinction, replay edges beyond the sanity tests.
3. **Phase 1 — separate ticket**: Telegram link-code endpoint +
   profile UI button. Intentionally out of #2.
