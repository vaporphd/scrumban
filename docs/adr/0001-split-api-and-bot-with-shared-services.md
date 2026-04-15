# ADR-0001: Split API and Bot as Two Processes with a Shared Services Layer

**Status:** Accepted
**Date:** 2026-04-15

## Context

The product has two client surfaces — the Vue web UI (via HTTP + WebSocket) and Telegram (via aiogram). Both mutate the same domain: boards, tasks, comments, attachments. The question is how to organize the code so mutations from either surface stay consistent, auditable, and observable.

Three candidates:

1. **One process, api owns the bot** — FastAPI includes aiogram as a background task.
2. **Two processes, two codebases** — api and bot each have their own package, talk over HTTP or a queue.
3. **Two processes, one package** — api and bot are separate entrypoints on a shared codebase.

## Decision

Option 3. `backend/app/` contains a shared `services/` and `repositories/` layer. Two entrypoints:

- `app/main_api.py` → FastAPI
- `app/main_bot.py` → aiogram dispatcher

Both import from `app/services/*`. Handlers (HTTP or bot) are thin: validate input → call a service → translate the result back. Business logic lives in services, and nowhere else.

## Reasoning

- **No duplication.** The same `move_task(task_id, column_id, position, actor)` service is called whether a user dragged a card in the web UI or pressed "→ Done" in Telegram. Any rule we add (permission check, activity log, Redis event) runs exactly once, in one place.
- **Independent scaling and failure domains.** The bot polls/webhook loop and the HTTP server have different load patterns. A stuck handler in one doesn't stall the other. Deploy them as separate containers; restart independently.
- **Clean event bus.** Services publish to Redis pub/sub (see ADR-0002). Because every mutation goes through a service, every channel event is guaranteed, regardless of which surface triggered it.
- **Testing**: services are pure async Python taking a session + inputs. No FastAPI or aiogram in unit tests.
- **Not option 1** because the bot's long-polling loop and FastAPI's request handlers don't share a clean lifecycle, and a bot crash would take the API down.
- **Not option 2** because an HTTP call between them adds latency, an auth surface, and a deployment dependency, for a gain we don't need at this scale.

## Consequences

- The bot and api container images are built from the same `backend/` directory with different `CMD`. Any dependency change rebuilds both.
- A handler that accidentally does DB work directly (bypassing the service layer) is the single worst thing that can happen to this architecture — reviewers must push back hard on that. The rule is written into `CLAUDE.md`.
- Cross-cutting concerns (authz, rate limiting, activity log, Redis events) are implemented once in the service layer and apply uniformly.
- Integration tests need to exercise both a REST call and a bot handler to catch regressions where a new field is added in one surface but not the other. We accept this cost.
