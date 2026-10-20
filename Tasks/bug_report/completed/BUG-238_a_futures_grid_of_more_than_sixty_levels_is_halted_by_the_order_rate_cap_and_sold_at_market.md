# BUG-238 — A Futures grid of more than 60 levels is refused `owner_budget_rate` while laying its ladder, then closed at market for a loss

- **Reported:** 2026-10-20 (the owner's journal of the VPS run, relayed by the delivery coordinator; found on `master-warrior` at `03e5dc5`)
- **Severity:** 🔴 P1 — real (testnet) funds lost to a plan the app itself accepted: 2.55 USDT of fees and spread on one run, and every grid with more than 60 levels meets the same wall.
- **Status:** ✅ Fixed (2026-10-20)
- **Board:** A Futures grid of 60+ levels was halted `start_refused: L61 SELL: owner_budget_rate` while laying its ladder and sold at market (−2.55 USDT). Cause: the order pacer kept orders only 250 ms apart (up to 240 a minute) while trading refuses the 61st order inside a minute. Fixed: the pacer holds the venue's orders to the budget's rate too (`OrderPacing`, `grid_pacing`), so a ladder longer than the rate is laid over more than a minute.
- **Context:** Bots → Grid on a Futures venue, Start (`Docs/SPEC/`: start a bot) → `src/modules/bots/` → `application/` (`kinds/grid/start/`, `services/orders/`) and `adapters/` (the order pacer), against `src/modules/trading/domain/policies/` (the owner budget)
- **Environment:** VPS, Futures Testnet, `BNBUSDT`, bot `6z20d2` ("BNB_FUTURE_TEST_83"); app at `master-warrior` `03e5dc5`. Owner budget caps are the defaults of ADR O1 (`trading.bot_limits.max_orders_per_minute` = 60, 250 ms spacing, 100 open orders). Never include credentials.

<!-- Follow .claude/rules/create-bug-report-rule.md for filing and closure; fix-bug-rule.md governs the fix. -->

## Reproduction
1. On a Futures testnet venue create a Grid with arithmetic spacing, a range of 661–948 (spacing 0.37%–0.52%), so the ladder has more than 60 levels; the capital and leverage are ones the Design step accepts.
2. Start it. The opening market order fills (3.78 BNB at 731.69), the protective stop stands, the ladder is laid level by level.
3. Expected: every level rests and the bot is RUNNING. Actual: the 61st order of the minute is refused and the bot closes the position.

Frequency: every time the start needs more than 60 orders inside one minute. Reproduced in the composed app on the strict fake exchange by the regression test below: red before the fix with the same halt and market close.

## Symptom
The owner's journal (times UTC+7; run started 13:26:17 UTC):

```
Bot 6z20d2: HALTED -> STOPPING on stop (start_refused: L61 SELL: owner_budget_rate; any position is closed at market, as a leveraged position is never left bare)
```

Then about 30 `Order cancelled ... SEW-6z20d2-*` lines, the 3.78 BNB closed at market in 6 exit slices, the protective stop dropped, the bot STOPPED: `[exit-closed] ... result -2.55269447`.

Expected instead: a ladder that is valid by every other rule is laid completely; a rate ceiling means wait for the window, not halt and sell.

## Root cause
At `03e5dc5`:

- `src/modules/bots/application/kinds/grid/grid_budget.py:47` (`grid_budget`) asks trading for `max_orders_per_window = caps.max_orders_per_minute` (60) over a one-minute window.
- `src/modules/trading/domain/policies/trading_limit_policy.py:160` (`_owner_budget_checks`) refuses an order when `orders_in_window + 1 > max_orders_per_window` (`owner_budget_rate`). The check is correct and stays.
- The only pacing was `src/modules/bots/adapters/monotonic_order_pacer.py:38` (`MonotonicOrderPacer.wait_turn`), which kept orders `min_order_spacing` (250 ms) apart: up to 240 orders a minute, four times the rate the bot had itself asked for. `grid_executor_factory.py:180` built the pacer from the spacing alone, so the rate never reached the pacer.
- `order_outcome.py:144` (`_refusal`) files `owner_budget_rate` under `REFUSED`; `grid_order_failure.py:101` (`_refuse`) turns that into `start_refused` while STARTING, and a Futures bot halting closes its position at market.
- The Design step (`grid_budget_problem`) judges a ladder by the orders it keeps open (`max_open_orders`), which is right: the ladder fits the cap; what was missing was the pace.

The gate was green while the defect was live: no test laid a ladder longer than the rate (the worlds' pacer waits for nothing and trading's clock is the machine's), so the unit and integration nets could not meet the rate window. Not a case study: the blind spot was this one path, and the regression test closes it (virtual time through the pacer and trading's window).

## Fix
- `contracts/i_order_pacer.py`: `OrderPacing` (spacing, max orders, window) is what a pacer is built from.
- `application/kinds/grid/grid_budget.py`: `grid_pacing(budget)` reads it off the budget the bot registers, so trading's figure and the pacer's cannot differ; `grid_executor_factory.py` builds the gateway's pacer from it.
- `adapters/monotonic_order_pacer.py`: a turn is also held until the window after the turn `max_orders` places back, kept `STAMP_JITTER` (2 s) longer than trading's because trading stamps an order a moment after the turn. One `[order-pacing]` line per streak says the rate is now the pace.
- `adapters/venue_order_pacers.py`, `composition/executor_bindings.py`: the pacers are keyed by venue and pacing.
- Not done, by decision: the 60/minute cap (an owner-approved setting, ADR O1) and the policy check are untouched; no safety net maps a residual `owner_budget_rate` to a pause, because the recovery for a pause cancels and re-lays the whole ladder against the same rate.

It is the mechanism, not the symptom: every order that builds a ladder or opens a position (the start, a resume's re-lay, the counter-orders of a burst of fills) takes its turn on the one pacer, so the whole family of "more than 60 *paced* orders in a minute" is covered, not only the start. Exits take no turn and a Spot exit still counts in trading's window; that is outside this fix (reviewer note on the pull request).

## Regression test
`tests/integration/modules/bots/test_a_futures_grid_of_more_than_sixty_levels_is_laid_in_full_on_the_fake_exchange.py::test_a_ladder_of_more_levels_than_the_rate_allows_is_laid_in_full_and_never_sold` — the composed app on the strict fake Futures exchange, the production pacer on a virtual clock that trading's rate window also reads. Failed before the fix for this reason: `STARTING -> HALTED on start_refused (start_refused: L4 BUY: owner_budget_rate)`, then `halted (start_refused); closing the position [halt-closes-position]` (the owner's sequence). Passes after: RUNNING, all 70 levels rest, the position is kept, nothing cancelled, more than a minute of virtual time paced.

Also `tests/unit/modules/bots/adapters/test_monotonic_order_pacer.py` (the 61st turn waits for the window; no window holds more than the rate; a quiet window resets; a rate of one), `tests/unit/modules/bots/application/kinds/grid/test_grid_pacing.py` (the pacing is the budget's; a ladder past the rate has no Design problem; one past the open-order cap is still refused). Mutation: removing the rate hold turns three of the pacer's tests red.

## Verification
Local, at the fix commit: the regression test red before and green after (above); the commit tier (`ci-local.ps1 -SkipTests`) PASS; `tests/unit/architecture`, `tests/unit/modules/bots`, `tests/unit/support` and `tests/integration/modules/bots` green. The full gate is GitHub Actions' `ci-local.ps1 -Full` run on the pull request's head; see the pull request for the sequences and the run.

