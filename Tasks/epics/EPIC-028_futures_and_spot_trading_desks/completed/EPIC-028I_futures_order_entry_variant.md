# EPIC-028I — The Futures order entry sets margin mode and leverage, reduce-only, TIF and TP/SL, and shows liquidation, cost and max

**Status:** ✅ Done (2026-10-01)
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🔴 — TP/SL places extra reduce-only orders on a real exchange; a wrong side opens a position instead of protecting one
**Complexity:** L — variant UI + TP/SL order construction
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028F](../completed/EPIC-028F_commission_and_futures_account_controls.md), [EPIC-028H](../completed/EPIC-028H_order_entry_panel_core_and_spot.md), [EPIC-028O](../completed/EPIC-028O_order_contract_and_missing_reads.md) (stop-limit), [EPIC-028R](../completed/EPIC-028R_futures_conditional_orders_via_algo_api.md) (Futures conditional orders), ADR O2, O3

---

## 1. Context and problem
- `OrderType` already has `STOP_MARKET` / `TAKE_PROFIT_MARKET`; no UI uses them.

## 2. Acceptance criteria
- [x] Margin-mode chip (Cross/Isolated) and leverage chip dispatch `EPIC-028F`'s commands and show the exchange's answer.
- [x] Buttons read Buy/Long and Sell/Short; reduce-only checkbox and TIF (GTC/IOC/FOK) map to the order.
- [x] With TP/SL on, a filled entry is followed by `TAKE_PROFIT_MARKET` and `STOP_MARKET` reduce-only orders on the opposite side (test asserts side and `reduce_only`).
- [x] The Futures profile offers the Stop-limit tab that `EPIC-028O` adds to the submission path (ADR O3).
- [x] A market maximum accounts for the open loss against the book, or leaves that margin (`EPIC-028G` §3: not modelled there).
- [x] TP/SL has one owner with `EPIC-026K`, which builds the same protective orders. The TP and SL placed after an entry are exempt from `MAX_ORDERS_PER_SESSION` and `MIN_ORDER_INTERVAL` (`trading_limits.py`), or they hit the app's own limits (the PR #300 epic review).
- [x] Liquidation price, cost and max show from `EPIC-028G`, the liquidation value labelled estimate.

## 3. Design
- **The order path carries protection** (commit 1). `OrderRequest` and `ExecuteOrderCommand` gain a purpose (`OrderPurpose`). A protective order passes the trading limits and is not counted as a trade; the command refuses one that is not reduce-only. `protective_orders_for` (a domain policy, shared with `EPIC-026K`) builds the take-profit (`TAKE_PROFIT_MARKET`) and stop-loss (`STOP_MARKET`): opposite side, reduce-only, protective. Both go through the Algo Order API like the stop-limit. The preview judges a take-profit on its own side of the market and rounds every trigger away from it.
- **The Futures profile** (`DeskProfile`): Buy/Long and Sell/Short sized by `futures_side_figures`, Limit/Market/Stop-limit (ADR O3), TP/SL available, Positions held, `futures_controls` on.
- **Figures** (`futures_entry_rules.py`): the maximum is `EPIC-028G`'s, within the leverage's notional cap less the open position. A market order also pays its open loss against the book (`futures_market_max_quantity`), and waits when the book was not read. Reduce-only is sized by the position it reduces. Cost is Binance's; liquidation is the estimate for the position the order opens alone, labelled as one. TP/SL levels are checked against the order's price.
- **Options** (`OrderOptionsViewModel`, `OrderOptionsBar`): time in force on both desks; reduce-only (one box for both sides), margin mode and leverage on Futures. The chips show the exchange's last read and ask for a change; `FuturesSettingsChanger` sends `EPIC-028F`'s command through the new `IFuturesSettingsControl` port (`VenueTradingPorts.futures_settings`) and reads the symbol back.
- **TP/SL after the fill.** On the fake exchange a Futures market order is acknowledged `NEW`; the fill arrives later on the user-data stream. So the presenter announces an entry placed with TP/SL (`entryPlaced`). `ProtectiveOrderFollower` waits for that entry's `FILLED` on its venue's `OrderFeed`, then places both orders and says what happened.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `contracts/order_purpose.py`, `protective_levels.py`, `order_request.py`, `trading_limits.py`, `order_type.py` | purpose, levels, `TRIGGERED_ORDER_TYPES` |
| `domain/policies/protective_orders.py`, `trading_limit_policy.py`, `stop_trigger_side.py` | TP/SL orders, limit exemption, take-profit trigger side |
| `application/orders/execute_order/*`, `preview_order/*`, `order_submission_service.py` | purpose carried; triggered types previewed |
| `adapters/binance/futures_algo_order_mapper.py`, `futures_order_payload_mapper.py` | `STOP_MARKET` / `TAKE_PROFIT_MARKET` sent |
| `contracts/i_futures_settings_control.py`, `application/account_control/futures_settings_service.py`, `contracts/venue_trading_ports.py`, the registry and the fake | the chips' port |
| `contracts/futures_order_estimates.py` | `book_open_loss`, `futures_market_max_quantity` |
| `ui/desk/desk_profile.py` | the Futures profile |
| `ui/desk/order_entry/` | `futures_entry_context.py`, `futures_entry_rules.py`, `futures_context_reader.py`, `order_options_view_model.py`, `order_options_bar.py`, `protection_fields.py`, `futures_settings_changer.py`, `protective_order_follower.py`, `order_outcome_text.py` (moved out of the presenter); the presenter, view model, side form, panel and preview |

