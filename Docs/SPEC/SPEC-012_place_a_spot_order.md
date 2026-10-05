# SPEC-012 — Place an order on Spot, and see it settle as a balance

- **Status:** ✅ built and proven — the real Spot Testnet round trip (§8's last row, `EPIC-027P`
  AC5) ran on 2026-09-29: a real MARKET BUY then SELL on Binance Spot Testnet (`BTCUSDT`), holding
  returned to baseline within one lot step
- **Actor:** trader
- **Origin:** `EPIC-027K` (the Spot order path itself), `EPIC-027O` (Holdings table, BUY/SELL
  labels, SELL gated on a real holding), `EPIC-027P` (this SPEC, and the real Spot Testnet round
  trip that proves it).
- **Surfaces:** the Spot desk's order panel (`EPIC-028H`/`028L`), which the desk's Trade → New
  order… (`F9`, `EPIC-033R`) focuses · the Dev Board's order dialog
  (`F9`), which hosts the same panel when the board trades Spot (`EPIC-028M`; both replaced the
  manual-order card of `EPIC-027O`) · `trade-once --live` at the command line, venue-agnostic like
  every other caller of `ExecuteOrderCommand`.

## 1. Trigger

*"I want to buy or sell this asset on my Spot account, and I want the app to know I hold it
afterwards — not pretend I opened a leveraged position."*

## 2. Preconditions

1. Spot Testnet is enabled in Tools → Options → Trading (ADR D8 — Spot mainnet is out of scope, `EPIC-026`'s
   gates own it). This is a boot-time choice, not a per-order one: on the Spot desk
   `MarketType.SPOT` follows from its venue everywhere this use case reads it (`ADR D1`).
2. Live trading is on (SPEC-004) — for a **live** submission only, same as SPEC-005.
3. Credentials resolve (`BINANCE_SPOT_TESTNET_API_KEY`/`_SECRET`, or the shared
   `secrets.local.json` fallback) and the connection is reachable.
4. For a SELL: a real, non-dust holding of the target asset — read fresh, at submit time, never
   assumed from what the screen last showed (§3 step 4).

## 3. Main flow

1. The actor uses the Spot desk's order panel (`F9` focuses it; or the Dev Board's `F9` dialog on a Spot board) for
   the symbol shown, and types a Buy or a Sell: Limit, Market or Stop-limit. The sides read
   **Buy** and **Sell**, not Long and Short — the same domain direction
   (`ManualOrderDirection.LONG`/`SHORT`) `manual_order_intent_for()` keys off, named for what the
   actor is actually doing (a Spot account has no position to open or close).
2. The panel shows each side what it can spend — the quote asset for Buy, the base asset for
   Sell — and disables Sell while the account it last read holds none of the base asset, so the
   actor is not invited to click a button that will only be refused.
3. BUY needs no such check: a flat Spot account can always buy more of an asset, the same as
   Futures' unconditional Long-when-flat case.
4. On submit, the app re-reads the account's real holdings (never the UI's own cache) and maps
   the click through `manual_order_intent_for()`, passing that fresh holding:
   - **BUY** → `OrderSide.BUY`, `reduce_only=False` — Spot's `create_order` rejects
     `reduceOnly` outright, so this is always false here, never computed from a position.
   - **SELL**, a real non-dust holding exists → `OrderSide.SELL`, `reduce_only=False`.
   - **SELL**, no real holding (or only dust) → refused with `ManualShortNotSupportedOnMarketError`
     **before** the order is even built — a Spot account has no leveraged position to open a
     short in, and there is nothing real to sell instead.
5. The order then crosses the same pipeline SPEC-005 describes step by step — normalise against
   the symbol's Spot exchange filters (`SpotMetadataProvider`, its own `NOTIONAL` filter name and
   `MARKET_LOT_SIZE` fallback, not Futures' `MIN_NOTIONAL`/`LOT_SIZE`), the four safety gates, the
   minimum-notional check, the four session limits, then submission through `SpotTradingClient`.
6. A filled order moves the account's real balances immediately (Spot has no matching delay for
   a MARKET order): the base asset for a BUY, the quote asset for a SELL, each net of the
   exchange's own commission, charged in the asset received.
7. The next read of `ITradingAccountReader.check_connection().holdings` — polled by
   `HoldingsRefreshService`, republished as `HoldingsChangedEvent`, rendered by the Spot desk's
   Assets tab and the Dev Board's Holdings table — reflects the new balance. There is no position to reconcile: the balance
   itself **is** the truth (ADR D7).

## 4. What must be true afterwards

- The Holdings table's number for the traded asset is the account's real, current balance — not
  a locally-computed delta the app trusts on its own.
- No `LivePosition` is ever fabricated for a Spot fill: no invented entry price, mark price,
  leverage or liquidation price (ADR D7, `domain-truth-rule.md`). `SpotTradingClient.
  get_positions()` always answers `[]`, and every caller already treats that as the true "flat"
  answer for this venue, not a fabricated one.
