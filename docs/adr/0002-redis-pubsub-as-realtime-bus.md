# ADR-0002: Redis Pub/Sub as the Realtime Event Bus

**Status:** Accepted
**Date:** 2026-04-15

## Context

A mutation from Telegram (e.g. moving a task to "Done") must propagate to every open web client on the affected board in under a second. The same goes the other way — a web drag-and-drop must surface in `/tasks` bot output on refresh, and in @-mentions as a Telegram notification.

The api and bot are separate processes (ADR-0001), so the API's in-process WebSocket connection registry cannot see events produced by the bot without a cross-process signal.

Candidates:

1. **Poll the DB** — WS clients poll `/api/boards/{id}/events?since=X`, bot handlers do likewise. Simple, but bursty and high-latency.
2. **Postgres LISTEN/NOTIFY** — push via the DB itself.
3. **Redis pub/sub** — dedicated channel per board.
4. **Message broker (RabbitMQ/NATS)** — full durable events.

## Decision

Redis pub/sub. One channel per board: `board:{board_id}`. Event payload is a JSON-encoded domain event:

```json
{ "type": "task.moved", "board_id": 1, "task_id": 42, "from_column_id": 3, "to_column_id": 4, "position": 0.5, "actor_id": 7, "ts": "..." }
```

- Every service method that mutates a board-scoped entity publishes an event after its DB commit.
- The API runs a Redis subscriber per open WS connection's board; events are forwarded to the WS.
- The bot similarly subscribes for surfaces that need live updates (future: a "watching" mode).
- Notifications (e.g. @mentions → Telegram DM) are driven by the same events, consumed by a handler in the bot process.

## Reasoning

- **Decouples api and bot** without introducing an extra service. Redis is already in the stack for bot FSM storage and rate limiting.
- **Low latency, low ceremony.** Pub/sub has no persistence overhead; we don't need it because WS clients hold a snapshot and events are idempotent-ish (client merges by `task_id`).
- **Channel per board** keeps fan-out scoped; a user subscribed to one board doesn't see churn on another.
- **Not LISTEN/NOTIFY** because Postgres connections held by WS handlers are a scaling footgun, and the payload size limit (8 KiB) is tight once events grow.
- **Not a durable broker** because no event is critical enough to need at-least-once delivery. A missed event is recovered by the client reconnecting and re-fetching the board state.

## Consequences

- **At-most-once semantics.** Clients must reconcile by fetching on reconnect. The WS client code has a `resync` path — don't remove it.
- **Redis is a single point of failure for realtime**, but not for correctness — the DB is still authoritative. An outage degrades to "no live updates until reconnect," which is acceptable.
- **Event schema is a contract.** Changes need backward-compat (additive fields OK; removed/renamed fields not OK without a version bump). Keep event types in `app/realtime/events.py` as typed dataclasses/pydantic models.
- **Publishing lives in `services/`, never in routers or handlers.** Reviewers must enforce this — otherwise the bot and api will drift.
- **Ordering within a single channel is preserved by Redis**, which is enough for our UI: moves and updates for the same task arrive in order.
