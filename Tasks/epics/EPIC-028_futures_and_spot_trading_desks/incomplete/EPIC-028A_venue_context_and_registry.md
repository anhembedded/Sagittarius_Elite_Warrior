# EPIC-028A — Futures and Spot adapters live side by side in one process, each in its own `VenueContext`

**Status:** 🟡 Awaiting review (2026-09-29) — implemented and verified on the fast tier; code merge waits on the independent review (`ONBOARDING.md` §7)
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🔴 — rewires every live-trading binding in the composition root; a wrong key sends an order to the wrong venue
**Complexity:** L — composition root, config reader, per-venue metadata cache, three docstrings
**Epic:** [EPIC-028](../README.md)
**Depends on:** ADR O1 — ✅ answered 2026-09-29 (one process, both venues)

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
Scope changes made during implementation are marked **(re-scoped)** with the reason in the implementation notes.
- [x] With `exchange.trading_venues: ["futures_testnet", "spot_testnet"]`, `IVenueContexts.get(FUTURES_TESTNET)` and `.get(SPOT_TESTNET)` return two contexts whose client factory, account reader, user data stream, metadata provider, credentials, metadata cache, session state and equity recorder are distinct objects of the right venue. **(re-scoped: `TradingLimitPolicy` stays one shared instance, see note 3.)** — `test_module_venue_contexts_binding.py`: `test_each_venue_gets_its_own_venue_shaped_adapters`, `test_venues_share_no_credentials_and_no_metadata_cache`, `test_session_state_and_equity_recorder_are_owned_per_venue`.
- [x] `get()` of a venue not enabled raises a named `VenueNotEnabledError`; `enabled()` lists exactly the configured venues in a stable order. — `test_a_venue_that_is_not_enabled_raises`, `test_disabled_is_never_a_gettable_venue`, `test_both_venues_are_enabled_in_configuration_order`.
- [x] A config still holding the scalar `exchange.trading_venue` loads as a one-element set; `"disabled"` becomes an empty set. **(re-scoped: the rewrite into the new shape moved to `EPIC-028C`, see note 1.)** — `test_resolve_trading_venues.py`.
- [x] BTCUSDT Futures and BTCUSDT Spot never collide in the order-metadata cache. **(re-scoped: one cache instance per venue instead of a `(TradingVenue, symbol)` key, see note 2.)** — `test_venues_share_no_credentials_and_no_metadata_cache` + guard `test_only_the_venue_assembly_constructs_venue_adapters.py`.
- [x] The "one venue per process" docstrings are rewritten to describe the registry: `adapter_bindings.py`, `i_symbol_order_metadata_cache.py`, `symbol_order_metadata_cache.py`, `i_trading_client_factory.py`. **(re-scoped: `SPEC-012` §2 is rewritten in `EPIC-028M` with the rest of the SPEC/HLD, see note 5.)**

## 3. Design
`VenueContext` is a frozen dataclass holding one venue's ports. `VenueAssembly` (composition,
named instead of the planned `VenueContextFactory` because it caches as well as builds) is the only
place a venue's adapters are constructed; it absorbs today's venue branches from
`adapter_bindings.py`, and builds each part lazily on first use. `VenueContexts` implements
`IVenueContexts` (ABC, `trading/contracts/`) and is bound once as a singleton.
Existing single-venue ports stay bound during Phase 1 as a thin shim resolving the *primary* venue
(first enabled, else `DISABLED`), so nothing breaks before `EPIC-028B` moves each caller; the shim
is deleted in `EPIC-028B`.
Rejected: named DI bindings (the venue key leaks into every `resolve()` call); two processes
(ADR D2).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/venue_context.py`, `i_venue_contexts.py` | new contract + registry port + `VenueNotEnabledError` |
| `src/modules/trading/composition/venue_assembly.py` | new — the only per-venue adapter construction |
| `src/modules/trading/composition/venue_contexts.py` | new — `IVenueContexts` backed by one assembly per venue |
| `src/modules/trading/composition/adapter_bindings.py` | bind `VenueContexts`/`IVenueContexts`; single-venue ports become primary-venue shims |
| `src/modules/trading/composition/state_bindings.py` | `TradingSessionState` is the primary assembly's own |
| `src/support/binance_gateway/contracts/binance_endpoints.py`, `src/config/config_keys.py` | `resolve_trading_venues()` + `EXCHANGE_TRADING_VENUES` |
| `tests/unit/architecture/allowlist_module_boundaries.txt` | three entries follow the constructions from `adapter_bindings` to `venue_assembly` (count unchanged) |

## 5. Testing
- `tests/unit/support/binance_gateway/contracts/test_resolve_trading_venues.py` — list, list over scalar, empty list, scalar-only (three venues), no key, unknown entry, `disabled`/repeat, non-list.
- `tests/unit/modules/trading/test_module_venue_contexts_binding.py` — the registry against the real `StdLibContainer` + `bind_adapters()`/`bind_state()`, one- and two-venue and nothing-enabled configs.
- `tests/unit/architecture/test_only_the_venue_assembly_constructs_venue_adapters.py` — `src/` scan; row in `scanned_roots_registry.py`.
- Mutation checks (2026-09-29): a process-wide shared metadata cache → `test_venues_share_no_credentials_and_no_metadata_cache` red; `TradingSessionState` bound to a fresh instance instead of the assembly's → `test_session_state_and_equity_recorder_are_owned_per_venue` red; a stray `InMemorySymbolOrderMetadataCache()` in `venue_contexts.py` → the guard red. All restored.
- Fast tier (2026-09-29): `ruff check`, `ruff format --check`, `mypy` (740 files) clean; `tests/unit/architecture` 469 passed; `tests/unit/modules/trading` + `tests/unit/support` + `tests/unit/config` + `tests/integration` 2335 passed, 4 skipped; `tests/sanity` 32 passed (its one `gc` `ResourceWarning` at interpreter shutdown reproduces identically on the base tree).
- Full gate: GitHub Actions on the pushed head.

## Implementation notes (written when done)
1. **No config rewrite here.** `resolve_trading_venues()` only reads. The one writer of the venue key is the Settings page, and it changes in `EPIC-028C` (per-venue toggles); the rewrite moved there as an acceptance criterion. Until then a scalar-only config reads exactly as before, and a config that holds the list lets the list win.
2. **Per-venue cache, not a composite key.** Each `VenueAssembly` owns its own `InMemorySymbolOrderMetadataCache`, and each venue's metadata provider only ever writes its own. A `(venue, symbol)` key would have changed the port's signature and every caller for a collision that separate instances already make impossible; the guard stops a shared instance from reappearing.
3. **`TradingLimitPolicy` stays one instance.** It is stateless (the per-session counters live in `TradingSessionState`, which is now per venue), so a second copy would hold identical config values. If per-venue limits are ever wanted, that is a config change first.
4. **State ownership.** `TradingSessionState` and `EquityCurveRecorder` are per venue, owned by `VenueAssembly` and wired into that venue's own user data stream. They are not on `VenueContext` yet, because `VenueContext` holds ports only; `EPIC-028B` exposes them when commands name their venue.
5. **`SPEC-012` §2** still states one venue per process. It stays until `EPIC-028M`, which rewrites the trading SPEC/HLD once the two desks exist; changing it now would describe a UI that does not exist yet.
6. **Lazy parts.** `VenueAssembly` builds each part on first use (`cached_property`), so resolving one venue's metadata provider never resolves `IEventBus`/`ITaskManager`. Existing binding tests that bind only `IConfig` keep working unchanged.
