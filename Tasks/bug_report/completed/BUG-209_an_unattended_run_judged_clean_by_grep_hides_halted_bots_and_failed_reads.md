# BUG-209 — A 24-hour run judged clean by grepping WARNING|ERROR|CRITICAL can hide halted bots, lost fills and dead feeds

- **Reported:** 2026-10-14 (owner, before running a real Grid bot on the headless host in normal mode; found by a read-only audit of `origin/master-warrior`)
- **Severity:** 🔴 P1 — real money: the owner's only two signals for an unattended run are a grep of the journal for ` - (WARNING|ERROR|CRITICAL) - ` and the INFO `[health]` line, and a bot that stopped trading, a fill the stream lost or a feed that died reached neither
- **Status:** Fixed (2026-10-14)
- **Board:** Halted and failed bots, our own pre-send refusals, a missed fill recovered by reconcile, clock drift, a dead kline stream and failing position/holdings reads were INFO or DEBUG, and the health line left out ERROR, STARTING and STOPPING. Cause: the level was chosen at each call site, not where a transition is applied. Fix: `BotRunState.transition` logs HALTED at WARNING and ERROR at ERROR with the reason; the other seven items raised once per streak with a recovery line; a guard walks the lifecycle table.
- **Context:** [SPEC-015](../../../Docs/SPEC/SPEC-015_run_the_bots_headless.md) → Modules `bots` (`application/services/lifecycle/`, `application/kinds/grid/recovery/`), `trading` (`application/`, `adapters/health/`), `market_data` (`adapters/binance/`), `operations` (`application/`) → Application / Adapters
- **Environment:** Linux headless host, `main.py run` without `--dev` or `--debug`; app commit `9df3449` (`origin/master-warrior`); no secret in this report.

## Reproduction
Each item is reproduced by a unit test (below), driving the real executor on the simulated venue or the real service with a failing dispatcher; not reproduced on a host.
1. Run a Grid and let a pre-send refusal (the lease, the minimum notional) or a reconcile mismatch halt it. Expected: a WARNING. Actual: one INFO line `Bot x: RUNNING -> HALTED on halt (...)`.
2. Put a bot in ERROR. Expected: an ERROR record and `error:1` on the health line. Actual: INFO, and the line counted running, paused, halted and recovering only.
3. Make the positions or holdings read fail for a day. Expected: one WARNING. Actual: DEBUG per tick.

