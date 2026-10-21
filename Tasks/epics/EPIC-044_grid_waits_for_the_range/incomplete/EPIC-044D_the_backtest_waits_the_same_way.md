# EPIC-044D — The Grid's backtest waits and enters by the same rule as the live bot

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-21, through the coordinating session (quoted once in the epic README: *"trường hợp giá out range, thì bot vẫn start, nhưng chờ giá vào trong range thì bot mới bắt đầu init lệnh"* — if the price is out of the range the bot still starts but only begins laying orders once the price is inside).
**Risk:** 🟡 — it changes what a replay reports for a window that starts away from the range.
**Complexity:** M — both replay engines, the benchmark, the result's wording.
**Epic (optional):** [EPIC-044](../README.md)
**SPEC (optional):** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-044B](EPIC-044B_the_state_and_the_entry.md)

---

## 1. Context and problem
ADR D11. `GridReplay` and `FuturesReplay` plan at `first.open` whatever it is.

## 2. Acceptance criteria
- [ ] While waiting, `may_trade_in` is true when the candle's `[low, high]` reaches the range, so its 1-second steps are walked; the bot enters at the first step whose close is inside, plans at that close, and the ladder rests from the next step; no exit is judged before entry; equity is the capital in cash until then; a candle with no 1-second klines is one coarse step and the result says so.
- [ ] The result states that the Futures replay approximates the mark with the trade close.
- [ ] The buy-and-hold benchmark starts at the same step (ADR O3).
- [ ] A test replays one price path through the replay and through the live entry decision and asserts the same entry step, for LONG, SHORT and NEUTRAL.
- [ ] A window that never enters the range returns a result with no fill, and the result says so.
- [ ] The recorded oracles for windows that start in the range are byte-identical.

## 3. Design
ADR D11; `range_position` is the shared definition.

## 3a. Reuse
`range_position`, `steps_for`, the engines' `may_trade_in`.

## 4. Changes, per file
`grid_replay.py`, `futures_replay.py`, `replay_engine.py`, `grid_simulator.py`, the result's wording.

## 5. Testing
Unit tier; the oracle comparison; the parity test.

## 6. Docs touched
`Docs/MODULES/bots/` (the replay's sequence), `Docs/SPEC/SPEC-014_run_a_grid_bot.md`.
