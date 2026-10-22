# EPIC-046B — Every place that shows a waiting Grid names its trigger, and its chart draws it

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
- [x] The owner's addition (2026-10-22, with a screenshot of an ETHUSDT plan): the chart draws a trigger line, distinct in style, tagged "Trigger ≤ T" (≥ for a Short), redrawn as the field is edited, also on the Backtest chart (both draw `IBotKind.overlay`), and left out once the bot has laid its ladder.
- [x] The owner's question: the Loss-at-stop and Result-at-TP rows of a triggered plan start from the trigger.

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
| `src/modules/bots/domain/bot_overlay.py`, `domain/grid/grid_overlay.py` | `OverlayRole.TRIGGER` and its line |
| `src/modules/bots/ui/chart/overlay_items.py`, `src/support/charting/chart_card/theme.py`, `price_level_layer.py` | its style: dash-dot (`LineStyle.DASH_DOT`), `TRIGGER_COLOR` |
| `src/modules/bots/ui/bots_screen/plan_trigger_line.py`, `bot_detail.py` | the line is left out once the bot latched |

## 5. Testing
Unit: `test_grid_ladder_texts.py` (LONG, SHORT, no price heard, no trigger), `test_a_waiting_bot_is_listed_with_its_range_and_price.py` (through the real read model and `bot list`; red with the read model's trigger removed), `test_a_grid_that_enters_its_range_tells_it_once.py` (LONG and SHORT on the simulated venue), `test_a_bot_that_enters_its_range_is_told.py` (both sides, and none).

Chart: `test_grid_overlay.py` (LONG ≤, SHORT ≥, none), `test_the_trigger_line_is_drawn_until_the_ladder_is_laid.py` (every state, RECOVERING by the state it returns to, a halted bot by what its record holds), `test_the_trigger_line_has_its_own_style.py` (its colour and dash are no other line's), `test_the_plan_of_a_triggered_grid.py` (the real `detail_for`: drawn for a draft, left out for a running bot, red without the wiring; the exit rows start from the trigger).

## 6. Docs touched
`Docs/SPEC/SPEC-014_run_a_grid_bot.md` (§3 step 5, §8), `Docs/MODULES/bots/05-building-blocks.md` (what shows a waiting Grid), `Docs/MODULES/alerting/05-building-blocks.md` (`on_range_entered`), `Docs/LEARNING/005_a_trigger_price_is_a_limit_order_on_the_entry.md` and its index row.

## Implementation notes (written when done)
- The new fields on the frozen `PricePosition` and on the event have defaults, so no other constructor changes.
- **The owner's Loss-at-stop question.** The rows already start from the trigger: `exit_estimates_for` plans through `entry_plan`, which plans at `entry_price` since #724. Replaying the screenshot's plan (2306.26–2784.15, geometric, SL 3 %, TP 2887, trigger 2329): of the grid counts 6 to 15, only an 11-grid plan planned at the trigger gives "filling 1 BUY" and "filling 10 SELL". From 2329 down to the stop at 2237.07 only L0 (2306.26) fills, and every level above 2329 sells on the way to 2887. The figures are right.
- Review of #725: a halted bot, one awaiting recovery or one in error is resumed over what it holds and never asks the trigger, so the line goes while its record holds inventory or a position (`RESUMED_BY_WHAT_IT_HOLDS`); resting orders alone do not count, as the Resume cancels them and then asks the trigger.
- The decision record is marked Accepted: the owner said "ok" to D1–D6 after #724 merged.
