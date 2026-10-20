# EPIC-036B1 — Early warnings reach the owner: a position near liquidation, a user-data stream that stays down

**Status:** ✅ Done (2026-10-20) — built and proven by unit and integration tests; the owner's first real warning on the VPS is still to be seen
**Source:** the coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, 2026-10-20: decision N5 and 026N of [`REVIEW_2026-10-20_what_is_still_missing.md`](../../EPIC-026_road_to_real_money/REVIEW_2026-10-20_what_is_still_missing.md) — liquidation warnings below `CRITICAL` and `UserStreamWatch`'s own alert belong to `EPIC-036B`; the owner runs bots unattended on a VPS and early warnings were only in the log.
**Risk:** 🟢 — reads two events that exist; no order, stop or close path, no new setting or dependency
**Complexity:** S
**Epic:** [EPIC-036](../README.md); split from [EPIC-036B](../completed/EPIC-036B_alert_sources.md), which keeps the rest of the sources
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (the journey row for the warnings)
**Design:** [`Docs/MODULES/alerting/`](../../../../Docs/MODULES/alerting/README.md); the decision is [`DECISION_2026-10-20_early_warnings.md`](../DECISION_2026-10-20_early_warnings.md) (an agent decision the owner may veto)
**Depends on:** [EPIC-036A](EPIC-036A_alerting_core.md), [EPIC-036G](EPIC-036G_walking_skeleton_halt_to_discord.md); reads `BotRiskChangedEvent` (`EPIC-039F`) and `UserStreamHealthEvent` (`EPIC-035B`)

---

## 1. Context and problem
Only a CRITICAL halt, error or failed stop reached Discord. A Futures bot nearing liquidation, or a user-data stream that stayed down, was in the log until the bots halted. Two facts exist as typed events and nothing in `alerting` heard them.

## 2. Acceptance criteria
- [x] **A Futures bot inside its warning distance raises one `LIQUIDATION_RISK` WARNING** with the mark price, the exchange's liquidation price and the distance; none for `CRITICAL` or `UNKNOWN`. (`test_a_warning_level_is_one_warning_alert_about_the_bot_with_the_figures`, `test_the_critical_level_raises_nothing_of_its_own_because_the_halt_is_the_alert`)
- [x] **Clear condition.** The return to `SAFE` (after the cool-down), the bot reaching `STOPPED` or its removal ends it with one "Recovered"; a `SAFE` after no warning clears nothing; a write while no warning is open reads no status. (`test_the_return_to_safe_after_the_cooldown_clears_the_warning_once`, `test_a_bot_that_stops_ends_its_open_warning_with_recovered`, `test_a_write_while_no_warning_is_open_reads_no_status`, `test_a_removed_bot_ends_its_open_warning`, `test_a_safe_reading_that_follows_no_warning_clears_nothing`)
- [x] **Cool-down.** A warning stands once; a `SAFE` inside 10 min leaves it open (no false "Recovered"); a `WARN` after 10 min on a warning still open is told again; a halted or errored bot forgets its warning, so the next approach after a resume is told. (`test_a_second_warning_inside_the_cooldown_is_not_told_again`, `test_a_return_to_safe_inside_the_cooldown_sends_no_recovered_that_a_recross_would_falsify`, `test_a_warning_still_standing_after_the_cooldown_is_told_again`, `test_a_halted_and_resumed_bot_warns_again_at_its_next_approach`)
- [x] **A user-data stream down past 60 s raises one `USER_STREAM_DOWN` for the venue**; a reconnect inside the grace is silent; the retries of one outage are one alert. (`test_an_outage_past_the_grace_is_one_alert_about_the_venue`, `test_a_reconnect_inside_the_grace_is_silent`, `test_the_retries_of_one_outage_are_told_once`)
- [x] **Clear and cool-down for the stream.** `CONNECTED` ends it with one "Recovered"; a drop again within 10 min sends no second pair; `STOPPED` is no outage; each venue has its own. (`test_the_return_of_the_stream_clears_the_condition_once`, `test_a_link_that_drops_again_inside_the_cooldown_sends_no_second_pair`, `test_an_outage_after_the_cooldown_is_a_new_alert`, `test_a_stream_nobody_wants_any_more_is_not_an_outage`, `test_each_venue_has_its_own_outage`)
- [x] **No secret in an alert.** The stream alert copies no failure text of the connection. (`test_the_alert_carries_no_failure_text_from_the_connection`)
- [x] **Wired in the composed app and reaching Discord.** (`test_a_liquidation_warning_reaches_discord_as_one_warning`, `test_a_user_stream_outage_reaches_discord_as_one_alert_about_the_venue` over `create_app()`)
- [x] **No change to order sending, stop or close code**; `bots` and `trading` import nothing from `alerting` (the boundary guards in `tests/unit/architecture`).
- [x] **Design in step**: `Docs/MODULES/alerting/`, the runbook's alert table and SPEC-014 changed in the same pull request.
- [ ] **A real warning on the VPS.** Needs the owner (a testnet Futures bot driven near its liquidation price); not run.

