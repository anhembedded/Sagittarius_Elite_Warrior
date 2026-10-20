# EPIC-036B2 — A bot's reason chooses its alert: rate limit, rejected key, storage pause and a quiet price feed

**Status:** ✅ Done (2026-10-20) — built and proven by unit and integration tests; the owner's first real message of each kind on the VPS is still to be seen
**Source:** the coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, 2026-10-20: the rest of `EPIC-036B` after `EPIC-036B1`, highest value first — the owner runs bots unattended on a VPS, a rejected key and a storage pause are the two conditions that leave orders resting that the app cannot manage, and a rate limit or a quiet feed arrived as an undifferentiated bot halt (or, for the storage pause, not at all).
**Risk:** 🟢 — reads the status report and an event that exist; no order, stop or close path, no new setting, dependency, timer or event
**Complexity:** S
**Epic:** [EPIC-036](../README.md); split from [EPIC-036B](../completed/EPIC-036B_alert_sources.md), which keeps `SystemAlertSource` and the retirement of `NotificationEventHandler`
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (the journey row for the four kinds)
**Design:** [`Docs/MODULES/alerting/`](../../../../Docs/MODULES/alerting/README.md); the decision is [`DECISION_2026-10-20_reason_alerts.md`](../DECISION_2026-10-20_reason_alerts.md) (an agent decision the owner may veto)
**Depends on:** [EPIC-036G](EPIC-036G_walking_skeleton_halt_to_discord.md), [EPIC-036B1](EPIC-036B1_early_warnings_liquidation_and_user_stream.md); reads `BotChangedEvent`, `BotRecoveryStalledEvent` (`EPIC-042C`) and the bots' status report

---

## 1. Context and problem
`BotAlertSource` alerted on the entry into `HALTED` or `ERROR` with the generic kind only. A rate-limit halt and a rejected API key arrived as `BOT_HALTED`; a bot paused because its state file cannot be saved (`PAUSED`) arrived nowhere; a bot waiting on a quiet price feed arrived, fifteen minutes in, as a generic `BOT_RECOVERY_STALLED`. The catalog already held `RATE_LIMITED`, `KEY_REJECTED`, `STORAGE_FAILURE` and `PRICE_FEED_STALE` and nothing raised them. There was no table that said, for each reason a bot records, whether it reaches the owner.

## 2. Acceptance criteria
- [x] **A rejected key raises one `KEY_REJECTED` CRITICAL (halted or errored), a bot paused for its storage one `STORAGE_FAILURE` CRITICAL**; a pause the owner asked for stays silent; **a wait for the exchange's rate-limit pause that stalls is one `RATE_LIMITED` WARNING**, and a rate limit that is a plain `HALTED` stays the CRITICAL halt, never saying it resumes. (`test_a_wait_for_the_exchanges_pause_that_stalled_is_one_warning_that_says_it_resumes`, `test_a_rate_limit_that_is_a_plain_halt_is_the_critical_halt_and_never_says_it_resumes`, `test_a_rejected_key_is_one_critical_alert_that_says_orders_may_rest`, `test_a_bot_paused_by_its_storage_is_one_critical_alert`, `test_a_pause_the_owner_asked_for_is_still_silent`)
- [x] **A bot waiting on a quiet price feed is one `PRICE_FEED_STALE` CRITICAL when the wait stalls**, silent on entry (`EPIC-042` D11); the grace is the recovery rule's `stalled_after`, no new timer. The halt that says the automatic recoveries are used up stays `BOT_HALTED`. Twenty bots losing the feed are one grouped message and a venue's `USER_STREAM_DOWN` hides them. (`test_a_wait_on_a_quiet_price_feed_is_silent_on_entry_and_one_critical_alert_when_it_stalls`, `test_a_halt_for_a_quiet_feed_stays_the_halt_with_its_recoveries_line`, `test_twenty_bots_losing_the_feed_become_one_grouped_alert`, `test_a_bots_stalled_feed_is_hidden_by_its_venues_stream_outage_through_the_real_hub`)
- [x] **Raise and clear.** Each kind is one message per condition under the hub's dedup, and the return to `RUNNING` ends it with one "Recovered"; a stop does not (no false "Recovered" while the key is still rejected). (`test_the_return_to_running_ends_the_condition`, `test_the_feed_coming_back_ends_the_condition`, `test_a_second_halt_of_another_reason_is_a_new_alert`)
- [x] **The reason-table completeness test.** Every `GridReason` is a row of `REASON_ROUTES` (own kind, stalled kind, exit, generic or silent); each row behaves as it says; the exit rows agree with the stop path; a reason the table does not know is a generic halt. (`test_every_bot_reason_code_is_routed_on_purpose`, `test_a_halt_for_any_reason_is_the_alert_its_route_says`, `test_the_exit_routes_agree_with_the_stop_path`, `test_a_reason_the_table_does_not_know_is_a_generic_halt`)
- [x] **No secret, key fragment or exception text in an alert.** These kinds say a fixed sentence and the reason code; the bot's detail (which carries the failure text of a request or of the disk) is not copied. (`test_no_text_from_the_exchange_or_the_disk_reaches_an_alert`)
- [x] **Wired in the composed app and reaching Discord.** (`test_a_quiet_price_feed_that_stalled_a_wait_reaches_discord_as_one_critical_alert` over `create_app()`; the existing journeys stay green)
- [x] **No change to order sending, stop or close code**; `bots` and `trading` import nothing from `alerting` (the boundary guards in `tests/unit/architecture`).
- [x] **Design in step**: `Docs/MODULES/alerting/`, the runbook's alert list and SPEC-014 changed in the same pull request.
- [ ] **A real message of each kind on the VPS.** Needs the owner (a testnet bot with a revoked key, a read-only data root); not run.

