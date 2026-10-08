# EPIC-035T — A rejected counter order does not kill the grid

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M11 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — one exchange rejection ends a healthy ladder
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035C

---

## 1. Context and problem
Audit M11: an exchange error on a counter order (`LOT_SIZE`, `PERCENT_PRICE`, `MIN_NOTIONAL`, `-2010`) raises, the bot goes to ERROR and the whole ladder is cancelled; counter orders are not re-checked against percent price before submission; `-2010` has no named mapping. Cited: `src/modules/bots/application/services/bot_order_gateway.py:271-305`, `src/modules/trading/adapters/binance/binance_error_translator.py:323-335`.

**Re-verified on `d563c0f` (2026-10-08).** The citations are stale (the translator is 91 lines; the gateway's submit is `_submit`, near line 300), the mechanism is not.
- **Holds:** `BotOrderGateway._submit` turned every exchange rejection that was not about the key or the symbol into `OrderOutcomeKind.FAULT`; `fail_with` answered a FAULT with `BotLifecycleEvent.FAULT` (ERROR) and `GridTaskGuard` then parked (cancelled) the whole ladder. A trading-side refusal on the minimum notional or the percent-price band (`REFUSED`) halted the bot the same way. Reproduced red before the change by `test_grid_counter_order_rejection.py` (ERROR / HALTED where RUNNING is wanted) and by the existing `test_any_other_refusal_that_raised_is_still_a_fault`, which pinned a `PRICE_FILTER` rejection to ERROR.
- **Does not hold as written:** "counter orders are not re-checked against percent price before submission". Trading's submit path already refuses an order outside the `PERCENT_PRICE_BY_SIDE` band and under `minNotional` before any request (`ExecuteOrderPriceRejection`, `ExecuteOrderNotionalRejection`; `BUG-147`, `BUG-090`), for the bot's orders as for any other. The counter order is validated against the exchange filters already; what was missing is the bot surviving the answer, so this task adds no second check.
- **Holds:** `-2010` had no mapping in the translator (fell to `UNKNOWN`).

## 2. Acceptance criteria
- [x] A counter order is validated against the exchange filters (including percent price) before it is sent. Already true on master through trading's gates (see Context); locked here by `test_a_counter_order_trading_refuses_on_a_filter_keeps_the_bot_running`, which drives both gates and asserts the bot's answer.
- [x] A rejected counter order leaves that level EMPTY with a named reason and the bot keeps running; repeated rejections of the same level HALT with the existing level rule. Evidence: `test_a_rejected_counter_order_leaves_the_level_empty_and_the_bot_running`, `test_the_rejection_is_named_with_the_rung_and_the_exchanges_words`, `test_the_same_rung_refused_twice_within_a_minute_halts` (`LEVEL_KEEPS_ENDING`, the existing rule and its one-minute window), `test_the_same_rung_refused_again_after_a_minute_keeps_the_bot_running`. All red before.
- [x] `-2010` maps to a named reason: `OrderRejectionReason.NEW_ORDER_REJECTED`. Evidence: `test_minus_2010_has_a_named_reason`. The mapping is unverified against a live answer, like its neighbours in the translator (egress to `*.binance.*` is blocked in this sandbox).

## 3. Design
Reuse, not a parallel path. The refusal travels the existing `OrderOutcome` → `fail_with` route unchanged; the one decision that is new is made in the one place that already makes the equivalent decision for the symbol's status, `GridLadderPlacer._place`.
- **One outcome kind, `ORDER_INVALID`**, for "the order's own numbers were refused": the exchange's `LOT_SIZE`, `MIN_NOTIONAL`, `PRICE_FILTER` and `-2010` (through `_NAMED_REFUSALS`, the table that already names the symbol and key refusals) and trading's two filter gates (`_refusal`). It is the only kind added; `REFUSED` stays "any other gate" (a limit, a lease), which still halts. Outside a RUNNING ladder `ORDER_INVALID` takes the `REFUSED` route in `fail_with` (a refused start halts as `START_REFUSED`, a refused exit slice as `EXIT_SLICE_FAILED`), so no state changes meaning except that an exchange rejection is no longer reported as an ERROR fault.
- **A RUNNING ladder** leaves the rung EMPTY: `rejected_counter` (domain, `grid_level_rejection.py`, pure) stamps the rung's `ended_at`, sets `GridReason.COUNTER_ORDER_REJECTED` with the exchange's words, and returns a `LEVEL_KEEPS_ENDING` halt when the rung was refused already inside `LEVEL_END_WINDOW`. The level rule is `on_end`'s, so the saved `ended_at` is read by both. It is a new file because `grid_reactions.py` is at 378 lines (400 ceiling).
- **No retry timer.** The rung is offered an order again only when its neighbour fills again, which is also what makes the "refused twice" rule observable. A price knowingly paid, in the module docstring: until then that rung rests nothing and the base or quote it would have used waits; the bot's reason says so.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/binance_error_translator.py` | `-2010` → `NEW_ORDER_REJECTED` |
| `src/modules/trading/contracts/order_rejection_reason.py` | the new member |
| `src/modules/bots/application/services/order_outcome.py` | `ORDER_INVALID`; the four exchange reasons and the two gates classify to it |
| `src/modules/bots/application/services/bot_order_gateway.py` | docstring only (the kind is listed) |
| `src/modules/bots/domain/grid/grid_level_rejection.py` (new) | `rejected_counter`, the rung's reaction |
| `src/modules/bots/domain/grid/grid_runtime.py` | `GridReason.COUNTER_ORDER_REJECTED` |
| `src/modules/bots/application/services/grid_ladder_placer.py` | a RUNNING `ORDER_INVALID` leaves the rung empty |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | the behaviour row |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test was shown red before the change. Unit tier, `tests/unit/modules/bots/application/services/test_grid_counter_order_rejection.py` against the real executor through the real factory and the simulated venue, and `test_binance_error_translator.py`:
- the rung is left EMPTY and the bot RUNNING for each of `LOT_SIZE`, `MIN_NOTIONAL`, `PRICE_FILTER`, `NEW_ORDER_REJECTED` and for both trading gates (red before: ERROR / HALTED);
- the reason names the rung and the exchange's words; nothing is cancelled;
- a refusal about the bot (`SYMBOL_LEASED`) still halts; an unnamed rejection (`UNKNOWN`) is still a fault;
- the same rung refused twice within a minute halts with `LEVEL_KEEPS_ENDING`; again after two minutes it does not;
- during the first laying of the ladder a rejection is a refused start (HALTED, `START_REFUSED`), not an ERROR;
- the rung remembers when it was refused (it is in the saved record).

Green after: the above, the whole `tests/unit/modules/bots` and `tests/unit/modules/trading`, `tests/unit/architecture` (703); the commit tier PASS (`scripts/ci-local.ps1 -SkipTests`, log read for `FAILED|ERROR|Traceback|ResourceWarning`: none).

## Implementation notes
- **A deliberate behaviour change, one test re-aimed on purpose, not weakened.** `test_any_other_refusal_that_raised_is_still_a_fault` (`test_grid_symbol_status.py`) pinned a `PRICE_FILTER` rejection to ERROR. That is exactly what this task changes, so the test keeps its purpose (an *unnamed* refusal is still a fault) with `UNKNOWN`, and the `PRICE_FILTER` path is covered by the new file.
- A refusal that reaches a stop's market slice as `ORDER_INVALID` is now reported "unsold" instead of "possibly unsold (the request may have executed)": the exchange read the order and refused it, so it is certain.
- Not done, by design: no retry of the refused rung on a timer and no re-read of the symbol's filters (that is `EPIC-035U`).

## Resume
Done. Nothing owed.
