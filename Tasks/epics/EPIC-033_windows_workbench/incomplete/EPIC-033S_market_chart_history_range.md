# EPIC-033S — The Market mode's charts scroll back and load a chosen range

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-05, deciding where the Dev Board's "load more" and date-range Load history go when the Dev Board is deleted (EPIC-033P): "Đưa vào Market mode sau" (put them in the Market mode later)
**Risk:** 🟡 — older candles prepended to a live chart; a gap at the join is the trap
**Complexity:** M — a command, a dialog and a prepend path in the chart
**Epic (optional):** [EPIC-033](../README.md)
**Depends on:** EPIC-033H (merged)

---

## 1. Context and problem
The Market mode's chart loads a fixed window of recent candles. Only the Dev Board loads older candles on demand ("load more") or a chosen date range; EPIC-033P deletes it without keeping either.

## 2. Acceptance criteria
- [ ] Chart → Load older candles prepends the previous window to the active chart, without a gap or a duplicate at the join.
- [ ] Chart → Load range… asks a UTC start and end (a `QDialogButtonBox` dialog) and shows exactly that range.
- [ ] Both are disabled while a load runs, and a load is fenced (`async-ui-action-rule.md`): closing the chart drops its result.

## 3. Design
Commands on the Market mode's chart, reusing the store's history query; the range dialog mirrors the Data mode's Sync history… range fields.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/market/` | the two commands, the dialog, the prepend path |

## 5. Testing
Unit: the join has neither gap nor duplicate (boundary values at the window edge); a fenced load dropped on close. Integration: Load range… against a seeded store.
