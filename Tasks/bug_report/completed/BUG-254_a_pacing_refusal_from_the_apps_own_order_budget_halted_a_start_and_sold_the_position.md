# BUG-254 — A start was refused by the app's own order budget (`owner_budget_spacing`), and the position it had opened was sold at market

- **Reported:** 2026-10-21 (the owner, from the desktop app on Futures Mainnet; coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`)
- **Severity:** 🔴 P1 — real money: the start closed a 0.18 BNB position at market for a loss of -0.125 USDT, and would do so on any start whose ladder orders are stamped unevenly
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** The Grid start read trading's `owner_budget_spacing` (the app's own 250 ms cap) as a fatal `REFUSED`: the pacer spaced the bot's turns exactly 250 ms apart, but trading stamps an order a moment after its turn that differs per order, so two stamps landed under 250 ms apart; `classify_submit` now reads a spacing refusal as `PACED`, `send_paced` takes another turn and resends (3 times), and a rate refusal or a spacing that kept missing pauses the bot as `RATE_LIMITED` instead of closing the position.
- **Context:** Start a Futures Grid (`Docs/SPEC/`) → bots (`src/modules/bots/`) → `application/services/orders/` (`BotOrderGateway`, `order_outcome.py`, `paced_send.py`); trading's `application/orders/execute_order/handler.py` stamps the order
- **Environment:** Windows desktop app, Futures Mainnet, `master-warrior` 970b77b. The VPS (testnet) never met it: plausibly its slower round trip to Binance makes the stamp lag steadier. Not captured: the app's Windows timer resolution.

## Reproduction
The owner started Grid bot xvp0x7: BNBUSDT LONG, range 698–807, 27 grids, 34 USDT, 7x, stop loss 658, take profit 822. Reproduced without the exchange: `tests/integration/modules/bots/test_a_burst_of_orders_is_not_refused_by_the_budgets_spacing_on_the_fake_exchange.py` runs the composed app and the production pacer, handler and policy on a virtual clock, with trading stamping each order a different moment after its turn. Frequency in the app: Not established beyond the one run; the cause is a race, so it recurs whenever an order is stamped sooner after its turn than the previous one was.

## Symptom
```
19:20:57,081 ExecuteOrderCommand            (opening market slice 0.18, filled 746.31)
19:20:58,437 protective stop SEW-xvp0x7-70aaa955d7 SELL at 658 saved before it is sent
19:20:58,679 ExecuteOrderCommand -> 58,785 Live order submitted; L14 BUY 0.01 @ 744.240
19:20:58,930 ExecuteOrderCommand -> 59,047 Live order submitted; L16 SELL 0.01 @ 750.850
19:20:59,180 ExecuteOrderCommand; L13 BUY 0.01 @ 740.930 -> owner_budget_spacing
19:20:59,207 WARNING STARTING -> HALTED on start_refused (start_refused: L13 BUY: owner_budget_spacing)
19:21:02,775 the exit of start_refused closed the position, 0.00 left; result -0.12534029
```
Expected: the order waits for its spacing and is sent; the start finishes.

## Root cause
Read at `master-warrior` 970b77b. Two components judge the same spacing from different reference points. The pacer (`src/modules/bots/adapters/monotonic_order_pacer.py:60-75`, `MonotonicOrderPacer.wait_turn`) reserves each turn `spacing` after the previous *turn* on the monotonic clock, records the scheduled instant (not the instant the sleep returned) and returns. Trading stamps the order later and by another clock: `src/modules/trading/application/orders/execute_order/handler.py:198` takes `datetime.now(UTC)` after the preview and after `live_submission_guard()` (held across the whole evaluate→submit→record of every bot of the venue, `:175`), judges `owner_budget_spacing` against the previous stamp (`src/modules/trading/domain/policies/trading_limit_policy.py:167-171`, `owner_order_ledger.py:109-111`) and records the stamp (`handler.py:243`). The gap trading sees is `spacing + lag(n) - lag(n-1)`, where lag is turn→stamp; any order whose lag is shorter than its predecessor's by more than the pacer's slack (none: the pacer plans exactly 250 ms) is refused. L16→L13 was 58.930→59.180, exactly the spacing. The refusal is classified `REFUSED` (`order_outcome.py` `_refusal`), which `grid_order_failure.py` `_refuse` turns into `START_REFUSED`, whose exit closes the position.

Two defects, one mechanism: (1) a race that no predictor can win, since the stamp is taken after the turn; (2) the app treating its own pacing as a verdict on the order. The first cannot be removed by making the pacer exacter (it would still forecast a stamp taken later, under a lock the pacer does not hold); the verdict of the judge that stamps must be the one that counts. Every path that places orders in a burst (the ladder, counter-orders after fills, re-arm, resume) goes through `BotOrderGateway._submit_paced`, so the repair is at that one seam. Exits (`_exit`, the protective stop) take no turn and trading exempts them from pacing (`trading_limit_policy.py:126-142`); they cannot meet it. The gate was green while the defect was live: `BUG-238`'s journey models a stamp lag that is the same for consecutive orders (`VirtualTime.early_stamp_lag`, which "never shortens the spacing"), so the one case that shortens it was untested.

## Fix
- `order_outcome.py`: `pacing_outcome` reads `owner_budget_spacing` as the new `OrderOutcomeKind.PACED` (`retry_after`: the spacing trading found missing, from the facts it judged) and `owner_budget_rate` as `RATE_LIMITED` for the budget's window. No other refusal changes.
- `paced_send.py` (new): `send_paced` takes a turn, sends, and on `PACED` takes another turn and sends again, up to `PACING_RETRIES` (3); then answers `RATE_LIMITED`, which the Grid already waits out in AWAITING_RECOVERY and resumes from (`EPIC-042F`). `PACED` never leaves the gateway.
- `bot_order_gateway.py`: `_submit_paced` uses `send_paced` and notes the pause so a halt schedules its resume by it.
- The owner's caps (150 open orders, 60 orders/min, 250 ms) are untouched, and the pacer is unchanged.
- Judgement the owner asked for: a pacing or rate refusal from the app's own budget is never a terminal `start_refused`. The spacing is waited for and retried; a rate refusal (the pacer's window margin was overrun) waits as the exchange's pause does. Price paid, written in `Docs/MODULES/bots/06-runtime.md`: a rate pause lasts the budget's window, and when it hits the opening's second slice, before the stop stands, the position is open and unprotected for it. `open_orders` (`owner_budget_open_orders`) is a capacity, not a pace, and stays `REFUSED`.

## Regression test
- `tests/integration/modules/bots/test_a_burst_of_orders_is_not_refused_by_the_budgets_spacing_on_the_fake_exchange.py::test_a_start_whose_orders_are_stamped_unevenly_lays_its_ladder_and_keeps_its_position` (3 jitters) — failed before the fix with `start_refused: opening slice 2: owner_budget_spacing`, the state STOPPED and the position sold; passes after. Real executor, pacer, handler and policy; only the clock is virtual.
- Same file, `test_turns_that_keep_missing_pause_the_start_and_sell_nothing`: the exhausted path pauses and sells nothing.
- `tests/unit/modules/bots/application/services/test_bot_order_gateway_own_pacing.py`: retry, exhaustion, rate, and that other refusals still halt.

## Verification
Regression test red at 970b77b, green after (see the pull request). Positive proof the mechanism ran: with the fix the log of the journey carries `trading found the order sooner than the budget's spacing after the previous one, short by 0:00:00.030000; it takes another turn (1 of 3) [order-pacing]` (DEBUG) before the start reaches RUNNING. Commit tier and the gate: in the pull request.

## Suggested next steps
None open. Related, separate: BUG-255 (the plan and the start judge the liquidation from different inputs).
