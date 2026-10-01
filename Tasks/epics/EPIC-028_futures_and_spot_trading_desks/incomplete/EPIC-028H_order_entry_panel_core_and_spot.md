# EPIC-028H — One order-entry panel places Limit, Market and Stop-limit orders; the Spot variant shows Buy and Sell side by side

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — the panel replaces the Dev Board card later; its dispatch must stay the one `ExecuteOrderCommand` path
**Complexity:** L — new shared UI package, view model, Spot variant, preview
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028G](../completed/EPIC-028G_order_estimate_policies.md)

---

## 1. Context and problem
- `dev_board_widgets/manual_order_card.py` (170 lines): Market/Limit combo, quantity, price, two
  buttons; no total, slider, TP/SL or estimates. HLD 11 §11.3 plans panels under `trading/ui/panels/`.

## 2. Acceptance criteria
- [ ] A `DeskProfile` (market type, side labels, which controls exist) selects the variant; no widget branches on `is_spot`.
- [ ] Core panel: tabs Limit / Market / Stop-limit, price with BBO fill, quantity, 0–100 % slider bound to max quantity, total in quote, TP/SL toggle, estimated fee.
- [ ] Spot variant: two columns Buy / Sell, each with available, max buy / max sell; Sell disabled without a holding (EPIC-027O rule kept).
- [ ] Submitting dispatches the existing path with the panel's venue; quantity and price are rounded to the symbol's filters before dispatch; a money-moving submit confirms in a dialog (HLD 11 §11.5).
- [ ] `preview.py` renders both variants.

## 3. Design
MVP per `ui-presentation-rule.md` §3: `order_entry_panel.py` (view), `order_entry_view_model.py`, `order_entry_presenter.py`; variants are small `QWidget` subclasses composed into the core. QtWidgets only, no stylesheet, no fixed pixel sizes.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/order_entry/` | new package (core + Spot variant + preview) |
| `src/modules/trading/ui/desk/desk_profile.py` | new |

## 5. Testing
qtbot unit tests per control; integration: Spot Buy through the fake exchange moves the holding.
- Not run.

## Implementation notes (written when done)
Not started.
