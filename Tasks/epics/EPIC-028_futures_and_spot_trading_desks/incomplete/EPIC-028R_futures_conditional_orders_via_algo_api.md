# EPIC-028R — Futures conditional orders go through Binance's Algo Order API, tracked and cancellable

**Status:** 🔵 Backlog
**Source:** found while building [EPIC-028O](EPIC-028O_order_contract_and_missing_reads.md) PR-1, 2026-10-01: the integration test that placed a Futures stop-limit on the fake exchange was answered `404 /fapi/v1/algoOrder`.
**Risk:** 🔴 — an order the app cannot see or cancel; Emergency Stop's reach
**Complexity:** M — one adapter path end to end, the user-data parser, the fake exchange
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028O](EPIC-028O_order_contract_and_missing_reads.md) PR-1 (the stop-limit order contract)

---

## 1. Context and problem
Since 2025-12-09 Binance serves USD-M conditional orders through the Algo Order API, and the pinned `python-binance` 1.0.37 follows. Its `futures_create_order` sends every conditional type to `POST /fapi/v1/algoOrder`: `STOP`, `STOP_MARKET`, `TAKE_PROFIT`, `TAKE_PROFIT_MARKET` and `TRAILING_STOP_MARKET`. Three consequences:
- **The client order id is lost.** The library drops `newClientOrderId` and generates a random `clientAlgoId`, unless one is passed. The app tracks every order by its own client order id.
- **The order is invisible to today's reads.** An algo order is listed by `GET /fapi/v1/openAlgoOrders`, not `openOrders`. Enable's reconciliation and the open-orders query never see it.
- **Emergency Stop does not cancel it.** `DELETE /fapi/v1/allOpenOrders` leaves algo orders alone, and they are cancelled by `DELETE /fapi/v1/algoOpenOrders`. This holds today for a conditional order placed outside the app, for example in Binance's own UI.

`EPIC-028O` PR-1 therefore refuses every conditional type in the Futures mapper (`futures_order_payload_mapper.py`), so the app never sends what it cannot track.

## 2. Acceptance criteria
- [ ] A Futures stop-limit is sent through the algo endpoint with `clientAlgoId` set to the app's own client order id, and read back by that id.
- [ ] `get_open_orders` returns regular and algo open orders together, as `Order`s; Enable's reconciliation sees both.
- [ ] `cancel_order` cancels an algo order by its client id.
- [ ] Emergency Stop and `cancel_all_orders` also call `DELETE /fapi/v1/algoOpenOrders`, so a conditional order placed anywhere is cancelled. A test places one directly on the fake and shows Emergency Stop removes it.
- [ ] The user-data stream's `ALGO_UPDATE` events are parsed, and the regular order a triggered algo order creates is matched back to it.
- [ ] Order history includes algo orders (`GET /fapi/v1/allAlgoOrders`).
- [ ] The fake Futures exchange serves the algo routes and triggers a conditional order by price.
- [ ] Payload shapes are taken from the pinned library and Binance's documentation, and the remaining gap (no live Testnet check) is stated.

## 3. Design
To be written when started.

## 4. Changes, per file
To be written when started.

## 5. Testing
- Not run.

## Implementation notes (written when done)
Not started.
