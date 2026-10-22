# EPIC-046B — Every place that shows a waiting Grid names its trigger, and the backtest enters by it

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-22 (see the [epic](../README.md)).
**Risk:** 🟡 — words a person decides on, and a backtest that must match live.
**Complexity:** M — an editor field, three texts, one alert, the replay's gate.
**Epic:** [EPIC-046](../README.md)
**SPEC:** [`SPEC-014`](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** EPIC-046A merged

---

## 1. Context and problem
After 046A the rule is live, but the Plan editor has no field for it, a bot waiting on its trigger is described as "Waiting for the price to enter X–Y" (`grid_ladder_texts.py` → `waiting_text`), the entry alert does not name the trigger, and `WaitingReplay` enters on the range alone.

## 2. Acceptance criteria
- [ ] The Plan editor has an optional trigger field, empty = off, with the validation's words on the field.
- [ ] The banner, `bot list` and `bot show` say "Waiting for the price ≤ X (now Y)" (≥ for a SHORT) while the range is met and the trigger is not.
- [ ] The Discord entry alert names the trigger it met.
- [ ] The replay enters at the first step whose close opens `entry_gate`; a test replays one path through the replay and the live rule and asserts the same entry step.
- [ ] A `Docs/LEARNING/` page on the limit-order entry.

## 3. Design
ADR D5's second half.

## 3a. Reuse
To be filled in when started: `waiting_text`, `GridPanel`, `BotRangeEnteredEvent`, `WaitingReplay`.

## 4. Changes, per file
To be filled in when started.

## 5. Testing
To be filled in when started.

## 6. Docs touched
To be filled in when started.
