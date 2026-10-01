# EPIC-028R — Futures conditional orders go through Binance's Algo Order API, tracked and cancellable

**Status:** ✅ Done (2026-10-01)
**Source:** found while building [EPIC-028O](EPIC-028O_order_contract_and_missing_reads.md) PR-1, 2026-10-01: the integration test that placed a Futures stop-limit on the fake exchange was answered `404 /fapi/v1/algoOrder`.
**Risk:** 🔴 — an order the app cannot see or cancel; Emergency Stop's reach
**Complexity:** M — one adapter path end to end, the user-data parser, the fake exchange
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028O](EPIC-028O_order_contract_and_missing_reads.md) PR-1 (the stop-limit order contract)

---

## 1. Context and problem
Since 2025-12-09 Binance serves USD-M conditional orders through the Algo Order API, and the installed `python-binance` 1.0.37 follows. `requirements.txt` does not pin its version, so a later install may route these orders differently; whether to pin it is the user's decision. Its `futures_create_order` sends every conditional type to `POST /fapi/v1/algoOrder`: `STOP`, `STOP_MARKET`, `TAKE_PROFIT`, `TAKE_PROFIT_MARKET` and `TRAILING_STOP_MARKET`. Three consequences:
- **The client order id is lost.** The library drops `newClientOrderId` and generates a random `clientAlgoId`, unless one is passed. The app tracks every order by its own client order id.
- **The order is invisible to today's reads.** An algo order is listed by `GET /fapi/v1/openAlgoOrders`, not `openOrders`. Enable's reconciliation and the open-orders query never see it.
- **Emergency Stop does not cancel it.** `DELETE /fapi/v1/allOpenOrders` leaves algo orders alone, and they are cancelled by `DELETE /fapi/v1/algoOpenOrders`. This holds today for a conditional order placed outside the app, for example in Binance's own UI.

`EPIC-028O` PR-1 therefore refuses every conditional type in the Futures mapper (`futures_order_payload_mapper.py`), so the app never sends what it cannot track.

## 2. Acceptance criteria
- [x] A Futures stop-limit is sent through the algo endpoint with `clientAlgoId` set to the app's own client order id, and read back by that id.
- [x] `get_open_orders` returns regular and algo open orders together, as `Order`s; Enable's reconciliation sees both.
- [x] `cancel_order` cancels an algo order by its client id.
- [x] Emergency Stop and `cancel_all_orders` also call `DELETE /fapi/v1/algoOpenOrders`, so a conditional order placed anywhere is cancelled. A test places one directly on the fake and shows Emergency Stop removes it.
- [x] The user-data stream's `ALGO_UPDATE` events are parsed, and the regular order a triggered algo order creates is matched back to it.
- [x] Order history includes algo orders (`GET /fapi/v1/allAlgoOrders`).
- [x] The fake Futures exchange serves the algo routes and triggers a conditional order by price.
- [x] `FUTURES_SENDABLE_ORDER_TYPES` gains `STOP_LIMIT` (the type gate then lets it through), and `src/config/cli_commands.json`'s `--type` choices list only types a venue can send.
- [x] Payload shapes are taken from the installed library (its version recorded) and Binance's documentation, and the remaining gap (no live Testnet check) is stated.

## 3. Design
**Scope.** Only the stop-limit (`STOP` on USD-M) becomes sendable. `STOP_MARKET` and `TAKE_PROFIT_MARKET` stay refused until a desk needs them (028I's TP/SL). Every read and every cancel, however, handles algo orders of any type, so an order placed outside the app (in Binance's own UI, for example) is seen and cancelled too.

- **Sending.** `futures_algo_order_mapper.py` (new) builds the `POST /fapi/v1/algoOrder` params:
  - `algoType=CONDITIONAL`, `type=STOP`, `triggerPrice` = the stop, the limit `price`, `timeInForce` and `quantity`;
  - `workingType=CONTRACT_PRICE`, so the trigger is the last price that the app's own stop check (`check_stop_trigger_side`) judges against;
  - `clientAlgoId` = the app's client order id, so the order is tracked by the id the app gave it.

  `FuturesTradingClient.place_order` calls `futures_create_algo_order` explicitly rather than relying on `futures_create_order`'s routing. In `VALIDATE_ONLY` mode a stop-limit is refused by name: the Algo Order API has no test endpoint, and `order/test` would validate a different request.
