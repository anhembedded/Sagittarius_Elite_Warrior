# EPIC-035A — The bot owns its price subscription, with a staleness rule

**Status:** 🔵 Planned
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
- [ ] Every bot that is not stopped (STARTING, RUNNING, PAUSED, RECOVERING, HALTED, ERROR, STOPPING) owns a price stream for its symbol and venue market, started when the bot enters such a state and released when it reaches STOPPED or DRAFT. The stream is requested through market_data's contract (`IMarketStream`) with a bots-owned `owner_id`, never by reaching into the Binance adapter.
- [ ] The stream does not depend on any chart: closing the chart, selecting another bot or switching modes leaves SL/TP watched.
- [ ] The stream is the bot's own venue and market: a Testnet tick never reaches a Mainnet bot and a Spot tick never reaches a Futures bot (`BUG-172` stays closed).
- [ ] A bot in RECOVERING and in STARTING evaluates stop-loss / take-profit on the ticks it receives (the exit then runs the existing `_run_stop` path, taking the ladder off).
- [ ] **Staleness rule:** while a bot is in a state that holds orders, no tick for N seconds moves it to HALTED with a named `GridReason` (for example `PRICE_FEED_STALE`) whose detail names the last tick's age. N is a named constant with a default derived from the stream's own cadence (the audit suggests tens of seconds; the value is chosen in the PR and recorded here).
- [ ] The staleness check uses a monotonic clock and an injected clock port, not `time.sleep`; it does not fire for a bot that has not yet received its first tick within the start grace, which is a separate, named, bounded wait.
- [ ] A fresh tick after a staleness HALT does not resume the bot by itself; the user's confirm-resume path stays the only way back.
- [ ] Two bots on the same symbol and venue share the market stream (one subscription per symbol and market, released when its last owner leaves), as `IMarketStream`'s owner model already allows.
- [ ] Stopping the app releases every bot-owned stream; the sanity tier shows a clean shutdown with no `ResourceWarning`.

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

Architecture guards: `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/architecture -q`. Not run yet. Verification of delivery follows `ci-rule.md` §1 (feature: `-Full` run on the PR head, then a reviewer session).

## Resume
Not started. First action: write `test_a_stop_loss_is_watched_with_no_chart_open` and run it red.
