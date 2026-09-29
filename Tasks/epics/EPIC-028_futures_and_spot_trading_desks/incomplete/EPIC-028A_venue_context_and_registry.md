# EPIC-028A — Futures and Spot adapters live side by side in one process, each in its own `VenueContext`

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🔴 — rewires every live-trading binding in the composition root; a wrong key sends an order to the wrong venue
**Complexity:** L — composition root, config migration, metadata cache key, four docstrings
**Epic:** [EPIC-028](../README.md)
**Depends on:** ADR O1 answered

---

## 1. Context and problem
- `adapter_bindings.py` (312 lines) binds `IMarketMetadataProvider`, `IExchangeCredentialsProvider`,
  `ITradingClientFactory`, `ITradingAccountReader`, `IUserDataStream` once, branched on
  `c.resolve(TradingVenue) is SPOT_TESTNET`.
- `TradingVenue` comes from the scalar `exchange.trading_venue` (`binance_endpoints.py:95`).
- `adapter_bindings.py:146`, `i_symbol_order_metadata_cache.py`, `i_trading_client_factory.py` and
  `SPEC-012` §2 all state "exactly one venue is ever active per process".
- `TradingSessionState`, `EquityCurveRecorder`, `TradingLimitPolicy` are per-process singletons
  (`state_bindings.py`).

## 2. Acceptance criteria
- [ ] With `exchange.trading_venues: ["futures_testnet", "spot_testnet"]`, `IVenueContexts.get(FUTURES_TESTNET)` and `.get(SPOT_TESTNET)` return two contexts whose client factory, account reader, user data stream, metadata provider, credentials, session state, equity recorder and limit policy are distinct objects of the right venue.
- [ ] `get()` of a venue not enabled raises a named `VenueNotEnabledError`; `enabled()` lists exactly the configured venues in a stable order.
- [ ] A config still holding the scalar `exchange.trading_venue` loads as a one-element set, once, and is rewritten in the new shape; `"disabled"` becomes an empty set.
- [ ] `ISymbolOrderMetadataCache` is keyed by `(TradingVenue, symbol)` — BTCUSDT Futures and BTCUSDT Spot never collide (test).
- [ ] The four "one venue per process" docstrings are rewritten to describe the registry.

## 3. Design
`VenueContext` is a frozen dataclass holding one venue's ports; `VenueContextFactory.build(venue)`
is the only place a venue's adapters are constructed (it absorbs today's venue branches from
`adapter_bindings.py`). `IVenueContexts` (ABC, `trading/contracts/`) is bound once as a singleton.
Existing single-venue ports stay bound during Phase 1 as a thin shim resolving the *first* enabled
venue, so nothing breaks before `EPIC-028B` moves each caller; the shim is deleted in `EPIC-028B`.
Rejected: named DI bindings (the venue key leaks into every `resolve()` call); two processes
(ADR D2).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/venue_context.py`, `i_venue_contexts.py` | new contract + registry port |
| `src/modules/trading/composition/venue_context_factory.py` | new — the only per-venue adapter construction |
| `src/modules/trading/composition/adapter_bindings.py` | delegate to the factory; bind `IVenueContexts` |
| `src/support/binance_gateway/adapters/binance_endpoints.py` | `resolve_trading_venues()` + scalar migration |
| `src/infrastructure/persistence/symbol_order_metadata_cache.py` + port | key by `(venue, symbol)` |

## 5. Testing
Unit: registry against a real `StdLibContainer` in both one- and two-venue configs; config migration; cache key collision. Architecture guard: no file outside `venue_context_factory.py` constructs a venue adapter (extend the existing construction guards).
- Not run.

## Implementation notes (written when done)
Not started.
