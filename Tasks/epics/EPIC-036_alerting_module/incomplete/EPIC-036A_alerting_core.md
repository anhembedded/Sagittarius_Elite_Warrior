# EPIC-036A — Alerting core: a typed alert goes through a hub, an outbox and a worker to any channel

**Status:** 🔵 Planned — not started
**Source:** the owner's approval of the alerting design, 2026-10-08 (N1, N2, N3, N5, N8), relayed by the coordinator session; design page https://claude.ai/artifact/Q6J7i4FCLEhHXZiQtruAm1.
**Risk:** 🟡 — a new module, a new durable store and a contract lifted out of `support`
**Complexity:** L — one module with five parts and a move of a contract; no UI and no real channel
**Epic:** [EPIC-036](../README.md)
**SPEC:** none yet; the journeys are added when 036B/036D land.
**Depends on:** None. Decision record: [`DECISION_2026-10-08_alerting_module.md`](../DECISION_2026-10-08_alerting_module.md).

---

## 1. Context and problem
`INotificationChannel.send(str)` (`src/core/contracts/i_notification_channel.py`) cannot carry a severity, a subject or a reason, so a channel cannot format, route or deduplicate. The Telegram channel does not retry and the only debounce is "same text as the last one" (`src/shell/notification_event_handler.py`). Nothing is persisted. `ISecretStore` is in `src/support/binance_gateway/contracts/i_secret_store.py` though more than one module now needs it. Cited lines from the design and a read on 2026-10-08; verify when the task starts (`execute-task`).

## 2. Acceptance criteria
- [ ] **Module skeleton:** `src/modules/alerting/` (`contracts/`, `domain/`, `application/`, `adapters/`, `composition/`, `module.py`) is an `IExtension` like its siblings; the module-boundary guards pass with `alerting` importing `bots/contracts` and `trading/contracts` only and `bots` never importing `alerting`.
- [ ] **Typed alert:** a frozen `Alert` (kind, severity, subject, title, detail, at, dedup key); `AlertSubject` (scope BOT / VENUE / APP, bot id, bot name, bot kind, venue, symbol); `Severity` (CRITICAL, WARNING, INFO); `AlertKind` with at least `BOT_HALTED`, `BOT_ERROR`, `STOP_LOSS_HIT`, `TAKE_PROFIT_HIT`, `PRICE_FEED_STALE`, `USER_STREAM_DOWN`, `KEY_REJECTED`, `STORAGE_FAILURE`, **`STOP_FAILED`**, `RATE_LIMITED`, `RANGE_EXIT`, `APP_FAILURE`, `HEARTBEAT`, `DAILY_SUMMARY`, `CHANNEL_FAILING`. Each kind has one fixed severity default and one fixed alert group (the groups the Options matrix shows).
- [ ] **Channel contract:** `IAlertChannel.deliver(alert) -> DeliveryResult` with `ok`, `retry_after`, `permanent`, `reason`; it **never raises**; a channel that does is contained by the worker and reported as a failed delivery.
- [ ] **AlertHub** (`publish(alert)`): deduplicates by key (a repeat updates one record and increments a counter, with a window per severity: CRITICAL 1 min, WARNING 15 min); coalesces alerts of one kind and venue in a 10 s window into one grouped alert listing the bots; **inhibits** (a venue-down alert suppresses per-bot feed-stale alerts of that venue, which survive only as a count); sends a **recovery** alert when the condition clears; applies the routes.
- [ ] **Routing:** a route cell is `(alert group, channel)` with a loudness of **loud / silent / off** (N4 defaults: CRITICAL loud, WARNING silent, INFO silent); a per-bot setting **On / Critical only / Off** (N5); quiet hours hold INFO and WARNING and release them as one summary, CRITICAL always goes; **CRITICAL goes to two channels** when two or more are enabled (N8).
- [ ] **Outbox (N2):** a SQLite file under `<data root>/state/`, behind `IOutbox` (`enqueue`, `due`, `mark`, `history`); alerts and per-channel deliveries survive a restart; an alert older than 24 h is marked **expired** and never sent.
- [ ] **DeliveryWorker:** a background thread (never the bot's or the UI's thread); a **queue per channel**, so a slow channel delays no other; a **priority queue, CRITICAL first**; when the queue is bounded and full, INFO is dropped before WARNING and CRITICAL is never dropped; `retry_after` is honoured and never retried earlier; a bounded number of attempts with backoff, then the delivery is **failed** and `CHANNEL_FAILING` is raised through the remaining channels; a CRITICAL whose channel answers `retry_after` > 5 min **fails over** to another enabled channel.
- [ ] **`ISecretStore` lifted** to `src/core/contracts/` (N3) with its `SecretStoreUnavailableError`; every importer is updated; where the keyring adapter lives (decision O2) is recorded here. No secret is in `AlertSettings`; a channel reads its secret by name when it sends.
- [ ] **A second channel needs no application change:** a `FakeChannel` is registered by composition alone.
- [ ] A bot or UI thread is never blocked by a failing, slow or rate-limited channel.