## 3. Design
`bot_reason_routes.py` (`alerting/application/sources/`) is the one table: `REASON_ROUTES` maps each reason code (as `GridReason.value`, a string: alerting reads `bots/contracts`, never `bots.domain`) to a `ReasonRoute` with a `Disposition` (`OWN_KIND`, `STALLED`, `EXIT`, `GENERIC`, `SILENT`), its kind, the states whose entry raises it and its sentence; a route is valid on creation. `BotAlertSource._alert_on_entry` asks `own_route_on_entry(state, reason)` before the generic `ALERT_ON_ENTRY`, and `on_recovery_stalled` asks `stalled_route(reason)` before the generic `BOT_RECOVERY_STALLED`. `CLEARED_ON_ENTRY["RUNNING"]` gains the four kinds. `bot_subject.subject_or_bare` replaces three copies of the same lines and a private helper, which keeps `bot_alert_source.py` at the 400-line ceiling.

## 3a. Reuse
`BotAlertSource`'s entry, clear and stalled paths, `bot_subject`, the hub's grouping and inhibition (`INHIBITED_BY`: `USER_STREAM_DOWN` already hides `PRICE_FEED_STALE`, built with the hub and tested only with hand-made alerts until now) and `RecordingAlertPublisher` are used as they are. No new source class: all four arrive as a bot's own state and reason, through the status report the source already reads. `EarlyWarningPolicy` and `WarningLatch` were not reused: these are states with a clear of their own (a return to `RUNNING`), not a level that flaps.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/application/sources/bot_reason_routes.py` (new) | The reason table, `ReasonRoute`, `own_route_on_entry`, `stalled_route` |
| `src/modules/alerting/application/sources/bot_alert_source.py`, `bot_subject.py` | The two lookups; the four kinds in `CLEARED_ON_ENTRY`; `subject_or_bare` |
| `tests/unit/modules/alerting/application/sources/test_bot_reason_alerts.py` (new), `test_bot_alert_source.py` | The table, the kinds, the hub journeys; the cleared list read from `CLEARED_ON_ENTRY` |
| `tests/integration/modules/alerting/` | `skeleton_world.py` (the composed-app world, moved out of the 400-line journey file), `test_a_stalled_price_feed_reaches_discord.py`, the generic stalled journey now on a reason with no kind |
| `tests/unit/architecture/test_every_state_set_that_names_halted_answers_for_awaiting_recovery.py` | One exception, with its reason |
| `Docs/MODULES/alerting/`, `Docs/OPERATIONS/headless_runbook.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | Design and the owner's reading |

## 5. Testing and implementation notes
Unit with a recording publisher and a fake clock, and with the real hub over a fake channel: `tests/unit/modules/alerting/application/sources/test_bot_reason_alerts.py`. Integration over the composed app, real hub, outbox and Discord channel with a fake transport: `tests/integration/modules/alerting/test_a_stalled_price_feed_reaches_discord.py`.

Mutation checks run on 2026-10-20, each turning the named tests red: the own-kind lookup disabled in `_alert_on_entry` (11 tests); the stalled lookup disabled in `on_recovery_stalled` (2); `STORAGE_FAILURE` removed from `CLEARED_ON_ENTRY` (2).

**Decided, not built (stays in `EPIC-036B`):** `SystemAlertSource` and the deletion of `NotificationEventHandler`, its direct Telegram wiring and the toast feed (a change of the GUI wiring and of the Telegram path `EPIC-036C` migrates); the criterion that a source which raises never breaks the publisher of the event. `PRICE_FEED_STALE` is raised by `BotAlertSource`, not `StreamAlertSource`: the bot already measures the silence, so a market-data stream timer would be a second clock (decision D3).

**Behaviour changes the owner may veto** (decision D2, D3; round 1 of the review moved the rate limit onto `EPIC-042F`'s wait): a wait for the exchange's pause that stalled is now a WARNING `RATE_LIMITED` (a generic stalled warning before); a wait stalled on a quiet feed is now a CRITICAL `PRICE_FEED_STALE` (it was a WARNING `BOT_RECOVERY_STALLED`).

## 6. Docs touched
`Docs/MODULES/alerting/README.md`, `03-context.md`, `05-building-blocks.md`, `06-runtime.md`, `09-decisions.md`; `Docs/OPERATIONS/headless_runbook.md` (§0 list and gap table); `Docs/SPEC/SPEC-014_run_a_grid_bot.md` (one journey row); `Tasks/epics/EPIC-036_alerting_module/` (README, TRACKING, the decision, `EPIC-036B`); `Tasks/epics/README.md`.

## Resume
Done. What is left is the owner's: see one real message of each kind on a testnet bot and veto or keep the two severities in the decision record.
