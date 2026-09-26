# EPIC-027L — Spot order truth and balances come from the Spot user data stream

**Status:** 🔵 Backlog
**Source:** follows the user's *"giao dịch spot"* request, 2026-09-26; `EPIC-021` ADR §4 ("order truth comes from the user data stream, not from the order response").
**Risk:** 🔴 — if the stream is wrong, every downstream screen, limit and emergency stop acts on false state.
**Complexity:** L — socket, parser, reconnect with generation fencing, balance feed, equity.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027H](EPIC-027H_spot_account_reader_and_holdings_model.md), [EPIC-027K](EPIC-027K_spot_trading_client_and_order_path.md)

---

## 1. Context and problem
- `FuturesUserDataStream` uses `bsm.futures_user_socket()` and handles only `ORDER_TRADE_UPDATE` and
  `ACCOUNT_UPDATE` (`adapters/binance/futures_user_data_stream.py:252,304-306`).
- The parser reads the Futures position array `"a"."P"` and the wallet balance `"a"."B"."wb"`,
  with a hard-coded `_QUOTE_ASSET="USDT"` (`user_data_event_parser.py:44,103-143`).
- Equity samples come only from Futures `ACCOUNT_UPDATE` (`futures_user_data_stream.py:364-375`).
- Spot's stream is `user_socket()` with `executionReport`, `outboundAccountPosition` and
  `balanceUpdate`.

## 2. Acceptance criteria
- [ ] A `SpotUserDataStream` implements `IUserDataStream`. Order status and fills come from
      `executionReport`; balances from `outboundAccountPosition`/`balanceUpdate`.
- [ ] It reuses the reconnect with generation fencing already proven for Futures. A stale-generation
      event is ignored and logged.
- [ ] Holdings and equity update from the stream. Nothing polls the account in a loop.
- [ ] The fee reported in `executionReport` (`n`, `N`: amount and asset) is recorded with the fill.

## 3. Design
- Share the connection/reconnect mechanism with the Futures stream (extract it if it is not already
  separable). Keep the parsers separate: the two streams describe different facts.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/spot/spot_user_data_stream.py` | new |
| `src/modules/trading/adapters/binance/spot/spot_user_data_event_parser.py` | new |
| shared reconnect helper (if extracted) | used by both streams |

## 5. Testing
- Unit: the parser against documented event payloads; fee asset; stale generation.
- Integration: a fake-exchange fill moves holdings and equity on screen.
- Not run yet.
