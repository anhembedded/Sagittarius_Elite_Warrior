# EPIC-035A — The bot owns its price subscription, with a staleness rule

**Status:** 🟡 In progress — implemented; awaiting the `-Full` run on the PR head and the reviewer
**Source:** the owner's Spot Grid audit, 2026-10-08, finding H1 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 1 approved by the owner the same day (D1).
**Risk:** 🔴 — stop-loss and take-profit are the only price-driven exit; a change to who owns the stream touches every running bot
**Complexity:** L — a new owner of a market_data stream inside the bots module, a staleness clock, a named HALT reason, SPEC and guard changes
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), extended by this task
**Depends on:** None

---

## 1. Context and problem
**Claim (audit H1), verified ✅ on `3bbe243`:** stop-loss / take-profit ticks reach a `GridExecutor` only through `MarketTickEvent`.
- `src/modules/bots/application/event_handlers/bot_event_router.py:106-114` (`on_tick`) is the only caller of `executor.on_tick`, and it reacts to `MarketTickEvent` from the bus.
- That event is published by `src/modules/market_data/adapters/binance/binance_websocket_service.py`, which runs only while a consumer has started a stream through `IMarketStream` (`src/modules/market_data/contracts/i_market_stream.py:86`, `start(symbol, timeframe, owner_id)`). In the bots module the only consumer is the selected bot's chart: `src/modules/bots/ui/bots_screen/bot_chart_host.py` (`_follow_if_live`, line 171) and `src/modules/bots/ui/bot_tick_feed.py`, which only *listens*. Selecting another bot, or closing the chart, ends the stream.
- `src/modules/bots/application/services/grid_executor.py:115-117` (`_WATCHES_EXITS` = RUNNING, PAUSED, HALTED, ERROR) and `:297-304` (`_apply_tick`) are the only place a price becomes an exit. A bot in **STARTING, RECOVERING or STOPPING never watches**, whatever the stream does.
- No code compares the age of the last tick with the clock. A feed that goes quiet looks the same as a flat market.

Result: with the chart closed, on another bot, or in RECOVERING after a restart, a crossed stop-loss goes unnoticed. Exchange-side stops (`EPIC-026K`) are the structural fix for a closed app and stay there; this task closes the window while the app runs.

## 2. Acceptance criteria
- [x] Every bot that is not stopped (STARTING, RUNNING, PAUSED, RECOVERING, HALTED, ERROR, STOPPING) owns a price stream for its symbol and venue market, started when the bot enters such a state and released when it reaches STOPPED or DRAFT. The stream is requested through market_data's contract (`IMarketStream`) with a bots-owned `owner_id`, never by reaching into the Binance adapter.
- [x] The stream does not depend on any chart: closing the chart, selecting another bot or switching modes leaves SL/TP watched.
- [x] The stream is the bot's own venue and market: a Testnet tick never reaches a Mainnet bot and a Spot tick never reaches a Futures bot (`BUG-172` stays closed).
- [x] A bot in RECOVERING and in STARTING evaluates stop-loss / take-profit on the ticks it receives (the exit then runs the existing `_run_stop` path, taking the ladder off).
- [x] **Staleness rule:** while a bot is in a state that holds orders, no tick for N seconds moves it to HALTED with a named `GridReason` (for example `PRICE_FEED_STALE`) whose detail names the last tick's age. N is a named constant with a default derived from the stream's own cadence (the audit suggests tens of seconds; the value is chosen in the PR and recorded here). **Chosen: 60 s after the last tick, 60 s for the first one; checked every 5 s** (`price_freshness.py`, `bot_price_watch.py`).
- [x] The staleness check uses a monotonic clock and an injected clock port, not `time.sleep`; it does not fire for a bot that has not yet received its first tick within the start grace, which is a separate, named, bounded wait.
- [x] A fresh tick after a staleness HALT does not resume the bot by itself; the user's confirm-resume path stays the only way back.
- [x] Two bots on the same symbol and venue share the market stream (one subscription per symbol and market, released when its last owner leaves), as `IMarketStream`'s owner model already allows.
- [x] Stopping the app releases every bot-owned stream; the sanity tier shows a clean shutdown with no `ResourceWarning`.

