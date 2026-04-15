# ADR-0003: Link Telegram Accounts via a One-Time Code from the Web UI

**Status:** Accepted
**Date:** 2026-04-15

## Context

The bot needs to identify which application user is sending a message. Telegram hands every update a `from.id` (the `tg_user_id`) and optionally `from.username`. The question is how we bind that to a row in our `users` table.

Candidates:

1. **Trust the first `/start` from a given `tg_user_id`** — whoever DMs the bot first claims that Telegram account.
2. **Telegram Login Widget on the web** — Telegram signs a payload, web verifies, binds.
3. **One-time code issued by the web UI** — user logs into web, generates a 6-digit code, sends `/start <code>` to the bot.

## Decision

Option 3. User logs into the web UI with username + password (the only auth path — see plan: no email, no OAuth). In their profile they press "Link Telegram" and receive a 6-digit code valid for 15 minutes, along with a `t.me/<bot>?start=<code>` deep link. They send `/start <code>` to the bot; on success we set `users.tg_user_id = from.id` and invalidate the code.

Until a user is linked, the bot refuses every command except `/start`. Anonymous messages get a one-line reply explaining how to link.

## Reasoning

- **Trust anchor is the web password, not a Telegram number.** Someone who can DM the bot is not automatically someone who has access to our app — without this separation, a known `tg_user_id` leak would become an account takeover.
- **Option 1 is unsafe at the moment a user account exists without a link** — any stranger who knows or guesses the username can claim the Telegram binding.
- **Option 2** requires a bot domain in BotFather, TLS, and the Login Widget's specific payload verification. It's a reasonable alternative but creates two auth flows (password + Telegram) that we'd have to keep consistent. Since we already need web auth for users who don't use Telegram day-to-day, adding a second login path is scope we don't need.
- **One-time code is standard practice** (GitLab, GitHub, Slack all do some variant), short-lived, single-use, revocable. Good security/UX balance.
- The code lives in a `tg_link_codes` table with `(user_id, code, expires_at, consumed_at)`. Easy to reason about, easy to audit.

## Consequences

- **`users.tg_user_id` is immutable once set**, changing it requires an "Unlink Telegram" action (which clears the field) followed by a new `/start <code>`. We never rewrite `tg_user_id` from inside a `/start` handler without the code ceremony — a bot handler that does so is a bug.
- **Bot handlers must early-return with a "link first" message** for any command from an unlinked `tg_user_id`. This is the single most important line of code in `app/bot/middlewares/` — add a unit test that regresses it.
- **Code generation is rate-limited per user** (at most one active code at a time; new requests invalidate prior codes). Otherwise brute-forcing a 6-digit code becomes attractive.
- **Code format** is 6 decimal digits (~20 bits). With 15-minute expiry and rate limits (e.g. 5 attempts per hour per chat), brute force is not a practical threat. If it becomes one, bump to 8 digits or alphanumeric — trivial change.
- **Username lookup for @mentions** can use `users.tg_username` but that field is advisory; `tg_user_id` is the authoritative key.