- **Reading.** `get_open_orders` returns `openOrders` and `openAlgoOrders` together.
  - An algo payload maps to an `Order`: `clientAlgoId` becomes the client order id, `orderType` the type, `triggerPrice` the stop price.
  - `algoStatus` maps to `OrderStatus`: `NEW` and `TRIGGERING` to `NEW`; `TRIGGERED` and `FINISHED` to a new terminal **`TRIGGERED`**; `CANCELED`, `REJECTED` and `EXPIRED` to themselves.
  - Why a new status: a conditional order that fired is neither filled nor cancelled. Its own life is over, and the regular order it placed carries on under its own id.
- **Cancelling.**
  - `cancel_order` tries the regular endpoint first. On Binance's `-2011` (unknown order) it cancels the algo order by `clientAlgoId`, then reads it back, because the cancel answers no order. Regular orders keep their one request.
  - `cancel_all_orders(symbol)` reads both lists and calls both `DELETE allOpenOrders` and `DELETE algoOpenOrders`, the second always, so an algo order placed between the read and the cancel is cancelled too.
  - Emergency Stop needs no change of its own: it takes its symbols from `get_open_orders`, which now lists algo orders, and cancels through `cancel_all_orders`.
- **History.** `order_history` adds `allAlgoOrders` rows to the regular rows. The same seven-day spans apply, with a 100-row limit. An algo row's executed quantity is zero by construction: its fill belongs to the regular order it placed, which `allOrders` already lists, so nothing is counted twice. `active_symbols` adds the symbols of open algo orders.
- **The user-data stream.**
  - `ALGO_UPDATE` is parsed into the algo order and, once triggered, the id of the regular order it placed (`ai`).
  - The stream keeps a bounded map from that order id to the app's client id. A later `ORDER_TRADE_UPDATE` for that order id is reported under the app's id, so a triggered stop's fill reaches the app as the order it placed.
  - Known limit: a fill reported before its `ALGO_UPDATE` keeps the exchange's id. Binance documents the algo update first.