## 3. Design
- **Pattern:** the owner-keyed stream of `IMarketStream` (`start(symbol, timeframe, owner_id)` / `stop(owner_id)`, "started and released together") is the vetted mechanism; the bots module becomes one more owner instead of borrowing the chart's. This is `CONSTITUTION.md` P5 (apply the existing mechanism): no new stream machinery.
- **Where:** an application service in the bots module, `BotPriceWatch` (name to be confirmed in the PR), subscribed to the executor lifecycle (the same hook that registers an executor in `bot_executors.py`). It owns start/stop of the stream per executor and a staleness clock per executor. It reads the stream through the market_data contract only (`test_module_boundaries` and the module allowlist, which may only shrink, stay as they are).
- **Tick path:** unchanged. `BotEventRouter.on_tick` keeps routing `MarketTickEvent` to executors; the change is that a tick now exists whether or not a chart is open, and that RECOVERING / STARTING evaluate it. `_WATCHES_EXITS` grows to every order-holding state; the exit in STARTING must not race the ladder placement (the executor's single worker queue already serialises it — a crossed exit during STARTING is queued behind the placement task and then stops the bot).
- **Staleness:** a domain function `price_is_stale(last_tick_at, now, limit)` (pure, `Decimal`-free, unit-tested) and an application timer that posts a `check_price_age` task onto the executor's queue, so the HALT goes through the same `GridTaskGuard` as every other task (and parks the ladder: see `EPIC-035C`). The reason is a new member of `GridReason` and a row in the FSM matrix test; the transition uses the existing `HALT` event, no new edge.
- **Why not "keep the chart's stream and warn":** the chart's stream is a UI concern with a UI lifetime; a safety rule must not depend on a widget being open. The audit's interim guidance (keep the chart Live) is exactly the coupling this removes.
- **Cost:** one websocket subscription per distinct symbol and market, not per bot. Binance allows far more streams per connection than a personal bot count uses.
- **Not here:** exchange-side stop orders (`EPIC-026K`); the status-bar text "Market data: not live" (`EPIC-035N`).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/bot_price_watch.py` (new) | Per-executor stream ownership through `IMarketStream`, the last-tick clock and the staleness check |
| `src/modules/bots/application/services/grid_executor.py` | `_WATCHES_EXITS` covers every order-holding state; a `check_price_age` task; the last-tick time is recorded in `_apply_tick` |
| `src/modules/bots/domain/grid/` (the pure rule) and `GridReason` | `price_is_stale`; `PRICE_FEED_STALE` |
| `src/modules/bots/application/services/bot_executors.py` | Start/stop the watch when an executor is registered or released |
| `src/modules/bots/module.py` | Wire the watch with `IMarketStream` and a clock port |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | The journey "the chart is closed" and "the feed goes quiet" |
| `tests/unit/modules/bots/**`, `tests/integration/modules/**` | The tests named in §5 |

## 5. Testing
Tier names per `ci-rule.md` §2. Every "red before" test must be run and shown red for the right reason before the change (`fix-bug-rule.md` §4 applies to the defect shape; the audit's claim is the failing behaviour).

| Criterion | Test | Tier | Expected |
| :--- | :--- | :--- | :--- |
| SL crossed with no chart open | `tests/unit/modules/bots/application/services/test_bot_price_watch.py::test_a_stop_loss_is_watched_with_no_chart_open` — red before: the executor gets no tick, so the ladder stays and the bot stays RUNNING | Unit, with `FakeMarketStream` (`src/modules/market_data/contracts/testing/fake_market_stream.py`) | After the tick below SL the bot is STOPPING, its tagged orders are cancelled |
| SL crossed in RECOVERING and STARTING | `test_a_stop_loss_is_watched_in_recovering_and_starting` (parametrised on the state) — red before: `_WATCHES_EXITS` excludes both | Unit | The exit runs in each state |
| Staleness | `test_no_tick_for_the_limit_halts_the_bot_with_a_named_reason` — red before: no rule exists | Unit with a fake clock | HALTED, reason `PRICE_FEED_STALE`, detail has the age; the ladder is parked |
| No first tick | `test_the_start_grace_is_bounded_and_named` | Unit | Within the grace nothing halts; after it, HALT |
| Fresh tick after HALT | `test_a_tick_after_a_stale_halt_does_not_resume` | Unit | Still HALTED |
| Venue isolation | `test_a_testnet_tick_never_reaches_a_mainnet_bot` | Unit | Mainnet executor unmoved |
| Shared stream | `test_two_bots_on_one_symbol_share_one_subscription` | Unit | One `start`, `stop` after the last owner |
| Pure rule | `tests/unit/modules/bots/domain/grid/test_price_is_stale.py` | Unit | Boundary at exactly the limit |
| FSM matrix | `tests/unit/modules/bots/domain/test_bot_lifecycle_fsm_matrix.py` | Unit | `PRICE_FEED_STALE` is reachable from each order-holding state |
| Clean shutdown | the sanity tier boot-and-shutdown | Sanity | No `ResourceWarning` |
| Real journey | an integration test: a bot RUNNING, chart never created, fake stream pushes a price below SL | Integration | Stopped |

Architecture guards: `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/architecture -q`. Verification of delivery follows `ci-rule.md` §1 (feature: `-Full` run on the PR head, then a reviewer session).

## Implementation notes (written when done)

**Delivered:** `BotPriceWatch` (`application/services/bot_price_watch.py`) gives every bot that is not DRAFT or STOPPED its own price stream through `IMarketDataSources.ports_for(venue.market_data_venue).stream` (`IMarketStream`), keyed `bot-price.<id>`. It follows the bot's state through `BotChangedEvent` (the store publishes one per write), reads the bot back from the store, makes sure a watched bot has an executor, and ticks every 5 s to (a) retry a stream that refused to open and (b) post `on_price_age_check` to each executor. The HALT itself is the executor's, on its own queue, through the existing `GridTaskGuard` (which parks the ladder).

**Decisions (CONSTITUTION P5/P6/P7, recorded here instead of asked):**
- **Owner per bot, not per symbol.** The criterion "share one subscription" is the live-stream service's reference count per `(market, symbol, interval)` (`BinanceWebsocketService.subscribe`); a second ref-count in the bots module would duplicate it. `test_two_bots_on_one_symbol_share_the_stream_until_the_last_leaves` asserts the owner-level behaviour; the sharing itself is the service's contract.
- **Limits:** `PRICE_STALE_AFTER_SECONDS = 60`, `PRICE_START_GRACE_SECONDS = 60`, check every 5 s. Binance pushes a kline update about every 2 s while a pair trades, so 60 s is about thirty missed pushes.
- **Two FSM cells added, contrary to §3's "no new edge".** `halt` was declared only for RUNNING, PAUSED and STOPPING; STARTING and RECOVERING had `start_refused` / `reconcile_mismatch` only. Reusing those events for a quiet feed would misname the cause, so `(STARTING, halt)` and `(RECOVERING, halt)` were declared (`PRICE_STALENESS_HALTS`). STOPPING has the cell but is deliberately **not** halted by a quiet feed: a stop sells and cancels without a price, and a halt would turn the user's Stop into a resume that re-plans a ladder. HALTED and ERROR already place nothing.
- **`_WATCHES_EXITS` gains STARTING and RECOVERING, not STOPPING.** A tick during STOPPING would re-enter `_run_stop` and could turn a Stop that keeps the base into one that sells it.
- **"Armed", not "began".** A first design restarted the grace at the halt; the unit test for a resume hours later was red, because nothing re-armed it. The age is now armed when built, at every check while the bot is in a state a quiet feed does not halt, and at the halt, so a resume after any wait gets a fresh bounded wait for its first tick (`GridPriceAge`).
- **A restored bot is watched at boot.** `BotPriceWatch.start()` builds the executor of every stored bot not at rest (the router only built one on a fill or the switch). A bot on a venue whose trading is not enabled yet (`VenueNotEnabledError`) keeps its stream and gets its executor on a later check; a bot the factory cannot read is said once, with its traceback, and does not stop the others.
- **Ports:** `IMonotonicClock` (a staleness clock a wall-clock step cannot move) and `IBotTicker` (a periodic trigger, a fake that fires on demand), each with a verified fake, a real adapter and a contract test; both sized for 035B/035K to reuse.
- **`GridExecutor` is back under its ceilings in size, not in members.** After merging `EPIC-035C` (PR 429) the actor reached 411 lines, so the tick reaction and the age check moved to `GridPriceReaction` (`grid_price_reaction.py`): the executor is 384 lines. It still has 17 public members (035C's `recover_after_restart` and this task's `on_price_age_check`, one over the 15-method threshold of `architecture-rule.md` §5.4); reducing that is a split of the actor's port and its own task.

**Red before (2026-10-08, `546b8a3`):** `test_grid_executor_exit_states.py` failed by assertion for STARTING and RECOVERING (the bot stayed in the state after a tick below its stop loss and above its take profit); every other new test failed at collection because the mechanism did not exist (`price_freshness`, `bot_price_watch`, the fakes). Logs: the session's scratchpad `red_exit_states.log`, `red_all.log`.

**Verification (head of this branch):**
- Commit tier `ci-local.ps1 -SkipTests`: `RESULT: PASS`.
- `tests/unit tests/integration tests/sanity`: 10,180 passed, 3 skipped, 1 failed. The one failure, `test_workbench_conformance[True-1024x700]` (`backtest@1024x700/fits_the_window`), fails identically on the unchanged base `546b8a3` in this container (verified with the change stashed); it concerns the Backtest mode's window size, not bots. Whether the GitHub run shows it too is recorded on the PR.
- Mutation checks (flip the boundary; drop a mode from `_WATCHES_EXITS`; drop `note_tick`; drop each `arm`; drop `bus.on(BotChangedEvent …)`, `watch.start()` and the shutdown `close()`; invert the state filter; point the stream at another venue; drop the `(RECOVERING, halt)` cell): each turns at least one test red.
- Integration journeys on the fake Binance server (`test_a_bot_owns_its_price_stream_on_the_fake_exchange.py`): no Bots screen is built; a crossed stop loss stops the bot and takes the ladder off, also for a bot restored RECOVERING; a silent feed halts it and a later tick does not resume it. The stream is the verified `FakeMarketStream` behind `FakeStreamSources`, so nothing reached a real exchange.
- Integration harness: `booted()` waits on the app thread pool's own count before `engine.stop()`; a post-fill account read left running by a journey that ends on a fill reached `testnet.binance.vision` in about half of the runs (the integration tier's network block caught it). 8 of 8 runs are clean after.

**Review round 1 (PR 430, reviewer `session_014XHPxwRwhUd2gceQjEXW8z`, NEEDS_REVISION, gate green):** (1) `BotPriceWatch` now reads the store and changes the stream as one step under its lock (`_reconcile`), and stops a stream inside the lock, so a Stop's late `stop(owner)` cannot close the stream a Start just opened, nor a stale snapshot reopen a released one (`test_a_stop_in_flight_cannot_close_the_stream_a_restart_just_opened`, red before). (2) The watch never builds the executor of a STARTING bot: `BotRunner.start` saves STARTING and builds the run's executor itself (`fresh`), so one built by the watch was a throwaway second writer (`test_a_bot_entering_starting_gets_no_executor_from_the_watch`, red before). (3) A RECOVERING bot with trading off still halts on a quiet feed, decided and pinned (`test_a_recovering_bot_with_trading_off_still_halts_on_a_quiet_feed`): it cannot watch its stop loss, the halt is what the user sees, and whether the ladder comes off is trading's answer (its cancels are refused with the switch off and the guard says so; the simulated venue does not model that refusal).

**Merge of master-warrior (2026-10-08, `7793962`, EPIC-035C):** conflicts were additive (the executor deps carry both `retries` and `monotonic`; `boot()` starts the price watch, then 035C's `BotBootRecovery`; `shutdown()` closes the retry scheduler, the watch, then the workers). The merge exposed one defect, red in `test_shutdown_closes_every_bot_worker`: a worker finishing its queue during shutdown saves its bot, and the watch's `BotChangedEvent` handler built a new executor and thread behind `close_all`; a closed watch now does nothing (`test_a_watch_that_was_closed_builds_no_executor`).

**Merge of master-warrior (2026-10-08, `39325e3`, EPIC-035B):** conflicts were additive (`GridReason` carries `PRICE_FEED_STALE` beside `USER_STREAM_DOWN`; `boot()` starts the price watch, then 035B's `UserStreamWatch`, then 035C's `BotBootRecovery`; the executor's imports lost `LevelState` and `crossed_exit` to the collaborators that took those methods). 035B's `test_user_stream_watch_wiring.py` imported a helper this branch had moved to `bots_module_world.py`, and now imports it from there. `GridExecutor` is 353 lines; this task adds nothing to its public surface beyond `on_price_age_check`.

**Not done / out of scope, by name:**
- `GridExecutor._price()` still prefers the cached last tick, which can be as old as a halt: a resume after a stale HALT plans from it. That is `EPIC-035J` (the reference price has an age).
- The owner's 24 h Testnet run with the chart closed (phase exit evidence): not run.
- Exchange-side stops: `EPIC-026K`.

## Resume
Implemented and committed on `epic-035a-bot-owns-price-subscription`. Remaining: the PR's `ci-local.ps1 -Full` run (read both `gate (Unit)` and `gate (Rest)` job logs), the reviewer session's read, then move this file to `completed/` and mark the epic README and TRACKING rows.
