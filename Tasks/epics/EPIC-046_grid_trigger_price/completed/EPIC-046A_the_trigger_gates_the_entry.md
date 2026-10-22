# EPIC-046A — A Grid's trigger price gates its live entry like a limit order

**Status:** ✅ Done (2026-10-22)
**Source:** the owner, 2026-10-22: *"tui muốn kích hoạt giống limit, giá tốt hơn giá đó mới kích hoạt grid"* ("I want it to activate like a limit order: the grid activates only when the price is better than that price").
**Risk:** 🔴 — decides when a position opens with real money.
**Complexity:** M — one domain gate, three callers, the Start check and the entry price.
**Epic:** [EPIC-046](../README.md)
**SPEC:** [`SPEC-014`](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None

---

## 1. Context and problem
`EPIC-044` built the wait for the range; nothing can hold a bot back inside it. The decision record's §1 cites the three places the entry is gated today.

## 2. Acceptance criteria
- [x] LONG (Spot and Futures) and SHORT (Futures) started inside the range but short of the trigger place nothing and wait in `AWAITING_RANGE`.
- [x] A price at the trigger or better lays exactly what a normal start at that price would; a price still short of it does not.
- [x] The range is judged first: a price outside it never enters.
- [x] A trigger already met at Start activates at once.
- [x] Once laid, a price back across the trigger leaves the bot running; a restart of a running bot returns it to `RUNNING`; a restart of a waiting one keeps waiting for the trigger.
- [x] A Resume of a bot that holds nothing waits for the trigger.
- [x] A trigger outside the range, a NEUTRAL trigger and an unreadable value are refused in words; `bot edit` judges a changed range, direction or trigger against the others; the definition round-trips and `off` clears it.
- [x] The Start check says `TRIGGER_NOT_MET` (information) and the Plan judges the ladder at the trigger.

## 3. Design
ADR D1–D4, D6 and the first half of D5. One gate, `grid_entry_gate.py` → `entry_gate`, replaces the three `range_position` asks; no lifecycle change.

## 3a. Reuse
- The wait, its rows, the fresh-book confirmation and the pre-checks: used `GridRangeEntry` (`EPIC-044B`).
- The flat Resume: used `GridResumeSequence._wait_if_still_flat`.
- The entry price: used `entry_plan` (ADR 044 D6), now through `entry_price`.
- The host verbs and the plan file: used the parameter map (`GRID_PARAMETER_KEYS`), no code of their own.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_entry_gate.py` | New: `EntryGate`, `entry_gate`, `trigger_met`, `entry_price` |
| `src/modules/bots/domain/grid/grid_params.py` | `trigger_price`, its validation and its key |
| `src/modules/bots/domain/grid/grid_parameter_check.py` | The key; judged with the range and the direction |
| `src/modules/bots/domain/grid/grid_range_checks.py` | `TRIGGER_NOT_MET` |
| `src/modules/bots/domain/grid/grid_evaluation.py` | `entry_plan` at `entry_price` |
| `src/modules/bots/application/kinds/grid/watch/grid_range_entry.py` | The gate in the start, the watch and the confirmation; the log cause |
| `src/modules/bots/application/kinds/grid/recovery/grid_resume_sequence.py` | The gate in the flat Resume |

## 5. Testing
Unit: `test_grid_entry_gate.py` (the rule's boundaries, the entry price, the validation, the round trip, `bot edit`), `test_grid_range_checks.py` (the verdict), `test_a_grid_with_a_trigger_waits_for_a_better_price.py` (the real executor over the simulated venue: the wait, the entry, the parity with a normal start, the latch, both restarts, the flat Resume, the saved key), `test_grid_parameter_check.py`. Mutation: each comparison, the side, the gate and the flat Resume's gate, each red.

## 6. Docs touched
`Docs/MODULES/bots/state-machines.md` (`AWAITING_RANGE` with a trigger), `Docs/SPEC/SPEC-014_run_a_grid_bot.md` (§3 step 5 and §8), `Docs/OPERATIONS/headless_runbook.md` (`bot edit`'s keys, the plan file).

## Implementation notes (written when done)
- The latch needs no stored flag: only `AWAITING_RANGE` asks the gate, so the lifecycle is the latch (ADR D3).
- `bot edit` could not clear a trigger with an empty value (a value is 1 to 64 characters), so `off` clears it, as it does a stop loss.
- The whole unit tier ran green apart from two environment items fixed in place (the log template catalogue regenerated, `pwsh` installed).
