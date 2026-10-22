Status: Current

# 005 — A trigger price is a limit order on the entry: one gate, and the state machine as the latch

Teaches the design of ADR 046, [`DECISION_2026-10-22_a_grid_trigger_price.md`](../../Tasks/epics/EPIC-046_grid_trigger_price/DECISION_2026-10-22_a_grid_trigger_price.md) (`EPIC-046`), built in #724 and `EPIC-046B`. It builds on [004](004_waiting_is_a_state_a_bot_that_starts_but_does_not_trade_yet.md).

## 1. The problem

The owner, 2026-10-22: *"tui muốn kích hoạt giống limit, giá tốt hơn giá đó mới kích hoạt grid"* ("activate like a limit order: only at a price better than that one"). A Grid already waited for its range (`EPIC-044`), but inside the range it laid its ladder at whatever the price was. With real money the entry price decides the whole run's cost basis, so the owner wanted the same promise a limit order gives: never worse than X.

## 2. Constraints

- The entry was already decided in three places (the start, the waiting bot's price watch, the Resume of a flat bot), and the backtest made the same decision a fourth way. A fifth condition copied into each would drift (P3).
- 17 consumers read the lifecycle state; a new state costs a review of every hand-written state set.
- A bot that has traded must never go back to waiting by itself: that would leave a ladder half-built and its stop loss watching nothing.
- The backtest must enter on the same step as the live bot, or its numbers lie.

## 3. Solutions considered

| Option | For | Against |
| :--- | :--- | :--- |
| A new state `AWAITING_TRIGGER` | A precise name | Same rows, same watches, same restart as `AWAITING_RANGE`: two copies of one wait |
| A flag `triggered: bool` on the bot's record | Explicit latch | A second source of a fact the state already holds; must survive every restart path |
| A trigger condition added at each call site | Smallest diff | Four copies of the rule, one of them the backtest |
| **One entry gate the wait asks; the lifecycle is the latch** | One rule, every caller; no new state or flag | The state's name says "range" for a wait that may be on the trigger |

## 4. The choice and why

One pure function decides whether a price may open the ladder: the range first, then the trigger on the better side (LONG at or below it, SHORT at or above it). Every place that decides an entry calls it, the backtest included. The latch is free: only the waiting state ever asks the gate, so once the bot has left it the trigger is never consulted again, which is exactly how a filled limit order behaves.

## 5. How it is implemented

```
price ──► entry_gate(params, price) ──► OUTSIDE_RANGE | TRIGGER_NOT_MET | OPEN
              │ (grid_entry_gate.py)
   asked by:  GridRangeEntry.waits_for_the_range   (the Start)
              GridRangeEntry.on_price / _attempt    (the wait, confirmed by a fresh book)
              GridResumeSequence._gate_closed       (a Resume of a bot holding nothing)
              WaitingReplay._opens / entry_band     (the backtest)
```

`src/modules/bots/domain/grid/grid_entry_gate.py` → `entry_gate`, `trigger_met`, `entry_band`, `entry_price`. The Plan draws the ladder at `entry_price` (where the bot will enter), and the waiting sentence (`contracts/grid_ladder_texts.py` → `waiting_text`) says "Waiting for the price ≤ X within L–U".

## 6. Risks and failure modes

- **A gap past the trigger and out of the range.** A LONG whose price falls from 130 to 95 in one tick does not enter: 95 is better than the trigger but outside the range. A plain limit order would have filled. A ladder below its range is meaningless, so the range wins; the SPEC says so.
- **A Resume of a flat bot asks the trigger again.** The code cannot tell "never traded" from "traded and flat again", and does not need to: neither holds anything to protect, so the owner's limit applies.
- **A save from an editor that rebuilds the definition** would silently drop a key it has no field for: found in review, fixed by giving the editor the field.

## 7. Limits

A single price threshold. A dwell ("below X for a minute"), a crossing (a stop-entry, which buys on the way *up*) or a NEUTRAL "touch" trigger are different order types; the gate's enum is where they would land.

## 8. Names to know

Limit order versus stop order; guard condition (a transition taken only when a predicate holds); latch; single source of truth; level-triggered versus edge-triggered; backtest-live parity.

## 9. Interview questions

1. *Why not a flag for "already triggered"?* — The state machine already knows: only the waiting state asks. A flag would be a second copy of that fact, with its own restart bugs.
2. *Why is the range judged before the trigger?* — The ladder only means something inside the range; a better price outside it is not an entry, it is a different trade.
3. *How do you keep a backtest honest about a live rule?* — Make both call the same pure function, and keep a test that drives one price path through both and asserts the same entry step.
4. *What is the difference between a limit and a stop entry?* — A limit enters at a better price than now (buy lower); a stop enters at a worse one (buy on a breakout). The owner asked for a limit.

## 10. Read more

- The OMG UML specification, the State Machines chapter: transitions with guard conditions.
- Binance's documentation of its order types (limit, stop-limit): the exchange's own definitions of the two entries.