- A refused SELL is a **named** domain error (`ManualShortNotSupportedOnMarketError`), never a
  silently-reinterpreted BUY or a Sell that goes through against a holding that was not actually
  there.
- Every other safety gate, limit and rejection shape SPEC-005 §4 describes applies unchanged —
  Spot is a different market, not a different pipeline.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| The actor clicks SELL with no real holding of the asset | `ManualShortNotSupportedOnMarketError`'s message: Spot has no leveraged position to open a short in, and there is no sellable holding of this asset | Refused in the domain layer, before an `OrderIntent` is even built — the same "refuse cheap, before any network call" discipline SPEC-005's safety gates already follow |
| The cached SELL-enabled state is stale (a holding sold elsewhere since the last Holdings refresh) | The click still reaches the real pipeline, and the fresh re-check at submit time refuses it the same way as above | The UI's `has_holding()` is a preemptive convenience, never the authority — the domain re-check is (`EPIC-027O`'s own design decision, defense in depth) |
| Any gate, limit or exchange rejection SPEC-005 §5 already describes | The same named outcome, on this venue too | The pipeline is shared; only the market-specific inputs (filters, the SELL precondition) differ |

## 6. What this use case does NOT promise

- **No margin, no leverage, no liquidation.** `TradingVenue.SPOT_TESTNET`'s effective leverage is
  always 1×; there is no concept of a liquidation price to report or protect against.
- **No average entry price.** `SpotHolding` carries only `asset`/`free`/`locked` — computing a
  cost basis is `GET /api/v3/myTrades`, explicitly deferred (ADR O6), not silently approximated.
- **It does not promise the fill price or quantity beyond what the account's own updated balance
  shows.** Same limit SPEC-005 §6 states for a market order's notional.
- **It does not switch the trading market mid-session.** The venue — and therefore the market
  this use case trades — is fixed at boot (ADR D1); the Dev Board's own Market combo changes only
  which market's **candles** the chart shows, a separate, view-only choice (SPEC-002).

## 7. Ports and modules it exercises

`trading`: the same `IOrderSubmission`/`ITradingClient`/`IMarketMetadataProvider` vocabulary
SPEC-005 names, now with `SpotTradingClient`/`SpotMetadataProvider` bound behind those ports for
`TradingVenue.SPOT_TESTNET` (`EPIC-027K`, `EPIC-027I`). `manual_order_intent_for()` gains a
`spot_holding: SpotHolding | None` parameter and a `market_type` parameter — the same
domain policy SPEC-005 exercises, extended rather than duplicated. `ITradingAccountReader.
check_connection().holdings` — the read this whole use case's "afterwards" section depends on,
unchanged from `EPIC-027H` — and `HoldingsChangedEvent`/`HoldingsRefreshService`/
`LiveOrderBookCoordinator` (`EPIC-027O`), which carry that read to the Assets tab; the order
panel reads the same holdings for its Sell side.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| `manual_order_intent_for()`'s Spot rows: BUY always allowed, SELL refused without a real or non-dust holding, SELL allowed with one, independent of `current_position` | `tests/unit/modules/trading/domain/policies/test_manual_order_intent.py` | unit |
| The Spot panel disables Sell without a holding and offers its own order types | `tests/unit/modules/trading/ui/desk/test_order_entry_panel.py` | unit |
| A Sell is sent as a sell of the held asset; one whose holding is gone at submit time is refused | `tests/unit/modules/trading/ui/desk/test_order_entry_presenter.py` | unit |
| A Buy on the Spot desk shows the bought asset in Assets | `tests/unit/modules/trading/ui/desk/test_spot_desk_journey.py` | unit |
| The Spot desk's Trade → New order… (`F9`) focuses its order panel and places nothing | `tests/unit/modules/trading/ui/desk/test_desk_new_order.py` | unit |
| The strategy card hides leverage on Spot | `tests/unit/modules/trading/ui/dashboard/test_dev_board_panel.py` | unit |
| The Spot order path's own mapping, rounding and Futures-only-type refusal | `tests/unit/modules/trading/adapters/binance/spot/test_spot_order_payload_mapper.py` | unit |
| A real BUY click's mapped `ExecuteOrderCommand`, dispatched through the real handler, reaches the wire and moves the exact balance `SpotAccountReader.check_connection()` reports afterwards | `tests/integration/application/test_spot_manual_order_pipeline_against_fake_server.py` | integration |
| The Spot order lifecycle (place → open → cancel → gone, a MARKET order fills immediately, positions always empty) against a real HTTP round trip through the fake exchange | `tests/integration/infrastructure/binance/test_spot_trading_client_order_lifecycle_against_fake_server.py` | integration |
| A real BUY then SELL round trip on the real Spot Testnet, the holding returning to its pre-trade baseline | `tests/testnet/spot/test_spot_order_lifecycle.py` — **the user runs it**: `SEW_TESTNET_TESTS=1` plus real Spot Testnet credentials, via `ci-local.ps1 -TestnetOnly`; the ordinary gate never invokes this tier | human |