## 3. Design
`LiquidationAlertSource` (`alerting/application/sources/liquidation_alert_source.py`) and `StreamAlertSource` (`.../stream_alert_source.py`) are siblings of `BotAlertSource`: an anti-corruption layer over a contract event, publishing through `IAlertPublisher`. Both hold a `WarningLatch` (`alerting/application/warning_latch.py`) built from `EarlyWarningPolicy` (`alerting/domain/alert_policies.py`). `AlertKind.LIQUIDATION_RISK` is new (BOT_EVENTS group, WARNING); `USER_STREAM_DOWN` existed. `AlertingModule.dependencies` gains `trading`. A separate class rather than a method of `BotAlertSource`, which sat at the 400-line ceiling.

## 3a. Reuse
The hub's dedup, grouping and inhibition were read first and are used as they are. They were not enough alone: `AlertHub.condition_cleared` forgets the dedup window of the key it clears (so a flap after "Recovered" is not swallowed), which makes a condition that flips between raised and cleared send a pair per flip, and the hub's window is 15 minutes for a WARNING and one minute for a CRITICAL. `WarningLatch` is the source's small bound on top (one open warning per key, a cool-down between raises). `BotAlertSource`'s state map was not reused: it alerts on entry into a lifecycle state, while these warnings follow a level (`RiskLevel`) and a connection state the lifecycle does not carry. `bot_subject.subject_of` and the contract events are reused.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/application/sources/liquidation_alert_source.py` (new) | The liquidation warning |
| `src/modules/alerting/application/sources/stream_alert_source.py` (new) | The stream outage |
| `src/modules/alerting/application/warning_latch.py` (new) | One open warning per key, a cool-down between raises |
| `src/modules/alerting/domain/alert_policies.py`, `alert_kind.py`, `alert_catalog.py` | `EarlyWarningPolicy`; the `LIQUIDATION_RISK` kind and its row |
| `src/modules/alerting/module.py`, `composition/alerting_bindings.py` | Subscriptions and bindings; `trading` as a dependency |
| `src/support/log_view/template_catalogue.json` | Regenerated for the new log calls |
| `Docs/MODULES/alerting/`, `Docs/OPERATIONS/headless_runbook.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | Design and the owner's reading |

## 5. Testing and implementation notes
Unit with a recording publisher and a fake clock: `tests/unit/modules/alerting/application/test_warning_latch.py`, `sources/test_liquidation_risk_alert.py`, `sources/test_stream_alert_source.py`. Integration over the composed app, real hub, outbox and Discord channel with a fake transport: `tests/integration/modules/alerting/test_a_halted_bot_reaches_discord.py`.

Mutation checks run on 2026-10-20, each turning the named test red: the `BotRiskChangedEvent` subscription removed from `AlertingModule.boot` (the liquidation journey); the `UserStreamHealthEvent` subscription removed (the stream journey).

**Decided, not built (stays in `EPIC-036B`):** `SystemAlertSource` and the deletion of `NotificationEventHandler`; the market-data stream's `PRICE_FEED_STALE`; `RATE_LIMITED`, `KEY_REJECTED` and `STORAGE_FAILURE` as kinds of their own (they arrive today as the generic bot halt); the completeness test of every bot reason code. A stream that reports `CONNECTED` and delivers nothing is not seen by this source; the periodic reconcile catches the missed fills.

## 6. Docs touched
`Docs/MODULES/alerting/03-context.md`, `05-building-blocks.md`, `06-runtime.md`, `09-decisions.md`, `10-quality.md`, `README.md`; `Docs/OPERATIONS/headless_runbook.md` (§0 list and gap table); `Docs/SPEC/SPEC-014_run_a_grid_bot.md` (one journey row); `Tasks/epics/EPIC-036_alerting_module/` (README, TRACKING, the decision); `Tasks/epics/README.md`.

## Implementation notes
Review round 1 of PR #613 found that the guard resets to `SAFE` without an event when a bot leaves the states it judges, which left the latch open after a halt and a resume; the source now forgets the latch on any other state (quietly, with "Recovered" only for `STOPPED` or removal). It also made the `SAFE` inside the cool-down defer (no false "Recovered"), moved the hand-over to the hub under the same lock as the latch, and made `on_bot_changed` read the bot store only while a warning is open. Mutation checks on the halt path: removing the `forget` turns `test_a_halted_and_resumed_bot_warns_again_at_its_next_approach` red.

## Resume
Done. What is left is the owner's: watch a real warning on a testnet Futures bot and veto or keep the numbers in the decision record.
