# EPIC-036B — Alert sources: bots, streams and the system become typed alerts

**Status:** 🔵 Planned — not started
**Source:** the owner's approval of the alerting design, 2026-10-08 (N1), relayed by the coordinator session; supersedes the source half of [`EPIC-035K`](../../EPIC-035_spot_grid_unattended_safety/cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md).
**Risk:** 🟢 — reads events that exist; the one removal is a handler with a known set of triggers
**Complexity:** M
**Epic:** [EPIC-036](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task for the alerts a running bot raises.
**Depends on:** [EPIC-036A](EPIC-036A_alerting_core.md) (`Alert`, `AlertHub`).

---

## 1. Context and problem
Today only `NotificationEventHandler` (`src/shell/notification_event_handler.py`, wired at `src/shell/composition_root.py:262-270`) feeds the channels, and it hears three system failures. A bot halting, a stop-loss firing, a stuck STOPPING or a lost user-data stream produce a log line at most (`src/modules/bots/application/services/bot_run_state.py`, `notifying_bot_store.py`). `EPIC-035F` and `EPIC-035C` each recorded an alert that "waits for the alert module". Verify each source event on the running app when the task starts.

## 2. Acceptance criteria
- [ ] **`BotAlertSource`** listens to the bots' published events and snapshot query in `bots/contracts` and turns a state change plus its reason into an `Alert`: HALT → `BOT_HALTED`, ERROR → `BOT_ERROR`, a stop-loss or take-profit trigger → `STOP_LOSS_HIT` / `TAKE_PROFIT_HIT`, a Stop or stop-loss that does not complete, or leaves orders or balance, → **`STOP_FAILED`** (CRITICAL), the storage pause → `STORAGE_FAILURE`, a revoked key → `KEY_REJECTED`, a rate-limit pause → `RATE_LIMITED`, a price leaving the range → `RANGE_EXIT` (once per exit, re-armed on return; the source is `BotRangeChangedEvent` in `bots/contracts/events/`, published by `EPIC-035L` once per change of place, `INSIDE` being the return). A bot's return to RUNNING raises the **recovery** alert.
- [ ] A kind of bot that adds a reason of its own needs no change in `alerting`: the generic state and reason map to a kind; the kind-specific reason goes in `detail`.
- [ ] **`StreamAlertSource`** turns `UserStreamHealthEvent` (`src/modules/trading/contracts/events/user_stream_health_event.py`) and a lost price feed into `USER_STREAM_DOWN` / `PRICE_FEED_STALE` with a VENUE or BOT subject and a stable dedup key (kind + venue), so the hub can coalesce and inhibit.
- [ ] **`SystemAlertSource`** replaces `NotificationEventHandler`: `UiActionFailedEvent`, `TaskFailed` and a failed bulk sync become `APP_FAILURE` alerts (text from `system_error_report.py`'s normalisers, not re-derived); the old handler, its one-message debounce and its direct Telegram wiring at `composition_root.py:262-270` are deleted.
- [ ] The in-app toast channel (`UiToastNotificationChannel`) keeps working for the same system failures; the way it is fed (a second subscriber of the same events, or an `IAlertChannel` adapter) is decided and recorded in the task.
- [ ] `bots` and `trading` import nothing from `alerting`; a source depends on their `contracts/` only.
- [ ] The two alerts the earlier tasks deferred are delivered here: `EPIC-035F`'s revoked key and `EPIC-035C`'s STOPPING that stays stuck after its retries.
- [ ] A source that fails to convert an event logs it and never breaks the publisher of the event.

## 3. Design
Anti-corruption layer: each source translates a foreign event into the alerting vocabulary at the module's edge (DDD); the same subscribe-and-forget style as `UserStreamWatch`. The map from (state, reason) to kind lives in one table with a test that every reason code of `bots` is mapped or deliberately ignored, so a new reason cannot silently produce no alert. Event handlers follow the engine standards in `ONBOARDING.md` §12 (`BaseEvent`, `report_handler_failure`).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/application/sources/` (new) | `BotAlertSource`, `StreamAlertSource`, `SystemAlertSource` |
| `src/shell/notification_event_handler.py` | Deleted |
| `src/shell/composition_root.py` | The handler wiring removed; the module's sources started by the module's `boot()` |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | The alert each journey raises |
| `Tasks/epics/EPIC-035_*/completed/EPIC-035L_*.md` | Already points its range-exit alert at `EPIC-036B` (this epic's scaffolding) |

## 5. Testing
Tier per `ci-rule.md` §2: unit with a fake bus and a `FakeChannel`, plus one integration journey.
- `test_a_halt_sends_one_alert_with_its_reason`
- `test_a_stop_that_leaves_orders_raises_stop_failed_critical`
- `test_a_stop_loss_trigger_raises_one_alert_with_the_price_seen`
- `test_a_return_to_running_sends_one_recovery_alert`
- `test_every_bot_reason_code_is_mapped_or_explicitly_ignored`
- `test_a_range_exit_alerts_once_and_rearms_on_return`
- `test_a_new_bot_kind_needs_no_change_in_alerting`
- `test_a_user_stream_down_event_becomes_one_venue_alert`
- `test_twenty_bots_losing_the_feed_become_one_grouped_alert` (hub + source)
- `test_a_task_failed_event_becomes_an_app_failure_alert`
- `test_the_old_handler_and_its_wiring_are_gone`
- `test_a_source_that_raises_does_not_break_the_event_publisher`
- the module-boundary guards (`bots` never imports `alerting`)

Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: `test_a_halt_sends_one_alert_with_its_reason`, run red.
