# EPIC-026M — Trading events reach an operator who is not looking at the screen (delivers `BOT-018`)

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 6; ADR `❓ O4`;
[`BOT-018`](../../../completed/BOT-018_notifications_alerting.md) (2026-08, the user's own item);
the user (2026-09-20): *"hãy cho lô trình để có thể giao dịch thật"*.

> **2026-09-23 — `BOT-018` closed separately, not by this task.** Picked up as a standalone
> backlog item without cross-checking this epic first — a process gap this note exists to flag,
> not to paper over. What shipped: `NotificationEventHandler` (`src/shell/`) on
> `BulkSyncProgressEvent`/`UiActionFailedEvent`/`TaskFailed` — sync and UI/background failures,
> the events that exist *today* — fanning out to `UiToastNotificationChannel`
> (`src/presentation/ui/`) and `TelegramNotificationChannel` (`src/infrastructure/notifications/`,
> config-file token/chat-id via `IConfigReader`, "last message repeated" debounce). None of §2-§4
> below is satisfied by it: no `support/notifications/contracts/` port, no `TradingAlertSubscriber`,
> no env-first credential resolution, no 60 s count-collapsing debounce, no `alert-test` CLI — this
> epic's own trading events (`OrderFilledEvent`/`CircuitBreakerTrippedEvent`/Emergency Stop/stream
> watchdog) don't exist yet regardless. This task is **not** narrowed or closed by the above; when
> it starts, decide explicitly whether `TradingAlertSubscriber` fans into the existing
> `NotificationEventHandler`/`INotificationChannel` (extend) or a separate
> `support/notifications/` port is still right for this epic's stricter secrets/debounce/CLI
> requirements (rebuild) — don't assume either without re-reading both.
**Risk:** 🟡 — a new outbound channel; a token in a log or a crash in the sender are the failure
modes, both named in `BOT-018` §4.
**Complexity:** M — port, one channel, one subscriber, debounce, secrets handling.
**Epic:** [`EPIC-026`](../README.md)
**Depends on:** ADR `O4` (Telegram unless the user names another)

---

## 1. Context and problem

Every alarm this app can raise ends in the log or in the UI's log panel (`SignalLogHandler`,
`market_data/ui/signal_log_handler.py:8`). A dead user-data stream logs a line
(`futures_user_data_stream.py:119`), a blocked order publishes `LiveOrderBlockedEvent` to a panel,
a fill draws a marker. None of it reaches a phone. `BOT-018` specified the mechanism a month ago —
`INotificationChannel`, a handler on the event bus, Telegram, config-gated, debounced — and was
never started because nothing yet needed it. Stage 2's soak (`EPIC-026O`) is 14 unattended days;
it needs it.

## 2. Acceptance criteria

- [ ] `INotificationChannel` (port, `support/notifications/contracts/` — a support package: no
      business language, several modules use it, HLD C6) with `TelegramNotificationChannel` and
      a `LogNotificationChannel` used when nothing is configured.
- [ ] `TradingAlertSubscriber` (in `trading/application/`) maps these events to messages:
      `OrderFilledEvent`, `OrderRejectedEvent`, `LiveOrderBlockedEvent`,
      `CircuitBreakerTrippedEvent`, the Emergency Stop result, the stream watchdog's events
      (`EPIC-026N`), enable/disable. The message names venue, symbol, side, quantity, price and
      reason; never a key, never a full payload.
- [ ] Token and chat id resolve through the same env-first provider pattern as exchange
      credentials (`env_first_credentials_provider.py`), with venue-neutral names
      (`SEW_TELEGRAM_BOT_TOKEN`, `SEW_TELEGRAM_CHAT_ID`); `repr` masks; the four leak paths
      `EPIC-021B` checked are re-checked for the token.
- [ ] Sending runs on a worker with a 5 s timeout; a failure is one `WARNING` under
      `App.Notifications` and never propagates; identical messages within 60 s collapse into one
      with a count.
- [ ] `main.py alert-test` sends one message and prints the channel's answer.

## 3. Design

`BOT-018`'s design, applied as written, with two changes measured from today's tree: the port is
a support package (it did not exist when `BOT-018` was filed), and the trading events are the
first consumers rather than sync errors (those can follow, from `market_data`, as `BOT-018`
intended). `BOT-018` stays in `Tasks/backlog/` until this task closes, then moves to
`completed/` citing this file — one delivery, two records.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/support/notifications/contracts/i_notification_channel.py`, `notification.py` | Port, DTO |
| `src/support/notifications/adapters/{telegram,log}_channel.py` | Channels |
| `src/support/notifications/adapters/notification_credentials.py` | Env-first token resolution |
| `src/modules/trading/application/alerts/trading_alert_subscriber.py` | Event → message, debounce |
| `src/modules/trading/composition/adapter_bindings.py` | Bindings |
| `src/presentation/cli/alert_test_cmd.py` | `alert-test` |
| `tests/unit/support/notifications/…` | Channels from the interface; masking; timeout |
| `tests/unit/modules/trading/application/alerts/test_trading_alert_subscriber.py` | One message per event; debounce; no secrets in text |
| `Docs/VOCABULARY/README.md` | Row: **Alert channel** |
| ~~`Tasks/backlog/BOT-018_notifications_alerting.md` | Moves to `completed/` on close~~ — already moved 2026-09-23, separately (see the note above) |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Mapping | subscriber unit test | unit | each event → one message with the named fields |
| Debounce | unit | unit | 3 identical in 60 s → 1 with "×3" |
| Failure isolation | unit, channel raises | unit | `WARNING`, event handling continues |
| Secrets | unit: token in `repr`, in the message, in a log record | unit | masked everywhere |
| Real channel | `alert-test` with a real token | human | message received; pasted here |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
