# ADR-0005: Opaque, Hashed, Rotating Refresh Tokens

**Status:** Accepted
**Date:** 2026-04-15

## Context

Phase 1 (issue #2) introduces the auth subsystem: register, login, refresh, `/me`, and a JWT-based `current_user` dependency. The plan in `tasks/todo.md` says "access + refresh JWT" but does not pin down what a refresh token actually is. The choice matters because it dictates whether we can revoke sessions, whether we can detect token theft, and what the DB schema looks like.

Access tokens are not in question: they are short-lived signed JWTs (HS256, `JWT__SECRET`) with `sub = user_id`, `iat`, `exp`. The only live decision is the refresh token.

Constraints that bound the choice:

- **Password-only auth** (ADR-0003 reaffirms this — no email, no OAuth). The refresh mechanism is the only session-extension path we have.
- **Bot + web share the same user record** but authenticate differently: web uses JWT, bot uses `tg_user_id` after the one-time-code ceremony. Refresh tokens apply to web only.
- **We want logout and "admin kill-switch"** on the roadmap (issue #2 body: "future: logout, admin kill-switch"). Both require revocation.
- **Team size is small** (a few dozen users). DB lookup per refresh is not a scaling concern.
- `argon2-cffi` and `python-jose` are already declared in `backend/pyproject.toml`; no new dependencies needed.

## Decision

Refresh tokens are **opaque random strings**, stored in the DB as a **SHA-256 hash** (never plaintext), **rotated on every use**, with **replay detection**.

Concrete shape:

1. Generate 32 bytes via `secrets.token_urlsafe(32)`. This is the only time the plaintext exists outside the client — it is returned in the login/refresh response and never stored.
2. Persist a `refresh_tokens` row with columns:
   - `id` (pk),
   - `user_id` (fk, indexed),
   - `token_hash` (CHAR(64), unique, indexed — hex SHA-256 of the plaintext),
   - `expires_at` (timestamptz),
   - `created_at` (timestamptz),
   - `revoked_at` (timestamptz, nullable) — set when the token is consumed or explicitly revoked,
   - `replaced_by_id` (fk to `refresh_tokens.id`, nullable) — set when rotation swaps this token for a successor.
3. On `POST /api/auth/refresh`:
   - Hash the incoming token, look it up.
   - If the row is missing → 401.
   - If `revoked_at IS NOT NULL` → **replay detected**. Revoke the entire chain for that `user_id` and return 401. (See Consequences for what "the chain" means.)
   - If `expires_at` is past → 401.
   - Otherwise: mark the row `revoked_at = now()`, insert a fresh row, set `replaced_by_id`, return the new access + refresh pair.
4. TTLs: access token 15 minutes, refresh token 30 days. Values live in `JWT__*` settings so they are tunable without code changes.

SHA-256 (not argon2) because the input is 256 bits of entropy — brute-forcing the preimage is already infeasible, and we do this lookup on every refresh. Argon2 is for low-entropy secrets (passwords).

## Reasoning

Three alternatives were considered.

**A. Self-encoded JWT refresh** — refresh token is itself a signed JWT with a longer `exp`.

- Pros: stateless, no DB lookup per refresh, symmetric with the access token (one code path).
- Cons: **cannot be revoked** without building a blocklist (which brings back the DB lookup, defeating the point). Logout becomes a lie — a stolen refresh JWT stays valid until `exp`. No replay detection. Admin kill-switch requires either rotating `JWT__SECRET` (nukes all sessions) or maintaining a revocation list.

**B. Opaque + hashed + rotating (chosen)** — this ADR.

- Pros: revocable by a single UPDATE. Rotation means a stolen token is valid for at most one refresh window — after the legitimate client refreshes, the attacker's copy is revoked. Replay detection: if a revoked token is presented again, we know the chain is compromised and nuke it. Logout is a straightforward revoke. Admin kill-switch is `UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = ?`.
- Cons: DB round-trip per refresh (acceptable at our scale). Chain-revocation logic needs to be right — sloppy implementation could revoke too aggressively (logging out innocent users) or not aggressively enough (letting an attacker stay in).

**C. Opaque + hashed + sliding TTL without rotation** — same storage, but the refresh endpoint just extends `expires_at` and returns the same token.

- Pros: simpler than B. Revocable like B.
- Cons: no replay detection. A stolen refresh token is valid for its full (sliding) lifetime with no signal to either party that theft occurred. Given we plan to carry this on phones and in browsers, rotation is cheap insurance.

**Why B over A**: revocation is on the roadmap, and building a JWT blocklist later is the worst of both worlds — stateful storage plus stateless verification with a cache-coherence problem. Start stateful, stay stateful.

**Why B over C**: rotation is essentially free once the table exists. The `replaced_by_id` column and the chain-revoke logic are ~20 lines. Detecting a replay is a real security win for a negligible cost.

**SHA-256 vs argon2 for `token_hash`**: argon2 is a memory-hard KDF designed to slow down attackers who have offline access to a password hash. It is the wrong tool for a 256-bit random secret — the entropy space is already unguessable, and argon2 would make every refresh cost ~100ms of CPU for no security gain. SHA-256 is the right primitive for this use case (same reasoning applies to session tokens in Django, Rails, etc.).

## Consequences

- **New table `refresh_tokens`** managed via Alembic. Adding this table is a schema change; removing it later means we lost revocation (see below).
- **The refresh endpoint MUST be transactional.** The sequence "lookup → revoke old → insert new" has to be atomic, otherwise a concurrent double-refresh races and either both succeed (breaks rotation) or both fail (user gets logged out). Use `SELECT ... FOR UPDATE` on the token row inside the transaction.
- **Chain revocation on replay**: when we detect a reused revoked token, we revoke every non-expired `refresh_token` row for that `user_id`. This logs the user out of every device. That is the right behavior — we have positive evidence of theft — but it is a user-visible consequence that must be documented in the auth service.
- **Clock skew matters**: `expires_at` uses the DB's clock; access token `exp` uses the API's clock. Keep both processes synchronized via NTP. If they drift, users see spurious 401s around the edges.
- **Cleanup job**: expired `refresh_tokens` rows accumulate forever without a sweeper. Phase 1 can defer this (low volume), but by Phase 3 we should have an APScheduler job in `app/bot/` (the scheduler process per CLAUDE.md) that deletes rows where `expires_at < now() - interval '7 days'`.
- **What breaks if we change our mind later?**
  - **Switch to JWT refresh (alternative A)**: we lose per-session revocation. We can drop the table only after explicitly accepting "logout doesn't really log out" or by maintaining a blocklist. Migration path is clean (new endpoint logic, keep the table dormant for a release, drop).
  - **Drop rotation, keep opaque (alternative C)**: trivially easy — stop creating the successor row, stop setting `replaced_by_id`. We lose replay detection. Reversible.
  - **Change the hash to argon2** or some other KDF: requires re-hashing existing tokens, which we can't do (we don't have the plaintext). We would have to force all users to log in again. Realistically this change is write-off-and-reissue, not a migration. Unlikely to be necessary.
- **Interaction with ADR-0003**: the Telegram linking flow is orthogonal. A logged-in user has a JWT + refresh token; linking Telegram does not produce or consume either. Revoking all refresh tokens (kill-switch) does NOT unlink Telegram — unlinking is its own operation. Keep the two concerns separated in the auth service.
- **Bot process does not need refresh tokens at all.** The bot authenticates users by `tg_user_id` lookup (ADR-0003), not by JWT. This table belongs to the web auth flow only.
