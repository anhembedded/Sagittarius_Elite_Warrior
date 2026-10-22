# EPIC-046B — Every place that shows a waiting Grid names its trigger

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-22 (see the [epic](../README.md)).
**Risk:** 🟡 — words a person decides on, and a backtest that must match live.
**Complexity:** S — the read model's trigger, three texts, one alert.
**Epic:** [EPIC-046](../README.md)
**SPEC:** [`SPEC-014`](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** EPIC-046A merged

---

## 1. Context and problem
After 046A the rule, the editor field and the backtest are live, but a bot waiting on its trigger is described as "Waiting for the price to enter X–Y" (`grid_ladder_texts.py` → `waiting_text`) and the entry alert does not name the trigger. The hand-off list is in [046A](../completed/EPIC-046A_the_trigger_gates_the_entry.md#hand-off-to-epic-046b).

## 2. Acceptance criteria
- [ ] The banner, `bot list` and `bot show` say "Waiting for the price ≤ X (now Y)" (≥ for a SHORT) while the range is met and the trigger is not.
- [ ] The Discord entry alert names the trigger it met.
- [ ] A `Docs/LEARNING/` page on the limit-order entry.

## 3. Design
ADR D5's last part.

## 3a. Reuse
To be filled in when started: `waiting_text`, `BotRangeEnteredEvent`, `entry_gate`.

## 4. Changes, per file
To be filled in when started.

## 5. Testing
To be filled in when started.

## 6. Docs touched
To be filled in when started.
