# EPIC-027H — The app reads a Spot account as balances and holdings, never as a futures position

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot"* ("I want to trade spot").
**Risk:** 🟡 — read-only, but it defines what "a position" means for everything built on top.
**Complexity:** M — domain type, adapter, snapshot mapping, read-only CLI first contact.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027G](EPIC-027G_spot_testnet_venue_and_credentials.md), [EPIC-027J](EPIC-027J_fake_exchange_spot_routes.md). ADR O6 must be answered before the entry-price criterion.

---

## 1. Context and problem
- `FuturesAccountReader` calls `futures_account`, `futures_get_position_mode` and similar
  endpoints, and reads the `USDT` asset only (`adapters/binance/futures_account_reader.py:58,67,126-152`).
- `LivePosition` is a signed amount with mark price, leverage, margin type and liquidation price
  (`contracts/live_position.py:192-212`).
- The Spot API returns per-asset `free`/`locked` balances (`GET /api/v3/account`). It returns no
  position, no entry price, no mark price and no liquidation price.
- `IAccountSnapshot` already states that Spot would answer `None` for the futures-only fields
  (`i_account_snapshot.py:21-25`). The seam was anticipated, but never filled.
- `ExchangeConnectionStatus` flags hedge mode as unsupported (`exchange_connection_status.py:290`).
  Spot has no such mode.

## 2. Acceptance criteria
- [ ] A `SpotHolding` value type carries asset, free, locked and a dust threshold. It has no field that
      Spot does not provide.
- [ ] A `SpotAccountReader` implements `ITradingAccountReader` over `ping`, `get_server_time` and
      `get_account`, and reports connection, permissions and balances.
- [ ] `exchange-status` against Spot Testnet (read-only) prints balances, and names a Futures key used
      by mistake as a key error, not a network error.
- [ ] Equity for Spot is the quote balance plus holdings × last price. The price source is named in the
      log.
- [ ] The average entry price comes from the source chosen in ADR O6. Until then it is shown as
      "not available", never guessed.

## 3. Design
- Holdings are their own type, not a `LivePosition` with zeros (ADR D7; `domain-truth-rule.md`).
  Consumers that need "is something open on this symbol" get a small read port that both markets
  can answer: Futures from its position, Spot from its base balance above dust.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/spot_holding.py` | new value type |
| `src/modules/trading/adapters/binance/spot/spot_account_reader.py` | new adapter |
| `src/modules/trading/contracts/i_account_snapshot.py` and implementers | Spot answers |
| `src/presentation/cli/exchange_status_formatter.py` | Spot output and key-mixup message |

## 5. Testing
- Unit: parsing of `GET /api/v3/account`; dust; equity.
- Integration: against the fake exchange's Spot account route (`EPIC-027J`).
- Opt-in testnet tier: `EPIC-027P`.
- Not run yet.
