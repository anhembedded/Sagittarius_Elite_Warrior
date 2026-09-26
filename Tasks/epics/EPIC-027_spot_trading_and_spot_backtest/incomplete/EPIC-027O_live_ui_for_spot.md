# EPIC-027O — The Trading screen and the Dev Board show Spot as balances, with Buy and Sell only

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot"* ("I want to trade spot").
**Risk:** 🟢 — presentation over behavior the earlier tasks prove.
**Complexity:** M — two surfaces, a balances table, manual-order buttons, wiring the inert market combo.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027L](EPIC-027L_spot_user_data_stream.md), [EPIC-027N](EPIC-027N_live_strategy_on_spot.md)

---

## 1. Context and problem
- The positions table shows Side, Entry, Mark, Leverage and Liquidation
  (`src/modules/trading/ui/order_book/table_models.py:81-90`). None of these exist on Spot.
- The manual order card has LONG and SHORT buttons (`dashboard/dev_board_widgets/manual_order_card.py`).
  The strategy card has a leverage spinbox (`strategy_card.py:90-97`), and so does the Trading screen
  (`ui/trading/trading_view.py:496-502`).
- The Dev Board "Market: Spot/Futures" combo is inert
  (`dashboard/dev_board_widgets/system_controls_card.py:140-145`). `TC-GAP-01`
  (`tests/integration/presentation/ui/test_dev_board_known_gaps.py:104-116`) asserts that it does
  nothing.
- The Trading presenter's block message says "only Futures Testnet is supported" (`trading_presenter.py:149`).

## 2. Acceptance criteria
- [ ] On a Spot venue, a Holdings table (asset, free, locked, value in USDT) replaces the Positions
      table on both surfaces.
- [ ] The manual order card shows BUY and SELL. SELL is disabled when there is no holding to sell.
- [ ] Leverage controls are hidden on Spot.
- [ ] The Dev Board market combo is either wired (it selects the chart's market; the trading market
      comes from the venue) or removed. `TC-GAP-01` is updated to assert the new truth, not deleted.
- [ ] Every message that names the venue names the market too.

## 3. Design
- The market for trading comes from the venue (`EPIC-027G`). The chart's market is a separate choice
  for viewing. A mismatch is shown by the environment banner (venue-alignment state), not blocked.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/order_book/` | Holdings table model |
| `src/modules/trading/ui/dashboard/dev_board_widgets/manual_order_card.py`, `strategy_card.py`, `system_controls_card.py` | Spot variants and the market combo |
| `src/modules/trading/ui/trading/` | the same on the Trading screen |
| `tests/integration/presentation/ui/test_dev_board_known_gaps.py` | `TC-GAP-01` updated |
| `preview.py` of each package | Spot previews |

## 5. Testing
- Unit (ViewModels): visibility and enablement per market.
- Integration (real `qtbot` clicks): BUY on fake Spot; SELL disabled without a holding.
- Not run yet.
