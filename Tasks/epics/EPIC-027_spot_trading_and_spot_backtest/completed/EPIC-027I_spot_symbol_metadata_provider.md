# EPIC-027I — Live Spot orders are rounded with Spot's own exchange filters

**Status:** ✅ Done (2026-09-27)
**Source:** found while measuring the Spot gap, 2026-09-26. It is part of the user's *"giao dịch spot"* request.
**Risk:** 🟢 — a pure parser and provider; the rounding policy itself is already exchange-agnostic.
**Complexity:** S — one provider, one parser branch, a market-neutral port name.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027G](EPIC-027G_spot_testnet_venue_and_credentials.md)

---

## 1. Context and problem
- `IMarketMetadataProvider` was typed to `FuturesSymbolMetadata`
  (`contracts/futures_symbol_metadata.py`).
- `FuturesMetadataProvider` always read `futures_exchange_info()` on a testnet client and ignored the
  venue (`adapters/binance/futures_metadata_provider.py`).
- The Futures parser reads `MIN_NOTIONAL` (`notional` or `minNotional`), but **not** the `NOTIONAL`
  filter Spot uses today. On a Spot payload it would silently default the minimum notional to 5. It
  also ignores `MARKET_LOT_SIZE`.
- `OrderQuantityRoundingPolicy` is Decimal and exchange-agnostic, so it is reused unchanged.

## 2. Acceptance criteria
- [x] A market-neutral metadata type and port. The Futures provider and a new Spot provider both
      implement it. The provider is chosen by the venue's `market_type`.
- [x] The Spot provider reads `GET /api/v3/exchangeInfo` and parses `PRICE_FILTER`, `LOT_SIZE`,
      `MARKET_LOT_SIZE` and `NOTIONAL` (`minNotional`, `applyToMarket`). A missing required filter is
      an error, not a silent default.
- [x] A Spot MARKET order is rounded with `MARKET_LOT_SIZE` when present, and a LIMIT order with
      `LOT_SIZE`.

## 3. Design
- **Renamed `FuturesSymbolMetadata` → `SymbolOrderMetadata` in place**, rather than adding a parallel
  type: the acceptance criterion requires both providers to return the *same* type, and a
  "Futures"-named type returned by a Spot provider would violate `code/naming.md` #1 (reveal intent).
  `IFuturesSymbolMetadataCache`/`InMemoryFuturesSymbolMetadataCache` renamed to
  `ISymbolOrderMetadataCache`/`InMemorySymbolOrderMetadataCache` for the same reason — the cache was
  already 100% market-neutral, only ever coupled to the old type name. `IMarketMetadataProvider`'s own
  name needed no change. `futures_metadata_parser.py`, `FuturesMetadataProvider` and
  `futures_metadata_provider.py` keep their names: they remain genuinely Futures-specific, only their
  return-type import changed.
