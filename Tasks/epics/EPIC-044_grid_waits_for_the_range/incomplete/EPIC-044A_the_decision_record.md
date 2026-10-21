# EPIC-044A — The decision for "a Grid waits for the range" is written, read by a reviewer and accepted

**Status:** 🟡 In progress
**Source:** the owner, 2026-10-21, through the coordinating session (quoted once in the epic README: *"trường hợp giá out range, thì bot vẫn start, nhưng chờ giá vào trong range thì bot mới bắt đầu init lệnh"* — if the price is out of the range the bot still starts but only begins laying orders once the price is inside).
**Risk:** 🟢 — documents only; the decision it records is a real-money behaviour, which is why a reviewer reads it before code.
**Complexity:** M — the rule touches the lifecycle, the start, the checks, six surfaces and the replay.
**Epic (optional):** [EPIC-044](../README.md)
**SPEC (optional):** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None

---

## 1. Context and problem
At `849d973` the Grid's answer to "started with the price outside the range" depends on the side and ignores the direction: a SHORT above the range plans a 0.1542 BTC market short before any order while `PRICE_ABOVE_RANGE` tells the owner it "places BUY orders only" (`grid_range_checks.py` → `check_price_against_range`, reading `plan.opening_buy_quantity`). The owner decided one rule instead (the ADR's D1).

## 2. Acceptance criteria
- [x] The ADR states the rule, the facts it rests on (with the probe), the state and its rows, the entry rule, the checks, the surfaces, the replay, the alternatives and the open questions.
- [ ] A reviewer other than the author has read it and said so on the pull request.
- [ ] The coordinator has accepted D2–D12 or the owner has vetoed some, and O1–O3 are answered.

## 3. Design
See [the ADR](../DECISION_2026-10-21_a_grid_waits_for_the_range.md). The new state follows `AWAITING_RECOVERY` (`EPIC-042`): one table, one state, derived sets.

## 3a. Reuse
None: no UI or application need; documents only.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Tasks/epics/EPIC-044_grid_waits_for_the_range/` | the epic, its tracking, four tasks and the ADR |
| `Tasks/epics/README.md`, `Tasks/ROADMAP.md` | the epic's row and link |
| `Docs/LEARNING/` | page 004, the teaching page for the decision |

## 5. Testing
Documentation only: `python3 scripts/check_skill_prompt_references.py`, the board guard (`tests/unit/test_task_board_is_consistent.py`) and the document guards.

## 6. Docs touched
`Docs/LEARNING/004_…`; the ADR. `SPEC-014`, `Docs/MODULES/bots/state-machines.md` and the vocabulary change with the code in 044B, not here (they would describe code that does not exist).