## Symptom
Audit, 2026-10-14 (line numbers re-verified at `9df3449`; the audit's paths for the first two items predate the module split and are given here as they are now):
1. `bots/application/services/lifecycle/bot_run_state.py:125` logged every transition at INFO; a refused transition (`kinds/grid/grid_order_failure.py` `_apply`) wrote nothing but a reason on the record.
2. `operations/application/host_health_line.py:37` `_LINE_STATES` held four of the lifecycle's states.
3. Pre-send refusals (`trading/application/orders/execute_order/handler.py`, `bots/application/services/orders/order_outcome.py`) are results, not log lines; the only record of the halt they cause was the INFO of item 1.
4. `kinds/grid/recovery/grid_missed_fills.py:100,126`: a fill, or an order end, the stream lost and history gave back, at INFO.
5. `trading/adapters/health/clock_skew_probe.py` had no logger; the only trace of drift was `skew_ms` on the INFO health line.
6. `market_data/adapters/binance/binance_websocket_service.py` `_run_stream` caught `OSError` only, and a `{"e": "error"}` message fell through as "not a kline".
7. `trading/application/position_refresh_service.py:106` and `holdings_refresh_service.py:83`: every failure at DEBUG.
8. `kinds/grid/recovery/grid_reconciler.py:182`: a larger exchange quantity returns `ReconcileMismatch`, which halts the bot, with the line of item 1 as its only record.

## Root cause
One design fault, repeated: **the level of a "this stopped trading" event was decided by each caller, and the one place that applies lifecycle transitions logged them all alike.** `BotRunState.transition` (`bot_run_state.py`) is the only writer of a bot's state in the executor, yet it logged at a fixed INFO, so items 1, 3 and 8 (every path into HALTED or ERROR) were invisible to the grep by construction. Item 2 is the same omission in a second place that lists lifecycle states by hand. Items 4 to 7 are call sites that chose DEBUG or INFO for an event the owner needs, or, for 5 and 6, had no line at all. The refresh services of 7 already had a model next door (`AccountSummaryRefreshService`: one WARNING per streak).

The gate was green while this was live: the run-log scan of `ci-rule.md` §3 fails on an unexpected WARNING, so it can only reward quiet code; no test asserted that a halt is loud. No case study: the blind spot is closed by the guard below, in the same change, and it is not open elsewhere.

## Fix
- `lifecycle/bot_run_state.py`: `transition` logs at the level of the state the bot lands in (`landing_level`: HALTED WARNING, ERROR ERROR, others INFO) with the reason and a `[bot-transition]` tag. `apply_or_record` replaces the `if can: transition else update` shape that `grid_order_failure._apply` and `symbol_status_gate._delisted` each carried: an event the table does not declare logs a WARNING `[bot-transition-refused]` and keeps the reason. `bot_restore_service` uses `landing_level` for a bot a restart lands in HALTED (STARTING) so the restart's one transition is loud too.
- No duplicate WARNING from one event: `symbol_status_gate` no longer logs a line of its own where a transition follows (it carries the same detail); where no transition happens (a PAUSED or RUNNING bot that only records its reason) it still does. The two records a failing step already wrote (the step's ERROR with its traceback, then the transition) are cause and effect, not a restatement.
- `host_health_line.py`: `error`, `starting`, `stopping` appended to the line's bot states (order is the contract's); `health_line.py` and `LOGGING.md` §4 updated.
- Items 4 to 8: `grid_missed_fills.py` WARNING `[missed-fill]`/`[missed-end]` (one per order in a reconcile, never per tick); `trading/application/refresh_failure_streak.py` (new, shared) used by `PositionRefreshService` and `HoldingsRefreshService`: WARNING at the first failure of a streak, DEBUG after, INFO `[refresh-recovered]`; `trading/adapters/health/clock_skew_alarm.py` (new) used by `ClockSkewProbe`: WARNING above 500 ms, ERROR at 1000 ms (the pre-flight's own `WARN_ABOVE_MS`/`FAIL_AT_MS`), INFO on recovery, once per venue and level; `binance_websocket_service.py`: `{"e": "error"}` raises `KlineStreamError` (an `OSError`, so the existing ERROR-and-reconnect path takes it) and any other exception is logged ERROR with the traceback and the stream reconnects. Items 3 and 8 need no line of their own: they halt through `transition`.
- `trading/module.py`: a user-data stream that failed to stop at shutdown is a WARNING, was DEBUG (a socket may stay open).
- `LOGGING.md` §6 (tag table) and a new §7 (what each level means for a bot or a feed); `headless_runbook.md` §6: the "judge a 24-hour run clean" paragraph and the hard-kill/OOM line (`systemctl show sew-run -p NRestarts`, `journalctl -u sew-run | grep -E 'Main process exited|Scheduled restart'`).

## Regression test
All fail on `9df3449` for the stated reason and pass after.
- `tests/unit/modules/bots/application/services/test_bot_transition_levels.py` — **the guard**: parametrised over `BOT_LIFECYCLE_TRANSITIONS`, so every row into HALTED or ERROR (21 today, and any added later) must produce exactly one record at its level carrying the reason; `test_the_guard_finds_a_transition_that_logs_below_its_level` is the probe that breaks it (the pre-fix INFO for every transition) and asserts the guard sees all 21. Failed before: the record was INFO.
- `test_grid_halt_levels.py` (a refusal at start, a lease refusal on a running bot, a failing step), `test_grid_reconciler_gap_unfilled.py` (missed fill, missed end, a quantity mismatch that halts), `test_host_health_line.py` (the seven states in order), `test_refresh_failure_streaks.py`, `test_clock_skew_alarm.py` (500/501/999/1000 boundaries, once per level, recovery), `test_binance_websocket_service.py` (`{"e":"error"}` and a non-`OSError` exception).

## Verification
Red on `9df3449` (31 and then 7 tests failed as above); green after. Unit tier and the new tests: see the PR. The full gate is the PR's GitHub Actions `ci-local.ps1 -Full` run. Not run on a host: a real 24-hour run.

**Checked, not guessed.**
- *The Engine's fallback bus logger* (`resolve_bus_logger`, `report_handler_failure`, `engine.ref` `f4ef582`): `report_handler_failure` always logs at ERROR with a traceback, but through whichever logger it is given. The app's `MemoryEventBus` is built with the app logger (`shell/composition_root.py:246`), so a failing handler there prints ` - App - ERROR - Handler … raised …` on stdout and matches the grep (run through the real `StdLogger`). A component built **without** a logger gets `FallbackLogger("sagittarius_engine.event_bus")`, which configures nothing and has no handler in this app, so Python's last resort prints the **bare message to stderr, with no ` - ERROR - `**: the grep does not match it. `QtEventBridge`, which `BaseFeed` (`support/ui_kit/base_feed.py:88`) builds without a logger, is such a component, so a handler failure in a GUI feed does not reach the grep. The headless `run` host builds no feed. Not fixed here (an Engine or `ui_kit` change); filed as a follow-up.
- *Does every bot come back RECOVERING after a hard crash?* **No.** The restart rule (`bot_lifecycle_fsm_matrix.py`, `APP_RESTART`) is applied to the last saved file, and the app writes no clean-stop marker, so a hard kill and a clean stop restore alike: RUNNING and PAUSED → RECOVERING (a second restart before the reconcile stays RECOVERING); STARTING → HALTED; HALTED, ERROR, STOPPING, STOPPED and DRAFT keep their state. A bot that was STOPPING at the kill stays STOPPING; nothing in the restore finishes it.

## Remaining swallowed exceptions (listed, not changed)
A scan of every `except` in `bots`, `trading` and `operations` that neither raises nor logs above DEBUG:
- `bots/application/kinds/grid/planner_numbers.py:97` — DEBUG; advice only (an open-order count in the planner), no order depends on it.
- `bots/application/services/venue/futures_facts_reader.py:115`, `exchange_facts_reader.py:111` — DEBUG, but the failure is converted to an explicit *unavailable* snapshot whose reason the bot shows; they run per poll, so a WARNING needs a streak like item 7. Candidate follow-up.
- `bots/adapters/persistence/json_bot_store.py:82` — DEBUG for an unreadable bot file; `BotRestoreService` logs the same file at ERROR.
- `trading/adapters/binance/exchange_call_policy.py:92` — DEBUG for a used-weight header that is not a number; harmless.
- The `except Exception` blocks of `trading/application/session/emergency_stop/handler.py` return the failure text in the step result the operator reads; not silent.
