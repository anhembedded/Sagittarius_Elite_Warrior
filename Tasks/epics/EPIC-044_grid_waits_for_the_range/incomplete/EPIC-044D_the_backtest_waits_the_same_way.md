# EPIC-044D — The Grid's backtest waits and enters by the same rule as the live bot

**Status:** 🟡 In progress
**Source:** the owner, 2026-10-21, through the coordinating session (quoted once in the epic README: *"trường hợp giá out range, thì bot vẫn start, nhưng chờ giá vào trong range thì bot mới bắt đầu init lệnh"* — if the price is out of the range the bot still starts but only begins laying orders once the price is inside).
**Risk:** 🟡 — it changes what a replay reports for a window that starts away from the range.
**Complexity:** M — both replay engines, the benchmark, the result's wording.
**Epic (optional):** [EPIC-044](../README.md)
**SPEC (optional):** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-044B](EPIC-044B_the_state_and_the_entry.md) (merged, #682)

---

## 1. Context and problem
ADR D11. `GridReplay` and `FuturesReplay` plan at `first.open` whatever it is.

## 2. Acceptance criteria
- [x] While waiting, `may_trade_in` is true when the candle's `[low, high]` reaches the range, so its 1-second steps are walked; the bot enters at the first step whose close is inside, plans at that close, and the ladder rests from the next step; no exit is judged before entry; equity is the capital in cash until then; a candle with no 1-second klines is one coarse step and the result says so: `waiting_replay.py` → `WaitingReplay`, `test_a_replay_waits_for_the_range.py` (the bound, a price just under it, the opening trade at the entry, the plan at the entry price, flat equity, no exit before entry, a coarse candle that closes outside and one that closes inside).
- [x] The result states that the Futures replay approximates the mark with the trade close (`grid_figures.py` → `_range_wait_notes`; `test_a_futures_result_says_the_mark_is_approximated_by_the_trade_close`).
- [x] The buy-and-hold benchmark starts at the same step (ADR O3): `test_the_benchmark_buys_at_the_entry_step_not_at_the_first_candle`.
- [x] A test replays one price path through the replay and through the live entry decision and asserts the same entry step, for LONG, SHORT and NEUTRAL: `test_the_replay_and_the_live_bot_enter_on_the_same_step.py` (Spot LONG and Futures LONG, SHORT, NEUTRAL × a plain climb, the bound itself, a wick that reaches the range and closes outside).
- [x] A window that never enters the range returns a result with no fill, flat equity and says so (Spot and every Futures direction; no funding charged).
- [x] The recorded oracles for windows that start in the range are byte-identical: `engine_starting_at` builds the venue's engine itself when the first candle opens inside, and `test_the_spot_oracle.py` and every existing replay test pass unchanged.

## 3. Design
ADR D11; `range_position` is the shared definition.

## 3a. Reuse
`range_position`, `steps_for`, the engines' `may_trade_in`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/domain/grid/waiting_replay.py` (new) | `engine_starting_at`, `WaitingReplay` |
| `bots/domain/grid/replay_engine.py` | `waited_for_range` and `range_entry`, concrete defaults on the port |
| `bots/domain/grid/grid_fill_rule.py` | `PriceStep.close` (a 1-second kline's close, a coarse step's candle close) |
| `bots/domain/grid/grid_backtest_result.py`, `grid_simulator.py` | `RangeEntry`, the two result fields, the walk starts through `engine_starting_at` |
| `bots/domain/grid/grid_figures.py` | the words: where it entered, or that it never did, and the Futures mark limit |

`grid_replay.py` and `futures_replay.py` are unchanged: the venue's engine is built at the entry through the same factory, so a third kind needs nothing.

## 5. Testing
`tests/unit/modules/bots/domain/grid/test_a_replay_waits_for_the_range.py` (22 cases), `tests/unit/modules/bots/application/services/test_the_replay_and_the_live_bot_enter_on_the_same_step.py` (12), the spot oracle unchanged. Mutation-checked: an exclusive bound, entering on any step, a wait that never walks the candle: each turns tests red.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/VOCABULARY/README.md` (the Grid backtest row).

## Implementation notes (written when done)
- The wait is a wrapper over the venue's engine, built at the entry step's close with a one-price synthetic first candle, because both engines plan and open in their constructors; that keeps them unchanged and the oracles untouched.
- Before the entry the wrapper keeps an unstepped probe engine planned at the nearest range edge, only to give the result a plan and the shape of an empty outcome (a Futures outcome keeps its funding terms, with nothing charged).
- Stated limit (ADR D11): the entry is judged on the trade close; a live Futures bot judges it on the mark.