## 3. Design
Hexagonal ports and adapters (`architecture-rule.md`); Bounded Context (N1); the **transactional outbox** pattern for N2 (an alert is persisted before any send is attempted, the worker reads from the store); the project's `IBotStore`/atomic-write precedent for SQLite handling, surveyed before inventing (`CONSTITUTION.md` P5). Alert groups and kinds are code constants: a new kind is one line in one group. `IAlertChannel` is the `INotificationChannel` seam extended (BOT-018), not a parallel port; whether it is a `Protocol` or an `ABC` follows `architecture-rule.md` §2.1 (a QObject channel forces a `Protocol`, a plain adapter does not). The clock and the sleep are injected (`IMonotonicClock`, `IBotTicker` from `EPIC-035A` are the precedent) so no test sleeps. Open question O2: `KeyringSecretStore` is at `modules/trading/adapters/binance/mainnet/keyring_secret_store.py`; `alerting` may not import it, so it moves with the contract or a second keyring adapter is not written — decide and record.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/` (new) | Module skeleton, `Alert` types, `IAlertChannel`, `DeliveryResult`, `AlertHub`, `AlertSettings`/`AlertRoute`, `IOutbox` + SQLite adapter, `DeliveryWorker`, `FakeChannel` for tests |
| `src/core/contracts/i_secret_store.py` | The lifted contract |
| `src/support/binance_gateway/contracts/i_secret_store.py` and the importers under `modules/trading/` and `support/binance_gateway/` | Import from the new place |
| `Docs/HLD/` (modules table) | `alerting` listed as a bounded context |
| `tests/unit/architecture/` allowlists | Entries for the new module's boundary, each with its reason |

## 5. Testing
Tier per `ci-rule.md` §2: unit and integration; every regression test shown red before the change.
- `test_an_alert_is_frozen_and_carries_its_subject`
- `test_every_alert_kind_has_one_group_and_one_default_severity`
- `test_a_repeat_updates_one_record_and_counts` (dedup by key, per-severity window)
- `test_alerts_of_one_kind_and_venue_coalesce_into_one_message`
- `test_a_venue_down_alert_inhibits_the_per_bot_feed_stale_alerts`
- `test_a_cleared_condition_sends_one_recovery_alert`
- `test_critical_goes_to_two_channels_when_two_are_enabled`
- `test_a_silent_cell_sends_silently_and_an_off_cell_sends_nothing`
- `test_a_bot_set_to_critical_only_drops_its_warnings`
- `test_the_outbox_survives_a_restart`
- `test_an_alert_older_than_24_hours_expires_and_is_not_sent`
- `test_critical_is_delivered_before_info`
- `test_info_is_dropped_before_critical_when_the_queue_is_full`
- `test_retry_after_is_never_retried_early` (fake clock)
- `test_a_channel_failing_after_its_attempts_raises_channel_failing_once`
- `test_critical_fails_over_when_retry_after_exceeds_five_minutes`
- `test_a_slow_channel_does_not_delay_another`
- `test_a_channel_that_raises_is_contained`
- `test_a_second_channel_needs_no_application_change` (the `FakeChannel`)
- `test_no_secret_is_stored_in_the_settings`
- the module-boundary and architecture guards (`pytest tests/unit/architecture -q`)

Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: `test_an_alert_is_frozen_and_carries_its_subject`, run red.
