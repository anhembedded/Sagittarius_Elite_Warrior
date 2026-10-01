# EPIC-028O — The order path carries every order the desks offer, and the panels can read every figure they show

**Status:** 🟡 In progress (2026-10-01) — PR-1 of 3
**Source:**
- ADR O3: the user, 2026-09-29, stop-limit on both desks (`STOP_LOSS_LIMIT` on Spot, `STOP` on Futures).
- Split out of [EPIC-028H](../completed/EPIC-028H_order_entry_panel_core_and_spot.md) on 2026-09-30.
- Widened on 2026-10-01 after the epic-level review on PR #300 (§1, "Plan 028H–N — missing inputs"); the user agreed: *"đồng ý, làm theo đề xuất của bạn"* ("agreed, do as you propose").
- See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).

**Risk:** 🔴 — new order shapes on a real exchange; a wrong trigger direction fills at once instead of waiting
**Complexity:** L — the order model end to end, two payload mappers, the fake exchange, four reads
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028H](../completed/EPIC-028H_order_entry_panel_core_and_spot.md)

---

## 1. Context and problem
The epic-level review found that 028H–N cannot be executed as written, because the order path and the reads lack inputs the panels need:
- **The order path.** `PreviewOrderQuery` has no stop price, no time-in-force choice and no quote quantity (`application/orders/preview_order/query.py`). The handler hard-codes GTC and sets a price only for LIMIT. `Order.stop_price` and the Futures mapper support stops, but nothing upstream fills them.
- **Order types.** `OrderType` has no stop-limit member. The Spot mapper accepts MARKET and LIMIT only.
- **Leverage.** Nothing reads the current leverage or the brackets (`symbolConfig`, `leverageBracket`). `LeverageSetting.max_notional` exists only in the answer to a change, so `futures_max_quantity`'s leverage and headroom, and the liquidation estimate's MMR and `cum`, have no source.
- **Prices.** There is no mark price for a flat symbol (`LivePosition.mark_price` only), and nothing reads `bookTicker`. So `FuturesOrderTerms` cannot be filled, and the market-order open loss (`EPIC-028G` §3) cannot be modelled.
- **The app's own limit.** No maximum knows the app's `max_notional_per_order` (`trading_limits.py`), so a 100 % slider can be refused by the app's own gate.

## 2. Acceptance criteria
- [x] `OrderRequest` and `PreviewOrderQuery` carry an optional stop price, a time-in-force and an optional quote quantity. Preview rounds the stop price to the tick, and the handler no longer hard-codes GTC. *(PR-1)*
- [x] `OrderType` gains stop-limit. The Spot mapper sends `STOP_LOSS_LIMIT` with `stopPrice`, and `quoteOrderQty` for a market buy sized by quote. *(PR-1)* *Deviation:* the Futures mapper does **not** send `STOP`. `python-binance` 1.0.37 routes every USD-M conditional order to Binance's Algo Order API, where the client order id is lost and Emergency Stop does not reach, so the mapper refuses all conditional types. Sending them is moved to [EPIC-028R](EPIC-028R_futures_conditional_orders_via_algo_api.md).
- [x] A stop price on the wrong side of the last price for its direction is refused before it is sent, with the reason named. It is never sent to trigger at once. *(PR-1)*
- [x] The fake exchange accepts both stop orders and fills them when triggered by price, and accepts a quote-quantity market buy. An integration test places each on its venue. *(PR-1, Spot; the Futures side moves to 028R with the algo routes.)*
- [ ] Reads on `IOrderEntryTerms`, each a venue-addressed query:
  - the symbol's current leverage and margin type (`symbolConfig`);
  - its brackets (`leverageBracket`);
  - the mark price (`premiumIndex`);
  - the best bid and ask (`bookTicker`);
  - the app's per-order notional limit.

  Spot answers the leverage, bracket and mark reads with "not applicable", never an invented value.
- [ ] Both desk profiles offer the Stop-limit tab with a stop-price field. The Spot market buy sizes by quote amount. The price button can fill the best bid or ask.
- [ ] Every maximum also respects the app's per-order notional limit.
- [ ] Moved from [EPIC-028Q](../completed/EPIC-028Q_phase_2_reader_fixes.md): the fake Futures exchange fills a market order and returns it from `userTrades`, so a Futures fill, its trade history and its average entry price are exercised end to end. Existing tests that rely on the fake never filling are updated in the same change.
- [ ] Moved from EPIC-028Q: the Futures account reader reads Multi-Assets mode (`GET /fapi/v1/multiAssetsMargin`), and the desk's available balance names the margin it counts when the mode is on.

## 3. Design
**Three pull requests**, each reviewed on its own, because each changes a different layer and each is useful alone:
1. **PR-1, the order contract** (acceptance criteria 1–4).
2. **PR-2, the reads** (criteria 5, 8 and 9).
3. **PR-3, the desk UI** (criteria 6 and 7).

### PR-1 — the order contract (built)
- **One new order type.** `OrderType.STOP_LIMIT` means "rest a limit order once the stop price trades". Binance spells it differently per venue:
  - Futures `STOP` takes `price`, `stopPrice` and `timeInForce`;
  - Spot `STOP_LOSS_LIMIT` takes the same three fields.

  So each mapper owns its own wire name, instead of sending `OrderType.name`. Each payload parser maps its venue's spelling back to `STOP_LIMIT`.
