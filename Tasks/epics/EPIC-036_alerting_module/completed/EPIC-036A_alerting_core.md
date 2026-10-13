# EPIC-036A — Alerting core: a typed alert goes through a hub, an outbox and a worker to any channel

**Status:** ✅ Done (2026-10-13)
**Source:** the owner's approval of the alerting design, 2026-10-08 (N1, N2, N3, N5, N8), relayed by the coordinator session; design page https://claude.ai/artifact/Q6J7i4FCLEhHXZiQtruAm1.
**Risk:** 🟡 — a new module, a new durable store and a contract lifted out of `support`
**Complexity:** L — one module with five parts and a move of a contract; no UI and no real channel
**Epic:** [EPIC-036](../README.md)
**SPEC:** none yet; the journeys are added when 036B/036D land.
**Design:** [`DESIGN_2026-10-08_alerting_module.md`](../DESIGN_2026-10-08_alerting_module.md) (the design of record; the owner's page is a secondary reference). **Research:** [`RESEARCH_2026-10-08_alerting_lessons.md`](../RESEARCH_2026-10-08_alerting_lessons.md) §2, §3, §9 (and §1, §2 for the per-channel queue).
**Depends on:** None. Decision record: [`DECISION_2026-10-08_alerting_module.md`](../DECISION_2026-10-08_alerting_module.md).

---

## 1. Context and problem
`INotificationChannel.send(str)` (`src/core/contracts/i_notification_channel.py`) cannot carry a severity, a subject or a reason, so a channel cannot format, route or deduplicate. The Telegram channel does not retry and the only debounce is "same text as the last one" (`src/shell/notification_event_handler.py`). Nothing is persisted. `ISecretStore` is in `src/support/binance_gateway/contracts/i_secret_store.py` though more than one module now needs it. Cited lines from the design and a read on 2026-10-08; verify when the task starts (`execute-task`).

## 2. Acceptance criteria
- [x] **Module skeleton:** `src/modules/alerting/` (`contracts/`, `domain/`, `application/`, `adapters/`, `composition/`, `module.py`) is an `IExtension` like its siblings; the module-boundary guards pass with `alerting` importing `bots/contracts` and `trading/contracts` only and `bots` never importing `alerting`.
- [x] **Typed alert:** a frozen `Alert` (kind, severity, subject, title, detail, at, dedup key); `AlertSubject` (scope BOT / VENUE / APP, bot id, bot name, bot kind, venue, symbol); `Severity` (CRITICAL, WARNING, INFO); `AlertKind` with at least `BOT_HALTED`, `BOT_ERROR`, `STOP_LOSS_HIT`, `TAKE_PROFIT_HIT`, `PRICE_FEED_STALE`, `USER_STREAM_DOWN`, `KEY_REJECTED`, `STORAGE_FAILURE`, **`STOP_FAILED`**, `RATE_LIMITED`, `RANGE_EXIT`, `APP_FAILURE`, `HEARTBEAT`, `DAILY_SUMMARY`, `CHANNEL_FAILING`. Each kind has one fixed severity default and one fixed alert group (the groups the Options matrix shows).
- [x] **Channel contract** (as built: `deliver(alert, loudness)`, because loudness belongs to the route cell; see the notes): `IAlertChannel.deliver(alert) -> DeliveryResult` with `ok`, `retry_after`, `permanent`, `reason`; it **never raises**; a channel that does is contained by the worker and reported as a failed delivery.
- [x] **AlertHub** (`publish(alert)`): deduplicates by key (a repeat updates one record and increments a counter, with a window per severity: CRITICAL 1 min, WARNING 15 min); coalesces alerts of one kind and venue in a 10 s window into one grouped alert listing the bots; **inhibits** (a venue-down alert suppresses per-bot feed-stale alerts of that venue, which survive only as a count); sends a **recovery** alert when the condition clears; applies the routes.
- [x] **Routing:** a route cell is `(alert group, channel)` with a loudness of **loud / silent / off** (N4 defaults: CRITICAL loud, WARNING silent, INFO silent); a per-bot setting **On / Critical only / Off** (N5); quiet hours hold INFO and WARNING and release them as one summary, CRITICAL always goes; **CRITICAL goes to two channels** when two or more are enabled (N8).
- [x] **Outbox (N2):** a SQLite file under `<data root>/state/`, behind `IOutbox` (`enqueue`, `due`, `mark`, `history`); alerts and per-channel deliveries survive a restart; an alert older than 24 h is marked **expired** and never sent.
- [x] **DeliveryWorker:** a background thread (never the bot's or the UI's thread); a **queue per channel**, so a slow channel delays no other; a **priority queue, CRITICAL first**; when the queue is bounded and full, INFO is dropped before WARNING and CRITICAL is never dropped; `retry_after` is honoured and never retried earlier; a bounded number of attempts with backoff, then the delivery is **failed** and `CHANNEL_FAILING` is raised through the remaining channels; a CRITICAL whose channel answers `retry_after` > 5 min **fails over** to another enabled channel.
- [ ] **Moved to EPIC-038E (owner, 2026-10-13); not delivered by this task.** **`ISecretStore` lifted** to `src/core/contracts/` (N3) with its `SecretStoreUnavailableError`; every importer is updated; where the keyring adapter lives (decision O2) is recorded here. No secret is in `AlertSettings`; a channel reads its secret by name when it sends.
- [x] **A second channel needs no application change:** a `FakeChannel` is registered by composition alone.
- [x] A bot or UI thread is never blocked by a failing, slow or rate-limited channel.

## 3. Design
Hexagonal ports and adapters (`architecture-rule.md`); Bounded Context (N1); the **transactional outbox** pattern for N2 (an alert is persisted before any send is attempted, the worker reads from the store); the project's `IBotStore`/atomic-write precedent for SQLite handling, surveyed before inventing (`CONSTITUTION.md` P5). Alert groups and kinds are code constants: a new kind is one line in one group. `IAlertChannel` is the `INotificationChannel` seam extended (BOT-018), not a parallel port; whether it is a `Protocol` or an `ABC` follows `architecture-rule.md` §2.1 (a QObject channel forces a `Protocol`, a plain adapter does not). The clock and the sleep are injected (`IMonotonicClock`, `IBotTicker` from `EPIC-035A` are the precedent) so no test sleeps. Open question O2: `KeyringSecretStore` is at `modules/trading/adapters/binance/mainnet/keyring_secret_store.py`; `alerting` may not import it, so it moves with the contract or a second keyring adapter is not written — decide and record.

## 3a. Reuse
Checked against `.claude/rules/capabilities.md` and `src/` on `master-warrior` `93ff7d0`, 2026-10-13. No UI need.
| Need | Checked | Result |
| :--- | :--- | :--- |
| A channel port | `INotificationChannel` (`core/contracts/i_notification_channel.py`) | **extended, not paralleled**: `IAlertChannel` takes a typed `Alert` and answers a `DeliveryResult`. The old port, `TelegramNotificationChannel` and `NotificationEventHandler` stay untouched: `EPIC-036B` replaces the handler, `EPIC-036C` moves Telegram |
| A durable queue | `src/infrastructure/persistence` (a symbol cache only); `bots`' `JsonBotStore` (one JSON file per bot); `market_data`'s SQLAlchemy models | `not used because` none can claim "the due deliveries of one channel, CRITICAL first" and the SQLAlchemy models are `market_data`'s own; stdlib `sqlite3` under `data_root()/state/`, so no dependency changes |
| Where runtime data lives | catalog: `data_root` | used: `state/alerts.sqlite3` |
| A periodic job | `Scheduler.every(...).do(...)` (Engine), as `operations` uses it | `not used because` every scheduled run publishes `runtime.tasks.started` / `.completed` on the event bus, so a one-second job put two events a second into the Developer event log and failed `test_workbench_conformance` (`columns_shown_whole`, CI run 38335428063). The grouping and quiet-hours flush runs on a housekeeping thread of `ThreadedDeliveryHost`; the lanes are threads too, because a lane blocks inside a channel and a scheduler tick must not |
| A clock | `bots`' `IBotClock` / `IMonotonicClock`; `operations`' `IOperationsClock` | `not used because` the first two are `bots`' contracts and `operations` may be depended on by none (`test_no_module_depends_on_operations.py`); `IAlertClock` is the same shape with a verified fake and a contract suite |
| The event bus | `IEventBus` | `not used here`: subscribing to `bots` and `trading` events is `EPIC-036B` |
| A health fact | `IOperationsRegistry.declare_health` | used: section `alerting`, see the notes |
| A read-only copy must not write | `IInstanceAccess.read_only`, as `operations` does | used |
| A secret | `ISecretStore` | `not imported`: no channel ships in this task. N3 is delivered by `EPIC-038E` (owner decision 2026-10-13); this task neither moves nor copies it |
| A capability entry | `Capability:` block | `not added`: the first user of `IAlertPublisher` is `EPIC-036B`; the block lands with it so the catalog row names a real user |

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/` (new) | Module skeleton, `Alert` types, `IAlertChannel`, `DeliveryResult`, `AlertHub`, `AlertSettings`/`AlertRoute`, `IOutbox` + SQLite adapter, `DeliveryWorker`, `FakeChannel` for tests |
| `src/core/contracts/i_secret_store.py` | **Moved to EPIC-038E (owner, 2026-10-13).** The lifted contract |
| `src/support/binance_gateway/contracts/i_secret_store.py` and the importers under `modules/trading/` and `support/binance_gateway/` | **Moved to EPIC-038E (owner, 2026-10-13).** Import from the new place |
| `Docs/HLD/` (modules table) | `alerting` listed as a bounded context |
| `tests/unit/architecture/` allowlists | None needed: the module imports no other module, so no allowlist or baseline changed |

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

Run 2026-10-13 on branch `claude/epic-036a-alerting-core`; results in the notes below.

## Implementation notes (written when done)
Written 2026-10-13 on `claude/epic-036a-alerting-core` from `master-warrior` `93ff7d0`. Engine at the pinned `f4ef582`, untouched. No dependency, `pyproject.toml` or settings change.

**What exists.** `src/modules/alerting/`: `domain/` (`Alert`, `AlertSubject`, `Severity`, `AlertKind` with `alert_catalog.py` giving each kind one group, one default severity and one label; `AlertSettings`, `AlertRoute`, `QuietHours`, `Loudness`, `BotAlertMode`, `DeliveryState`, `NoisePolicy`, `DeliveryPolicy`); `contracts/` (`IAlertChannel`, `DeliveryResult`, `IAlertPublisher`, `IOutbox`, five narrow ports, and the verified fakes `FakeAlertClock` and `FakeAlertChannel`); `application/` (`AlertHub`, `AlertRouter`, `AlertDeduplicator`, `AlertCoalescer`, `ConditionBook`, `QuietHoursHold`, `DeliveryAdmission`, `ChannelDelivery`, `AlertingHealthContributor`); `adapters/` (`SqliteOutbox`, `ThreadedDeliveryHost`, `WakeSignal`, in-memory settings, clock, catalog, null publisher); `composition/` (`alerting_bindings.py`, `channel_bindings.py`); `module.py`. `AlertingModule` is listed in `shell/modules.py` before `operations`. `boot()` starts the lanes and the housekeeping thread; `shutdown()` stops them and closes the outbox.

**Path of an alert.** `publish` (caller's thread; writes the outbox, calls no channel) -> inhibited? -> deduplicated? -> held for quiet hours? -> grouped? -> routed -> admitted to each channel's bounded queue -> `enqueue`. A lane per channel (`ThreadedDeliveryHost`) runs `ChannelDelivery.run_due`: expire, take the due delivery with the highest severity, call the channel, record the outcome. A wait (`retry_after`, or the back-off) pauses the whole channel; the worker pass takes an injected clock and no thread, which is why no test sleeps.

**Decisions taken, and why.**
- **`deliver(alert, loudness)`, not `deliver(alert)`.** The criterion's signature has no way to say "silently"; loudness belongs to the route cell (group x channel), not to the event, so it travels beside the alert instead of inside the frozen `Alert`.
- **N8 and fail-over override an *off* cell for CRITICAL (fail-over also on exhaustion, on refusal, and when a longer-than-five-minute wait holds the channel while a CRITICAL waits); a disabled channel and a bot set to Off do not.** A CRITICAL that fewer than two channels would hear is lifted to two (loud) from the enabled channels. The matrix cannot remove the cover for a push that never arrives; the owner's explicit "disable this channel" and N5's confirmed "Off" for a bot still win.
- **Dedup, grouping, inhibition and recovery state is in memory.** After a restart a repeat is a new record (the owner hears it twice, never zero times: `test_dedup_windows_do_not_survive_a_restart`), and nothing recovers until the source raises the condition again. The alerts, their counts and their deliveries are durable.
- **An inhibitor lapses after one hour** (`NoisePolicy.inhibition_ttl`), so a source that never clears a venue-down alert cannot silence the venue's bots for good.
- **Held (quiet-hours) alerts are recorded in the outbox when held** (history) and leave as one `DAILY_SUMMARY`; the summary's list of held alerts is in memory, so a restart inside quiet hours loses the summary, not the record. `EPIC-036E` owns the *daily* summary and the heartbeat.
- **A wait the platform asks for is not a failure (review question 6a).** An answer with `retry_after` pauses the channel and sets the delivery's next time but does not use an attempt, so a burst of 429s never raises `CHANNEL_FAILING`; the 24 h expiry bounds how long a wait is honoured (`test_endless_rate_limiting_ends_at_the_expiry_not_at_a_failure`). `attempts` counts real tries that did not work.
- **The channel's wait survives a restart (6b).** The worker reads `IOutbox.retry_horizon(channel)`, the latest wait among the channel's open RETRYING rows, the first time it looks at a channel (`test_a_wait_the_channel_asked_for_survives_a_restart`). A real failure's back-off is part of that horizon, as it is part of the in-memory pause.
- **Bounded queue per channel (`DeliveryPolicy.capacity`, 200).** A full queue sheds the oldest delivery of the lowest severity below the newcomer; with none below, a newcomer under CRITICAL is recorded `DROPPED` (never silently lost), and a CRITICAL is admitted beyond the bound.
- **Finished alerts are purged after 30 days** (hourly, from the flush tick) so the file cannot grow without bound on an unattended host.
- **Settings are in memory** (`InMemoryAlertSettings`, N4's defaults). Persistence belongs to the Options page (`EPIC-036D`); `IAlertSettingsSource` is the seam it replaces.
- **No `Scheduler` job.** The flush every second is a housekeeping thread in `ThreadedDeliveryHost` (`test_the_periodic_flush_puts_nothing_on_the_event_bus` locks it against the real graph). Found by CI on the first head: the scheduler's per-run bus events flooded the Developer event log.
- **Recovery clears the slate.** `condition_cleared` forgets the key's dedup entry, so a condition that comes back after "Recovered" is sent again and the next clear recovers again; a grouped feed-stale alert is booked with its member keys (`ConditionBook.adopt`) and recovers when the last member clears.
- **A read-only copy** (`EPIC-035H`) opens no outbox and starts no lane; `IAlertPublisher` resolves to a null publisher there.
- **Health (`declare_health`, section `alerting`):** `undelivered` and `oldest_undelivered_age_s`; `status: degraded` when the oldest has waited over 15 minutes. One line of `tests/integration/modules/operations/test_the_host_writes_its_snapshot.py` (the expected section list) gained `alerting`.
- **`ISecretStore` / N3 / open question O2:** not touched here (owner decision 2026-10-13). No channel in this task reads a secret.

**Verification, on the checked tree.**
- Red first: the new test files failed to import (`ModuleNotFoundError: ...modules.alerting`) before any source existed.
- `tests/unit/modules/alerting`: 111 tests; `tests/integration/modules/alerting`: 6 tests (the composed app delivers to a declared channel, delivers after a restart, leaves no `alerting-*` thread after `stop`, publishes the health section, and a read-only copy writes no outbox and starts no lane).
- Mutation checks (each turned a test red, the code restored after): N8 floor, dedup window, channel pause, fail-over threshold, severity ordering of `due`, shedding bound, expiry boundary, inhibition TTL, wake-up on enqueue, single-alert group, "channel failing" once. One mutant survived at first (the channel pause) because the test ran one pass; the test now runs a second pass inside the wait.
- `scripts/ci-local.ps1 -SkipTests`: PASS (ruff, format, mypy, reference check). `pytest tests/unit/architecture -q`: all pass after one fix (`ANN401` on an untyped `register(context)`).
- `pytest tests/integration -q` (whole tier, local): 534 passed, 3 skipped, 1 failed. The failure, `test_workbench_conformance[True-1024x700]` (the Backtest mode needs 706 px of height in a 700 px window), fails identically on a clean `master-warrior` `93ff7d0` worktree: a font-metric difference of this container, not this change. `tests/sanity`: 49 passed (the real composition boots, headless boot without PySide6 included).
- `ci-local.ps1 -Full` is GitHub Actions' to run on the PR head.

**Review round 1 (PR #472, reviewer comment on `6a5dce4`, CI run 38335428063).** CI: the Developer event log was widened by the scheduler's per-run bus events (fixed: no `Scheduler` job); the Log Scan hits were the `'bots'` health warning that the UI fixture's fake dispatcher also raises on `93ff7d0`, printed only because a failing test shows its captured log. Review findings 1-6 fixed with red-first tests; the mutants that survived (the `_failing` guard, the 5 min boundary, and two more found while fixing) are now killed. Two lines the fix first added turned out to be dead code (the recovery key is never remembered, the group key is never looked up by dedup) and were removed.

**Review round 2.** A feed-stale *recovery* entered the 10 s grouping window and came out of `_group` as a new, non-recovery "Price feed stale: N bots" alert, announcing an outage as the feeds came back. `AlertCoalescer.wants` now refuses a recovery (`test_feeds_coming_back_are_never_reported_as_a_new_outage`, red first, mutant killed). `master-warrior` `012b5ca` (BUG-199) is merged in; two integration tests that asserted "no `alerting-*` thread in the process" now compare against a snapshot taken before boot, because the sanity tier keeps its own app booted.

**Not verified.** Nothing ran against a real channel or network. "Restart" is the outbox closed and reopened on the same file, and the app stopped and booted again in-process; no process was killed mid-write. The Windows behaviour of SQLite in WAL mode was not exercised. The lanes are tested with fakes; a soak with a real slow channel is `EPIC-036C`'s.

**Open for the neighbours.** `EPIC-036B`: the sources call `IAlertPublisher.publish` / `condition_cleared`, add `bots` and `trading` to `AlertingModule.dependencies`, add the first `Capability:` block, and decide the toast channel's path. `EPIC-036C`: append `AlertChannelDescriptor`s to `composition/channel_bindings.py`. `EPIC-036D`: replace `InMemoryAlertSettings` and read `IOutbox.history`. `EPIC-036E`: heartbeat and the daily summary through `IAlertPublisher`.

## Resume
Done. The only unchecked criterion is the `ISecretStore` lift, delivered by `EPIC-038E`.