## 5. Testing
- Unit: `test_protective_orders.py`, `test_stop_trigger_side.py` (take-profit), `test_execute_protective_order.py`, `test_order_submission_service.py` (purpose), `test_futures_algo_order_mapper.py`, `test_futures_order_estimates.py` (book open loss), `test_futures_settings_service.py`, `test_futures_settings_control_fake.py`, `test_desk_profile.py`, `test_futures_entry_rules.py`, `test_order_options_view_model.py`, `test_futures_order_panel.py`, `test_futures_order_entry_panel.py` (qtbot, real clicks), `test_protective_order_follower.py`.
- Integration: `test_protective_orders_against_fake_server.py` (an entry and both protective orders past a one-order session). `test_futures_order_panel_against_fake_server.py`: the leverage chip changes the fake's leverage and reads it back; a market long with TP/SL is protected once its fill is published.
- Mutation-checked: the limit exemption, the session count, the reduce-only refusal, the take-profit side, the protective side and reduce-only, the purpose carried, the book's open loss, the reducible side, the book side, the margin used for liquidation, the reduce-only box, the time in force on a market order, no protection for a reduce-only entry, protection only on `FILLED`, the TP/SL box, the message kept on re-read, the re-read after a chip, Futures reads only on a Futures desk, the headroom. Each mutation turned a test red.

## Implementation notes (written when done)
- **All four limits pass a protective order, not two.** The task named the session cap and the interval. The position count (1 by default) refuses a take-profit on a symbol that already has a position too, and a take-profit's notional can exceed the entry's. The exemption is safe only because a protective order must be reduce-only, and `ExecuteOrderCommand` enforces that.
- **Two columns, not one form.** The Futures desk reuses the Spot layout with Buy/Long and Sell/Short. Binance's single form with two buttons is one `SideLayout` member, left to `EPIC-028K` if the desk wants it.
- **TP/SL waits for the venue's fill.** A partly filled entry that is then cancelled is not protected, and the desk says so. The two protective orders are not linked: when one triggers, the other stays until the reduce-only refusal (or a cancel) removes it.
- **An order that closes a position is not protected.** When the order sent is reduce-only (the box, or a Sell/Short against a long), there is no new position, so no TP/SL is announced. The box also keeps an order reduce-only when the position went away between the figures and the submit, so the exchange refuses it rather than opening the other way.
- **The liquidation estimate is for the order's position alone** (cross reads optimistic; see `liquidation_estimate.py`). It shows "—" when no price liquidates it.
- **Fixed on the way:** a re-read after an order or a leverage change cleared the panel's message ("Order placed …"), because `set_context` always cleared it. Now only a new symbol's "Loading" line is cleared.
- **Not wired into a screen yet.** `EPIC-028K` builds the Futures desk: the panel, the follower connected to `entryPlaced`, the account tabs and summary.
- **No live check.** The algo shapes for `STOP_MARKET`/`TAKE_PROFIT_MARKET` follow Binance's docs and `python-binance` 1.0.37; `EPIC-028N` confirms them on the Testnet.
