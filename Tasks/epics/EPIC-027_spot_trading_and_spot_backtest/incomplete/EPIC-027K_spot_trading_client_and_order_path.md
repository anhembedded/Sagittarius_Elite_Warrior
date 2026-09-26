# EPIC-027K — A Spot MARKET or LIMIT order goes through the same `ExecuteOrderCommand` to Spot Testnet

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot"* ("I want to trade spot").
**Risk:** 🔴 — the first Spot order ever sent; a wrong payload is a real (testnet) order.
**Complexity:** L — adapter, payload mapper, order vocabulary, cancel paths.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027F](EPIC-027F_venue_selected_trading_client_factory.md), [EPIC-027G](EPIC-027G_spot_testnet_venue_and_credentials.md), [EPIC-027I](EPIC-027I_spot_symbol_metadata_provider.md), [EPIC-027J](EPIC-027J_fake_exchange_spot_routes.md)

---

## 1. Context and problem
- The only `ITradingClient` is `FuturesTradingClient`. It calls `futures_create_order` and similar
  endpoints (`adapters/binance/futures_trading_client.py:67-149`).
- The payload mapper always sends `positionSide="BOTH"` and `reduceOnly`
  (`futures_order_payload_mapper.py:50,82-83`). The Spot API rejects both.
- `OrderType` includes `STOP_MARKET`/`TAKE_PROFIT_MARKET` (`contracts/order_type.py:135-138`). These
  are Futures-only. Spot uses `STOP_LOSS(_LIMIT)`/`TAKE_PROFIT(_LIMIT)`/`LIMIT_MAKER`.
- `Order.reduce_only` and `OrderIntent.reduce_only` exist because, in one-way Futures, SELL can mean
  "close long" or "open short". On Spot, SELL can only reduce a holding.

## 2. Acceptance criteria
- [ ] A `SpotTradingClient` implements `ITradingClient`: place (MARKET, LIMIT), cancel one, cancel all,
      open orders. `get_positions` is not faked: the port is split, or Spot answers through the
      holdings port from `EPIC-027H`.
- [ ] A Spot payload never contains `reduceOnly` or `positionSide`. A test asserts the exact payload
      against the fake exchange.
- [ ] Sending a Futures-only order type to a Spot venue is refused before the network, with a named
      reason.
- [ ] The factory from `EPIC-027F` returns the Spot client for `SPOT_TESTNET`. No handler is edited
      for this.
- [ ] A client order id is on every Spot order (`newClientOrderId`), as on Futures.
- [ ] `VALIDATE_ONLY` mode uses `POST /api/v3/order/test`.

## 3. Design
- `reduce_only` is not deleted from the shared contract (Futures needs it). For Spot it is a
  precondition: a SELL is always reducing, and `reduce_only=False` together with SELL is refused
  (ADR D4 — never a short on Spot).
- If `ITradingClient.get_positions` cannot be answered truthfully by Spot, the port is split
  (Interface Segregation, `architecture-rule.md` §1) rather than returning invented positions.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/spot/spot_trading_client.py` | new adapter |
| `src/modules/trading/adapters/binance/spot/spot_order_payload_mapper.py` | new mapper |
| `src/modules/trading/contracts/order_type.py` | market-aware validity of order types |
| `src/modules/trading/adapters/binance/trading_client_factory.py` | the Spot row |
| `src/support/binance_gateway/contracts/i_trading_session_factory.py` | Spot-shaped session protocol |

## 5. Testing
- Unit: mapper per order type; refusal of Futures-only types; SELL precondition.
- Integration: place, fill and cancel against the fake exchange's Spot routes.
- Real Spot Testnet: `EPIC-027P`.
- Not run yet.