- Added `market_step_size: Decimal | None = None` and `step_size_for(order_type: OrderType) -> Decimal`
  to `SymbolOrderMetadata` — a non-boolean-flag method (`code/quality.md` #7) selecting `MARKET_LOT_SIZE`
  for `OrderType.MARKET` when published, falling back to `LOT_SIZE` otherwise (every Futures symbol
  today; any Spot symbol whose `exchangeInfo` omits the filter). Every other `OrderType`, `STOP_MARKET`
  included, uses `LOT_SIZE` directly, matching this task's own acceptance wording ("a LIMIT order with
  `LOT_SIZE`") and Binance's own semantics (a stop order rests on the book like a limit order).
- **Reuse vs. reinvent (§3's own open question, resolved):** the backtest side's
  `market_metadata_parser.py` parses Spot filters into a `float`-shaped `SymbolMarketMetadata`
  (`BOT-095E1`) for the broker simulator. The live side needs `Decimal` — comparing `stepSize`/
  `tickSize` as `float` is the exact trap `ONBOARDING.md` §8 names from a real prior incident — so
  `spot_metadata_parser.py` is a **new, independent** Decimal parser, not a reuse of the float one. It
  sits on the same shelf as `futures_metadata_parser.py` (`architecture-rule.md` §5): same abstraction
  level, same kind of input, deliberately not merged into one file because their failure policies are
  opposite (see next point) and `architecture-rule.md` §3 already bars a `trading`/`market_data`
  cross-module share for this.
- **Deliberate divergence from Futures' parser, by design, not an oversight:**
  `futures_metadata_parser.py` defends against a missing filter with a named default (documented in its
  own module docstring: "never crash"). `spot_metadata_parser.py` does the opposite — it **raises**
  `KeyError` naming the missing filter type or field. This is exactly what this task's own acceptance
  criterion asks for ("a missing filter is an error, not a silent default"), and Futures' existing,
  test-covered defensive behaviour is completely unchanged; only the new Spot path is strict. Only
  `MARKET_LOT_SIZE` is treated as genuinely optional (see above), since Binance does not publish it for
  every symbol.
- **Cache symbol-collision risk — resolved as a non-issue, documented, not engineered around:** Futures
  and Spot can both use the string `BTCUSDT` for two different instruments. This would be a real
  collision in one `ISymbolOrderMetadataCache` instance keyed by bare `symbol` if both markets were ever
  live in the same process — they are not: exactly one `TradingVenue` is resolved at boot
  (`ONBOARDING.md` §7's authority table). Documented explicitly in the port's own docstring with a
  forward-note to key by `(TradingVenue, symbol)` if that assumption ever changes, rather than adding
  unused complexity now (`code/quality.md` #6: seam now, variant later).
- **Session construction:** `SpotSessionFactory.create_metadata_client()` mirrors
  `FuturesSessionFactory.create_futures_metadata_client()` — an unsigned client, on no port (its only
  caller is this module's own `SpotMetadataProvider`), added to the same file already on the
  architecture guard's allow-list (`test_only_the_session_factory_constructs_binance_client.py`), so no
  guard update was needed.
- **Composition:** `adapter_bindings.py`'s `IMarketMetadataProvider` binding now venue-branches exactly
  like `ITradingAccountReader`'s own bind (`EPIC-027H`) — `SpotMetadataProvider` for
  `TradingVenue.SPOT_TESTNET`, unchanged `FuturesMetadataProvider` for every other venue (including
  `DISABLED`, matching every other unconditional read-only bind in this file).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/symbol_order_metadata.py` | renamed from `futures_symbol_metadata.py`; added `market_step_size`, `step_size_for()` |
| `src/modules/trading/contracts/i_market_metadata_provider.py` | docstring made market-neutral (no rename) |
| `src/modules/trading/contracts/i_symbol_order_metadata_cache.py` | renamed from `i_futures_symbol_metadata_cache.py` |
| `src/infrastructure/persistence/symbol_order_metadata_cache.py` | renamed from `futures_symbol_metadata_cache.py` |
| `src/modules/trading/adapters/binance/futures_metadata_parser.py` | import/return-type updated only; behaviour unchanged |
| `src/modules/trading/adapters/binance/spot/spot_metadata_parser.py` | new — strict Spot `exchangeInfo` parser |
| `src/modules/trading/adapters/binance/spot/spot_metadata_provider.py` | new — `SpotMetadataProvider` |
| `src/modules/trading/adapters/binance/spot/spot_session_factory.py` | added `create_metadata_client()` |
| `src/modules/trading/composition/adapter_bindings.py` | `IMarketMetadataProvider` now venue-branches |
| ~20 other `src/`/`scripts/` files and ~15 test files | mechanical identifier rename only (old-name grep returns zero hits) |

## 5. Post-review correction (2026-09-27, PR #283)
Independent review found a BLOCKING gap: `SymbolOrderMetadata.step_size_for(order_type)` existed and was
unit-tested in isolation, but `PreviewOrderQueryHandler.execute()` — the only place a live order's
quantity is rounded (`ExecuteOrderCommandHandler` delegates to it) — still rounded unconditionally with
`metadata.step_size` (`LOT_SIZE`'s own step), never calling `step_size_for()`. Acceptance criterion #3
("a MARKET order is rounded with `MARKET_LOT_SIZE` when present, and a LIMIT order with `LOT_SIZE`") was
checked `[x]` above without being satisfied by any code path, and nothing gated this off as Phase-3
work: `OrderSubmissionService.preview()` reaches this handler with no `TradingVenue` gate, so a Spot
MARKET preview was reachable and silently wrong today. Fixed by making the handler call
`metadata.step_size_for(query.order_type)` once and reuse the result for both the rounded quantity and
`OrderPreview.step_size` (`preview_order/handler.py`). Two new end-to-end tests
(`test_preview_order.py`) prove the wiring itself, not just the isolated dataclass method: a MARKET
order rounds with `MARKET_LOT_SIZE` when published, a LIMIT order ignores it even when published.
Mutation-verified: reverting the fix to plain `metadata.step_size` makes the new MARKET test fail for
exactly this reason.

## 6. Testing
- Unit: `tests/unit/modules/trading/adapters/binance/spot/test_spot_metadata_parser.py` — real
  fixture-shaped BTCUSDT entry, decimal exactness, `MARKET_LOT_SIZE` absent, missing-status default,
  each of `PRICE_FILTER`/`LOT_SIZE`/`NOTIONAL` missing raises `KeyError`, a filter missing a required
  field raises, a non-dict filter list item is still skipped defensively, catalog-level parsing
  (one-per-symbol, skips non-dict entries, empty catalog, propagates a malformed entry's own error).
- Unit: `tests/unit/modules/trading/contracts/test_symbol_order_metadata.py` — `step_size_for()`:
  LIMIT always uses `LOT_SIZE`; MARKET uses `MARKET_LOT_SIZE` when present, falls back to `LOT_SIZE`
  when absent; `STOP_MARKET` uses `LOT_SIZE`, not `MARKET_LOT_SIZE`.
- Unit: `tests/unit/modules/trading/test_module_metadata_provider_binding.py` — `IMarketMetadataProvider`
  resolves `FuturesMetadataProvider` for no venue / `DISABLED` / `FUTURES_TESTNET`, and
  `SpotMetadataProvider` for `SPOT_TESTNET`, against the real `StdLibContainer` and production
  `bind_adapters()`.
- Integration: `tests/integration/infrastructure/binance/test_spot_metadata_provider_against_fake_server.py`
  — real HTTP round trip through `tests/sanity/fake_exchange/spot_routes.py`'s existing
  `_SPOT_EXCHANGE_INFO` fixture (`EPIC-027J`); proves `refresh()`'s real filter values and the
  cache-first contract (a cache hit issues no second request).
- All 24 new tests pass. Regression: full `tests/unit/architecture` (451 passed), every unit/integration
  test file touched by the mechanical rename (119 + 11 passed), `ruff check`/`ruff format --check`
  clean, `mypy src scripts` unchanged at the frozen 584-error baseline (zero new errors in any file this
  task touched, confirmed by diffing the full mypy run before and after).
