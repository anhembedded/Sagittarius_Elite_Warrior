# EPIC-046B — Every place that shows a waiting Grid names its trigger

**Status:** ✅ Done (2026-10-22)
**Source:** the owner, 2026-10-22 (see the [epic](../README.md)).
**Risk:** 🟡 — words a person decides on.
**Complexity:** S — the read model's trigger, one sentence, one alert.
**Epic:** [EPIC-046](../README.md)
**SPEC:** [`SPEC-014`](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** EPIC-046A merged (#724, `8e5e27a`)

---

## 1. Context and problem
After 046A the rule, the editor field and the backtest were live, but a bot waiting on its trigger was described as "Waiting for the price to enter X–Y" (`contracts/grid_ladder_texts.py` → `waiting_text`, at `8e5e27a`) and the entry alert did not name the trigger. The file keeps its first name; the backtest part moved into 046A in review.

## 2. Acceptance criteria
- [x] The banner, `bot list`, `bot show` and the heartbeat say "Waiting for the price ≤ X within L–U (last price Y, N s ago)" (≥ for a SHORT) for a plan with a trigger; a plan without one keeps the range sentence.
- [x] The Discord entry alert names the trigger it met and its side; without a trigger it says nothing of one.
- [x] A `Docs/LEARNING/` page on the limit-order entry.

## 3. Design
ADR D5's last part. One sentence whichever side of the range the price is on: the range and the trigger together are the prices that open the gate, so "≤ T within L–U" is true below, inside and above the range. The read model carries the trigger as `TriggerMark` (the price and its better side) on `PricePosition`, so the text needs no domain call. The state badge keeps "Waiting for the range": it names the state, and the sentence beside it names what the state waits for.

## 3a. Reuse
- The sentence: used `waiting_text`, the one sentence the banner, `bot list`/`bot show` and the heartbeat already print.
- The read model: used `GridLadder.position` (`_position`), extended.
- The alert: used `BotRangeEnteredEvent` and `BotAlertSource.on_range_entered`, extended with defaulted fields.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/grid_ladder.py` | `TriggerMark`; `PricePosition.trigger` from the plan |
| `src/modules/bots/contracts/grid_ladder_texts.py` | `waiting_text` names the trigger |
| `src/modules/bots/contracts/events/bot_range_entered_event.py` | `trigger`, `trigger_at_or_below` |
| `src/modules/bots/application/kinds/grid/watch/grid_range_entry.py` | publishes them |
| `src/modules/alerting/application/sources/bot_alert_source.py` | the alert says them |

## 5. Testing
Unit: `test_grid_ladder_texts.py` (LONG, SHORT, no price heard, no trigger), `test_a_waiting_bot_is_listed_with_its_range_and_price.py` (through the real read model and `bot list`; red with the read model's trigger removed), `test_a_grid_that_enters_its_range_tells_it_once.py` (LONG and SHORT on the simulated venue), `test_a_bot_that_enters_its_range_is_told.py` (both sides, and none).

## 6. Docs touched
`Docs/SPEC/SPEC-014_run_a_grid_bot.md` (§3 step 5, §8), `Docs/MODULES/bots/05-building-blocks.md` (what shows a waiting Grid), `Docs/MODULES/alerting/05-building-blocks.md` (`on_range_entered`), `Docs/LEARNING/005_a_trigger_price_is_a_limit_order_on_the_entry.md` and its index row.

## Implementation notes (written when done)
- The new fields on the frozen `PricePosition` and on the event have defaults, so no other constructor changes.
- The decision record is marked Accepted: the owner said "ok" to D1–D6 after #724 merged.
