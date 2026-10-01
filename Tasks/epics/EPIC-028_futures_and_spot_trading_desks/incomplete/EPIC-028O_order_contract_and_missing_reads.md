# EPIC-028O — The order path carries every order the desks offer, and the panels can read every figure they show

**Status:** 🟡 In progress (2026-10-01) — PR-1 merged in #302; PR-2 (the reads) in review; PR-3 and PR-4 to do
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
- [x] Reads on `IOrderEntryTerms`, each a venue-addressed query: *(PR-2)*
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
**Four pull requests**, each reviewed on its own, because each changes a different layer and each is useful alone:
1. **PR-1, the order contract** (acceptance criteria 1–4). Merged in #302.
2. **PR-2, the reads** (criterion 5).
3. **PR-3, the fake Futures fills and Multi-Assets mode** (criteria 8 and 9).
4. **PR-4, the desk UI** (criteria 6 and 7).

The plan had three; on 2026-10-01 the reads were split from the fake's fills and Multi-Assets mode. The reads alone touch the port, five queries, four adapters and the fake's read routes. The fills change the fake's order lifecycle, which existing tests rely on, and are reviewed better on their own.

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

### PR-2 — the reads (built)
- **Where each read lives.** Each read goes on the port that already owns its kind of fact, and Spot answers from an absent port, as `account_control` set the pattern (`EPIC-028F`):
  - the leverage and margin mode (`symbolConfig`) and the brackets (`leverageBracket`) are signed reads of this account's settings, so they join `IFuturesAccountControl` and fail with its two errors. Its docstring already listed both as the next methods;
  - the best bid and ask (`ticker/bookTicker`) is public data both venues have: a new `IBookTickerReader` on every `VenueContext`;
  - the mark price (`premiumIndex`) is public data only Futures has: a new `IMarkPriceReader`, `None` on a Spot `VenueContext`.
- **"Not applicable" is a value.** `NotApplicable.ON_THIS_VENUE` is the answer of the setting, bracket and mark queries on a venue without the port. The union `X | NotApplicable` makes every caller narrow it, so no caller can size an order with a leverage of 1 or a last price passed off as a mark. A `None` would have said the same thing less plainly, and is the codebase's spelling for an unknown value, not an inapplicable one.
- **Five venue-addressed queries:** `GetFuturesSymbolSettingQuery`, `GetLeverageBracketsQuery`, `GetMarkPriceQuery`, `GetBestBidAskQuery` and `GetOrderNotionalLimitQuery`. The last answers `TradingLimitPolicy.limits.max_notional_per_order`, the figure `ExecuteOrderCommandHandler` refuses an order over, so the limit shown and the limit enforced cannot drift. One policy serves every venue today; the query names the venue so that per-venue limits change one handler.
- **`IOrderEntryTerms` gains five methods**, one per query, because each changes at its own pace (the setting on a user change, the prices every second, the limit with the configuration). `OrderEntryTermsService` checks every answer's type, so an unbound handler is named instead of reaching a panel as `None`.
- **Value types.** `FuturesSymbolSetting`, `LeverageBracket`/`LeverageBrackets` (lowest notional first, no gaps; `bracket_for(notional)` is floor-inclusive and cap-exclusive, `max_leverage` is the first bracket's), `MarkPrice` and `BestBidAsk` (`has_bid`/`has_ask`: a side counts only with a price and a quantity).
- **Answer shapes.** `leverageBracket?symbol=` answers one object, and a list without a symbol; the parser accepts both and picks the asked symbol's row, so a list can never hand back another symbol's brackets. Every reader also checks the answer's symbol. Shapes follow Binance's documentation and the installed `python-binance` 1.0.37's paths; no live call verified them (egress to `*.binance.*` is blocked here).
- **Fake exchange.** `GET /fapi/v1/symbolConfig` (Binance's defaults for a new account, 20x cross, until changed), `leverageBracket` (one five-bracket table shaped like Binance's `BTCUSDT` table), `premiumIndex` and `ticker/bookTicker` (fixed per symbol), and Spot `GET /api/v3/ticker/bookTicker` (a cent either side of the last price, so a test that moves the price moves the book). The leverage change now answers its `maxNotionalValue` from the same bracket table; leverage 10 still answers 10 000 000.

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

## 4b. Changes, per file (PR-2)
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/not_applicable.py` · `futures_symbol_setting.py` · `leverage_brackets.py` · `mark_price.py` · `best_bid_ask.py` · `market_price_unavailable_error.py` | new value types and error |
| `src/modules/trading/contracts/i_book_ticker_reader.py` · `i_mark_price_reader.py` | new ports |
| `src/modules/trading/contracts/i_futures_account_control.py` · `venue_context.py` · `i_order_entry_terms.py` | two reads; two `VenueContext` fields; five methods |
| `src/modules/trading/adapters/binance/futures_account_control.py` · `futures_account_settings_parser.py` | `symbol_setting`, `leverage_brackets` and their parsing |
| `src/modules/trading/adapters/binance/market_price_reads.py` · `futures_book_ticker_reader.py` · `futures_mark_price_reader.py` · `spot/spot_book_ticker_reader.py` | the public readers and their shared error translation |
| `src/modules/trading/application/queries/get_{futures_symbol_setting,leverage_brackets,mark_price,best_bid_ask,order_notional_limit}/` | the five queries and handlers |
| `src/modules/trading/application/orders/order_entry_terms_service.py` · `composition/venue_assembly.py` · `query_bindings.py` | the service's five reads; the readers built per venue; the handlers bound |
| `src/modules/trading/contracts/testing/` | `FakeOrderEntryTerms` seeded per symbol (`FuturesReads`); unarranged stand-ins for the new ports |
| `tests/sanity/fake_exchange/futures_market.py` · `futures_symbol_config.py` · `futures_routes.py` · `spot_routes.py` · `spot_account_state.py` | the read routes |

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

## 5b. Testing (PR-2)
- **Units.**
  - Value types: a notional's bracket at and around every cap, past the last cap, a gap and an empty table refused, a bracket no exchange would send refused; a side of the book counts only with a price and a quantity.
  - Parsers: both `leverageBracket` answer shapes, out-of-order brackets sorted, another symbol's row never read, an unknown margin type unreadable.
  - Adapters: an unreadable settings answer is `AccountControlUnavailableError` saying nothing was changed; every price reader fails only with `MarketPriceUnavailableError` (another symbol, no answer, a missing field).
  - Queries: Futures answers from its own ports, Spot answers `NotApplicable` without touching one, each venue reads its own book, the notional limit is the policy's.
  - Service: each read addressed to the service's venue, `NotApplicable` passed through, an unbound handler named.
  - Wiring: each venue's `VenueContext` holds its own readers, Spot no mark-price reader; the architecture guard lists the three new adapters as built only by `VenueAssembly`.
- **Integration** (`test_order_entry_reads_against_fake_server.py`, real adapters and `python-binance` over HTTP): the default setting, the setting read back after a change, the brackets in order with their maintenance figures, an unlisted symbol's brackets refused with `-1121`, the mark price of a flat symbol, each venue's own book, an unlisted symbol on each price read.
- **Mutation:** 15 mutations of the new conditions (the three `NotApplicable` branches, the bracket boundary, the gap check, `max_leverage`, the parser's symbol pick and sort, both symbol checks, `has_bid`, the Spot mark-price absence, the service's pass-through, the fake's bracket rule, the symbol parameter sent), all killed.
- **Runs:** `tests/unit` + `tests/integration` green; ruff and mypy green.

## Implementation notes (written when done)
Not started.