- **Order fields.** `Order` gains `quote_quantity`, the quote amount a Spot market buy spends (`quoteOrderQty`). When it is set, the Spot mapper sends `quoteOrderQty` instead of `quantity`, and `quantity` holds the preview's estimate. Futures refuses it, since it has no such parameter.
- **What the caller can say.** `OrderRequest` and `PreviewOrderQuery` gain four optional fields:
  - `stop_price`;
  - `time_in_force`, default GTC, which replaces the hard-coded GTC;
  - `quote_quantity`;
  - `last_price`, the market price the stop is judged against.

  `PreviewOrderQuery` refuses an inconsistent combination at construction: a stop-limit without a stop price or a last price, a stop price on another order type, or a quote quantity on anything but a market buy.
- **Rounding.** Preview rounds the stop price to the tick *away from the market*: up for a buy stop, down for a sell stop. A stop never rounds onto the wrong side.
- **The trigger-side rule is a domain policy** (`stop_trigger_side.py`). A buy stop must be above the last price and a sell stop below it, on both venues. Otherwise the exchange either rejects the order (Spot `-2010 would trigger immediately`) or fills it at once.
  - Preview records the verdict as `OrderPreview.stop_check`.
  - `ExecuteOrderCommandHandler` refuses with `ExecuteOrderStopRejection.STOP_ON_WRONG_SIDE` before any request is sent. This is the `MIN_NOTIONAL` pattern (`BUG-090`).
- **A type the venue cannot send is refused by name** (the PR #302 review, should-fix 1). `ITradingClientFactory.accepted_order_types()` answers with the venue's payload mapper's own set (`FUTURES_SENDABLE_ORDER_TYPES`, `SPOT_SENDABLE_ORDER_TYPES`). `ExecuteOrderCommandHandler` refuses anything outside it with `ExecuteOrderTypeRejection.NOT_SENDABLE_ON_VENUE`, before any request and on the dry run too, after the stop-side check. Before this, a Futures stop-limit dry run answered clean and the live path raised from inside `place_order`, against `IOrderSubmission`'s "a refusal is a named value" promise. A test keeps each factory's set equal to what its mapper sends, for every `OrderType`.
- **Futures conditional orders are refused (found while building).** `python-binance` 1.0.37's `futures_create_order` sends every conditional type to `POST /fapi/v1/algoOrder` (Binance's change of 2025-12-09). It replaces `newClientOrderId` with a random `clientAlgoId`, and the order then lives outside `openOrders` and outside `allOpenOrders`, so Emergency Stop does not reach it. The Futures mapper now refuses `STOP_MARKET`, `TAKE_PROFIT_MARKET` and `STOP_LIMIT` with that reason. None was reachable before: nothing upstream set a stop price. Doing it properly is [EPIC-028R](EPIC-028R_futures_conditional_orders_via_algo_api.md).
- **Fake exchange.**
  - Spot accepts a stop-limit and keeps it as `NEW`.
  - A test sets a symbol's last price through the fake's state. A stop the new price crosses becomes a resting limit order, and Spot fills it at the limit as its matching rule does.
  - Spot accepts `quoteOrderQty` on a market buy and fills `quote ÷ price` truncated to 8 decimals (the fake does not apply `LOT_SIZE`).

## 4. Changes, per file (PR-1)
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/order_type.py` · `order.py` | `STOP_LIMIT`; `Order.quote_quantity` |
| `src/modules/trading/contracts/order_request.py` · `application/orders/preview_order/query.py` | `stop_price`, `time_in_force`, `quote_quantity`, `last_price`; construction checks |
| `src/modules/trading/contracts/stop_price_check.py` · `domain/policies/stop_trigger_side.py` | new |
| `src/modules/trading/contracts/order_preview.py` · `execute_order_result.py` | `stop_check`; `ExecuteOrderStopRejection` |
| `src/modules/trading/application/orders/preview_order/handler.py` | stop rounding away from the market, TIF, quote sizing |
| `src/modules/trading/application/orders/execute_order/handler.py` | refuses a crossed stop before sending |
| `src/modules/trading/application/orders/order_submission_service.py` | hands the new fields on |
| `src/modules/trading/adapters/binance/spot/spot_order_payload_mapper.py` · `spot_user_data_event_parser.py` | `STOP_LOSS_LIMIT`, `quoteOrderQty`, stop price read back |
| `src/modules/trading/adapters/binance/futures_order_payload_mapper.py` · `user_data_event_parser.py` · `order_enum_parsing.py` | conditional types refused; `STOP` read as `STOP_LIMIT` |
| `src/modules/trading/ui/execute_order_block_reason.py` · `strategy/cli/trade_once_formatter.py` | the refusal in words |
| `tests/sanity/fake_exchange/` | Spot stop-limit trigger and fill, quote-sized market buy, `set_last_price` |

## 5. Testing (PR-1)
- **Units.**
  - The trigger-side rule at, one tick below and one tick above the last price, per side.
  - Preview: stop rounding per side, `stop_check`, TIF default and override, quote sizing, and every refused combination.
  - Execute: a stop below or at the last price is refused with nothing sent; one tick above passes the gate.
  - Mappers and parsers, both venues; the service hand-off; both refusal texts.
- **Integration** (`test_stop_and_quote_orders_against_fake_server.py`, real handler, clients and `python-binance`):
  - a Spot buy stop rests, ignores a price one cent short, then fills at its limit when the price reaches the stop;
  - a crossed Spot stop sends no `POST /api/v3/order`;
  - a 1 000 USDT market buy fills 0.02 BTC at 50 000;
  - a Futures stop-limit is refused with no `POST` to `/fapi/v1/order` or `/fapi/v1/algoOrder`.
- **Mutation:** 31 mutations of the new conditions, all killed; after the review's should-fix 1, six more on the type gate, both factories, the mapper's last guard and both refusal texts, all killed.
- **Runs:** `tests/unit` + `tests/integration` 6724 passed, 4 skipped; ruff and mypy green.

## Implementation notes (written when done)
Not started.
