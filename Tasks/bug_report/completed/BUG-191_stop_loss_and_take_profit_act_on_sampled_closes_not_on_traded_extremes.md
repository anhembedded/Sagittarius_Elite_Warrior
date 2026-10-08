# BUG-191 — A Grid bot's stop loss did not fire on a wick below it: stop loss and take profit act on sampled closes, not on the traded extremes

- **Reported:** 2026-10-08 (the owner, live on Spot Mainnet, via the coordinator session)
- **Severity:** 🔴 P1 — real money: the safety exit the owner configured did not run, and the bot kept a position through a fall it was set to exit
- **Status:** ✅ Fixed (2026-10-08)
- **Board:** 2026-10-08: Fixed: the bot's exit check compared one sampled kline close per push with the stop loss and take profit, so a wick between two pushes never fired it; the tick now carries the kline's low and high (`PriceTick`) and `GridPriceReaction` checks the range the bot observed while watching (`GridTickExtremes`), so a start never fires on a wick from before the run.
- **Context:** [SPEC-014 run a grid bot](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → Module `src/modules/bots/` → `application/event_handlers/` and `application/services/` (the one tick path), `domain/grid/grid_ladder.py`
- **Environment:** Spot Mainnet, ETHUSDT, the owner's desktop app; app commit `d3be4f7` (master-warrior). Engine commit not captured.

## Reproduction
Preconditions: a Grid bot RUNNING with a stop loss and a take profit. The 2026-10-08 bot: ETHUSDT, lower 2511, upper 2661, 6 geometric grids, stop loss price 2419, take profit price 2801.

1. Price falls through the stop loss and recovers within the 1–2 s between two kline pushes.
2. Expected: the bot runs Stop with *sell base at market*, reason STOP_LOSS.
3. Actual: the bot stays RUNNING, holds about 0.0143 ETH and its 6 SELL orders keep resting. Price recovered to about 2430–2434.

Observed: once, on the owner's account. The unit-level reproduction (a kline whose close stays above the stop and whose low is below it) is deterministic.

## Symptom
The app's own live 1h chart, fed by the same Binance kline stream, shows a wick below 2419 (low about 2415–2417). The bot did not stop. (The owner's log was not attached to the report; the numbers are the owner's.)

## Root cause
`BotEventRouter.on_tick` (`src/modules/bots/application/event_handlers/bot_event_router.py:108`) passed only `Decimal(str(candle.close_price))` to `executor.facts.on_tick`; `GridPriceReaction.on_tick` (`src/modules/bots/application/services/grid_price_reaction.py`) compared that one price with the exits through `crossed_exit` (`src/modules/bots/domain/grid/grid_ladder.py`). The bot's own stream is the 1m kline stream (`bot_price_watch.py`), which Binance pushes every 1–2 s with the close at that moment (`binance_websocket_service.py:258`). A wick between two pushes is never a close; the kline's `low_price` / `high_price` record it and were ignored. `grid_replay.py` compares candle low/high with the exits, so a backtest stopped where the live bot did not. Confirmed as described; no deviation. The gate was green because every existing test fed a tick whose close was the whole story (`low == high == close`), so no net distinguished a sampled close from a traded range; no case study (the same blind spot is not open elsewhere: the other tick consumers are listed below).

Other consumers of `MarketTickEvent` / `on_tick` that decide something: `WakeExitCheck` (a price read from the venue's book after a sleep: a lone price, `PriceTick.at`, no range exists to carry) and `GridFacts.on_tick`, which all go through `GridPriceReaction`; `bot_tick_feed.py`, the Market/Desk charts and `market_presenter` are display only; the strategy path's `on_tick` is a closed-candle commit (`BUG-164`) and makes no stop/take decision.

## Fix
- `contracts/bot_price_tick.py`: `PriceTick(last, low, high, bar_start)`, the value type `IBotFacts.on_tick` now takes instead of a bare price; `PriceTick.at(price)` for a lone price.
- `domain/grid/grid_ladder.py`: `crossed_exit_in_range(low, high, stop, take)` is the one comparison rule; `crossed_exit(price, …)` is its degenerate range.
- `application/services/grid_tick_extremes.py`: `GridTickExtremes`, the guard. A kline update carries the bar's low/high from its open, so the first update after a start, resume or restart holds extremes from before the bot ran. Rule: the first update of a run counts by its close only (and remembers the bar's extremes); in the same bar a low lower / high higher than the last heard counts; the first update of a later bar counts whole; an older bar counts by its close. The state resets whenever the bot is in a state that does not watch exits, so each run starts afresh.
- `grid_price_reaction.py`: the one place every tick goes through checks the observed range; STARTING and RECOVERING use the same rule (they may already hold base and the guard already keeps a pre-start wick out; a start rule that ignores wicks would leave exactly the window this bug lived in). When an exit fires on an extreme rather than the close it logs one INFO line `[exit-on-extreme]` (close, low or high, threshold); the Stop it starts leaves every watching state, so it is once, and nothing logs per tick.
- `bot_event_router.py` builds the tick from the kline; `wake_exit_check.py` passes `PriceTick.at(price)`. Existing tests pass `PriceTick.at(price)`.

Known limit: a wick that trades during a feed gap *within the same bar* is counted when the feed returns (it happened while the bot was running); one before the first update of a run is not.

## Regression test
`tests/unit/modules/bots/application/event_handlers/test_bot_event_router_extremes.py` (real router and executor over the simulated venue; no mock stands in for the check): `test_a_wick_below_the_stop_loss_between_two_pushes_stops_the_bot`, `test_a_wick_above_the_take_profit_between_two_pushes_stops_the_bot`, `test_a_wick_in_the_first_push_of_a_new_bar_counts`, `test_a_new_extreme_after_a_pre_watch_wick_does_count`, `test_a_wick_while_starting_stops_the_bot_like_one_while_running` — all five failed before the fix because the bot stayed RUNNING / STARTING with a close inside the band; they pass after. `test_an_extreme_from_before_the_bot_watched_never_fires_its_exit` (stop and take profit) holds before and after: it guards the new behaviour from firing on a start. `tests/unit/modules/bots/application/services/test_grid_tick_extremes.py` covers the guard's rules directly.

## Verification
- Red before the fix, green after: 5 failed / 2 passed before; 7 passed after.
- `tests/unit/modules/bots`, `tests/unit/architecture`, `tests/integration/modules/bots`: 2241 passed.
- Commit tier `scripts/ci-local.ps1 -SkipTests`: RESULT PASS (ruff, format, mypy, reference check).
- Positive proof the mechanism ran: `Bot a3f9c1: stop_loss fires on a wick, not on the close: close 100, low 89, threshold 90 [exit-on-extreme]` and the take-profit twin (close 100, high 151, threshold 150), at `grid_price_reaction.py:90`, from the regression tests.
- Not run: the full `-Full` gate locally (GitHub Actions runs it on the PR head); nothing was run against a real exchange.