- **The fake exchange.** `futures_algo_orders.py` (new) serves the algo routes (`POST`/`GET`/`DELETE algoOrder`, `openAlgoOrders`, `algoOpenOrders`, `allAlgoOrders`). `OrderBookState.move_price(symbol, price)` triggers every crossed conditional order: the algo order becomes `TRIGGERED` with its `actualOrderId`, and its limit order rests in the order book.
- **Type gate and CLI.** `FUTURES_SENDABLE_ORDER_TYPES` gains `STOP_LIMIT`. The CLI's `--type` choices list only `MARKET` and `LIMIT`: the CLI takes no stop price, and `STOP_MARKET`/`TAKE_PROFIT_MARKET` are sendable on neither venue.
- **Payload shapes** are taken from `python-binance` 1.0.37's `client.py` (paths and parameter names) and Binance's USD-M documentation for the Algo Order API and `ALGO_UPDATE` (field names). No live Testnet call verified them, because egress to `*.binance.*` is blocked here.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/futures_algo_order_mapper.py` (new) | stop-limit → algo params; algo payload → `Order` and `OrderRecord`; `algoStatus` and type tables |
| `src/modules/trading/adapters/binance/futures_trading_client.py` | algo place (refused in `VALIDATE_ONLY`), open orders from both lists, cancel with the `-2011` fallback, cancel-all on both endpoints |
| `src/modules/trading/adapters/binance/futures_order_payload_mapper.py` | `FUTURES_SENDABLE_ORDER_TYPES` gains `STOP_LIMIT`; the regular mapper still refuses every conditional type |
| `src/modules/trading/adapters/binance/futures_history_reader.py` | `allAlgoOrders` in order history; open algo orders in `active_symbols` |
| `src/modules/trading/adapters/binance/algo_update_parser.py` · `algo_order_links.py` · `futures_order_updates.py` (new) · `futures_user_data_stream.py` | `ALGO_UPDATE` parsed; a triggered stop's fill reported under the app's id; order messages split out of the stream |
| `src/modules/trading/contracts/order_status.py` | `TRIGGERED`, terminal |
| `src/support/binance_gateway/contracts/i_trading_session_factory.py` | the six algo calls on `ITradingSessionClient` |
| `src/config/cli_commands.json` | `--type`: `MARKET`, `LIMIT` |
| `tests/sanity/fake_exchange/futures_algo_orders.py` (new) · `futures_routes.py` · `order_book_state.py` | the algo routes; `move_price` triggers |
| `Docs/VOCABULARY/README.md` | **Conditional order** |

## 5. Testing
- **Units:**
  - **The mapper:** the exact request with the app's id as `clientAlgoId`; every refusal (wrong type, no stop or limit price, no time in force, unrounded quantity, price or stop); every `algoStatus`; a type placed in Binance's UI that the app has no member for, read as `UNKNOWN` and never lost; an algo history row with no fill of its own.
  - **The client**, against `Mock(spec=Client)` specced from the installed library: the stop-limit goes only to `futures_create_algo_order`; it is refused in `VALIDATE_ONLY` mode; open orders from both lists; a regular cancel costs one request; the algo fallback runs on `-2011` only; an id neither kind knows keeps the regular refusal; cancel-all runs the algo cancel even when the read found none.
  - **History:** algo rows, read 100 at a time; open algo orders count as active symbols.
  - **The stream:** `ALGO_UPDATE` parsed, triggered or not; the link is bounded, forgetting the oldest first; a triggered stop's fill reported under the app's id, through `FuturesUserDataStream`'s own dispatch; another fill keeps its own id; a malformed update is logged and dropped.
  - **Execute:** a Futures stop-limit is sent through the algo API with the request's client id, while `STOP_MARKET` is still refused by name.
  - **Enable** reconciles an algo order.
  - **The CLI's** `--type` choices are locked to the sendable set (red on the old choices).
  - **`TRIGGERED`** is terminal.
- **Integration** (`test_futures_algo_orders_against_fake_server.py`, the real handler, client and `python-binance`):
  - a stop-limit is posted to `/fapi/v1/algoOrder` and never to `/fapi/v1/order`, and is read back by the app's id;
  - it is cancelled by the app's id;
  - a price one tick short leaves it waiting; the trigger price places its limit order and leaves a `TRIGGERED` history row;
  - Emergency Stop cancels a conditional order placed straight on the fake and calls `DELETE /fapi/v1/algoOpenOrders`.
- **Mutation:** 25 mutations, all killed:
  - the mapper's id, trigger, status and fill;
  - the client's routing, `VALIDATE_ONLY` refusal, `-2011` branch both ways, refusal choice, algo cancel-all and algo listing;
  - history's merge, row limit and active symbols;
  - the stream's link, remap and dispatch;
  - the link's refresh and bound;
  - the parser's placed id;
  - the sendable set;
  - `TRIGGERED`'s terminality;
  - the fake's trigger boundary.
- **Runs:** `tests/unit` + `tests/integration` + `tests/sanity`: 6957 passed, 4 skipped. ruff, mypy and `ci-local.ps1 -SkipTests` green.

## Implementation notes (written when done)
- **No live check.** Paths and parameters are `python-binance` 1.0.37's, and field names Binance's documented ones. A Testnet round trip (`EPIC-028N`) is what confirms them.
  - The one shape this design depends on beyond the docs is `ALGO_UPDATE`'s `ai`.
  - If Binance reports a triggered order's fill under `clientAlgoId` itself, the fill already carries the app's id and the link goes unused. Nothing is lost.
- **Not built:**
  - sending `STOP_MARKET` / `TAKE_PROFIT_MARKET` (028I's TP/SL needs them; one table entry each);
  - trailing stops;
  - an `ALGO_UPDATE` status event on the bus. The stream still publishes fills only, as for regular orders.
- **`python-binance` is not pinned** in `requirements.txt`. A later version could change these calls; pinning it is the user's decision (§1).
