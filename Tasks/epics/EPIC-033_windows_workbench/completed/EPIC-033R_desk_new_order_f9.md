# EPIC-033R — Each trading desk has Trade → New order… (F9)

**Status:** ✅ Done (2026-10-05)
**Source:** the user, 2026-10-05, deciding where the Dev Board's F9 goes when the Dev Board is deleted (EPIC-033P): "F9 cho desk" (F9 for the desks)
**Risk:** 🟢 — a shortcut that moves the focus; a clash with another F9 is refused by the Engine
**Complexity:** S — one command per desk
**Epic (optional):** [EPIC-033](../README.md)
**Depends on:** EPIC-033D (merged); folds into EPIC-033I when the desks become the Trade mode

---

## 1. Context and problem
Only the Dev Board binds F9 to "new order". HLD §11.2.3 lists Trade → New order… (F9) for the Trade mode; the Spot and Futures desks have no such command today, so the order entry is reachable by mouse only.

## 2. Acceptance criteria
- [x] Trade → New order… (F9) exists in the Spot desk and the Futures desk, contributed by the trading module, enabled while the desk can place an order.
- [x] Triggering it moves the keyboard focus to the desk's order entry (its first field), and places nothing.

## 3. Design
A `CommandContribution` per desk mode with `shortcut="F9"`; the handler asks the view to focus its order entry. The order itself is still placed by the order entry's own command, with its confirmation.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `desk_screen/desk_commands.py` | `new_order_id(venue)` and the third contribution: `&New order…`, F9, on the toolbar, `needs_input` |
| `desk_screen/desk_presenter.py` | binds it to `OrderEntryViewModel.request_focus`, enabled from `can_take_order` through a `DerivedState` on `changed` |
| `desk_screen/disabled_desk_presenter.py` | binds it disabled for the run, with the other two |
| `order_entry/order_entry_view_model.py` | `can_take_order` (terms read, no order in flight), `focusRequested`, `request_focus()` |
| `order_entry/order_side_form.py` | `first_field()`: the first shown, enabled field top to bottom (stop, price, amount, total); the fields' enabled state now reads `can_take_order` |
| `order_entry/two_column_sides.py`, `order_entry_panel.py` | the layout's first field is the Buy form's; the panel focuses it and selects its text |

## 5. Testing
Unit: triggering the action focuses the order entry's first field and emits no order request; it is disabled while the desk cannot trade.

## 6. Implementation notes
- **"Can trade" is the order entry's own state**, the one its fields are enabled by: the symbol's terms are read and no order is in flight. The command and the fields read the same property (`OrderEntryViewModel.can_take_order`), so F9 is never enabled where the field it focuses is not. Whether trading is *enabled* does not gate it: a manual order does not need the session toggle. A desk whose venue is off binds it disabled for the run (`DisabledDeskPresenter`).
- **The first field follows the order type**, because the fields shown change with it: a stop-limit starts at the stop, a limit at the price, a market order at the amount (or the total, on a side sized by quote).
- **The focus is a request, not a reach into the view**: the presenter asks the view model, the panel answers. The presenter holds no widget.
- **F9 is free in both desk modes.** The Engine refuses a duplicate key within a mode or against a mode-less command (`action_registry.py`); the only other F9 is the Dev Board's, in its own mode, and no command without a mode takes it.
- The HLD table marks Trade → New order… as on the Trade toolbar, so it is (`on_toolbar=True`).

## 7. Verification
- `tests/unit/modules/trading/ui/desk/test_desk_new_order.py`: contribution per mode with F9; focus lands on the first field on both desks and nothing is previewed or submitted; the first field follows Limit / Market / Stop-limit; disabled while busy and while a symbol's terms load; disabled for the run on a venue that is off. Each mutation turned the file red: no focus wiring (4), `can_take_order` always true (2), the disabled desk not binding it (1), price before stop (2), hidden fields not skipped (4), no shortcut (3).
- Commit tier: `ci-local.ps1 -SkipTests` PASS with a clean log; `tests/unit/architecture` green; all of `tests/unit` (8522), `tests/integration` (307) and `tests/sanity` (33) green locally.
