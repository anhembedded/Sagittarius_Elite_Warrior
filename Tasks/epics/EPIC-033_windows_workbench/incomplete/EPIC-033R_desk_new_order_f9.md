# EPIC-033R — Each trading desk has Trade → New order… (F9)

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-05, deciding where the Dev Board's F9 goes when the Dev Board is deleted (EPIC-033P): "F9 cho desk" (F9 for the desks)
**Risk:** 🟢 — a shortcut that moves the focus; a clash with another F9 is refused by the Engine
**Complexity:** S — one command per desk
**Epic (optional):** [EPIC-033](../README.md)
**Depends on:** EPIC-033D (merged); folds into EPIC-033I when the desks become the Trade mode

---

## 1. Context and problem
Only the Dev Board binds F9 to "new order". HLD §11.2.3 lists Trade → New order… (F9) for the Trade mode; the Spot and Futures desks have no such command today, so the order entry is reachable by mouse only.

## 2. Acceptance criteria
- [ ] Trade → New order… (F9) exists in the Spot desk and the Futures desk, contributed by the trading module, enabled while the desk can place an order.
- [ ] Triggering it moves the keyboard focus to the desk's order entry (its first field), and places nothing.

## 3. Design
A `CommandContribution` per desk mode with `shortcut="F9"`; the handler asks the view to focus its order entry. The order itself is still placed by the order entry's own command, with its confirmation.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/*_desk*` commands and bindings | the command and its focus handler |

## 5. Testing
Unit: triggering the action focuses the order entry's first field and emits no order request; it is disabled while the desk cannot trade.
