# BUG-127 — the Backtest screen's exchange-rule check has never checked anything

- **Reported:** 2026-09-16 (found while measuring `EPIC-025D` item 2, not by a user)
- **Severity:** 🟠 P2 — no wrong number is shown and no money is at risk; a shipped feature simply
  does nothing, and its failure mode is a message that looks like a normal "not yet" state
- **Status:** ✅ **Fixed 2026-09-16** — root-caused by measurement against the real object graph,
  reproduced by a regression test confirmed red for the right reason, fixed as the mechanism, and
  verified by positive log evidence that the new path runs (§3 below, not merely the absence of the
  old symptom).

## 1. Symptom

The Backtest screen shows a "market rule verification" line whose job (`BOT-095E1`) is to say
whether the configured symbol and starting capital would satisfy the exchange's order rules —
minimum notional, lot step, price tick — before a run. It always says:

> Not verified against exchange rules (no metadata for this trading pair yet).

Not for a rare symbol, not on a cold start: always, for every symbol, on every run, since the
feature shipped. The branches below that one — the staleness check and the real filter evaluation —
have never executed in production.

No traceback, no log line, nothing red. This is the evidence, taken against the graph
`create_app()` actually builds:

```
$ python -c "... create_app(ConfigManager()); container.resolve(ISymbolMarketMetadataCache)"
RAISED -> DependencyResolutionError Cannot instantiate abstract class
          ...contracts.i_symbol_market_metadata_cache.ISymbolMarketMetadataCache
```

```
$ grep -rn "\.put(" --include=*.py src scripts tests | grep -i metadata_cache
(no output)
```

## 2. Root cause

The feature is a complete set of parts with **two missing wires**, and each part has its own
passing test:

| Part | File | State |
| :--- | :--- | :--- |
| The rich metadata type and its three filters, with `validate_*` | `modules/market_data/contracts/symbol_market_metadata.py` | works, tested |
| `validate_order_intent()` — the actual rule evaluation | same file | works, tested |
| `parse_binance_symbol_metadata()` — the **only** producer | `modules/market_data/adapters/binance/market_metadata_parser.py:57` | works, tested, **called by nothing in `src/` or `scripts/`** |
| `ISymbolMarketMetadataCache` — the port | `modules/market_data/contracts/i_symbol_market_metadata_cache.py` | **bound by nobody** |
| `InMemorySymbolMarketMetadataCache` — the adapter | `modules/market_data/adapters/persistence/symbol_market_metadata_cache.py` | works, tested; constructed only by the fallback below |
| The consumer | `presentation/ui/screens/backtest/coordinators/strategy_config_coordinator.py:237` | runs on every config change, always down the `None` branch |

So nothing ever fetches metadata, and nothing ever stores it.

The second wire is hidden by a fallback that is not a fallback
(`presentation/ui/screens/backtest/backtest_presenter.py:405-413`):

```python
try:
    resolved_cache = container.resolve(ISymbolMarketMetadataCache)
    self._market_metadata_cache: ISymbolMarketMetadataCache = (
        resolved_cache
        if isinstance(resolved_cache, ISymbolMarketMetadataCache)
        else InMemorySymbolMarketMetadataCache()
    )
except Exception:  # noqa: BLE001
    self._market_metadata_cache = InMemorySymbolMarketMetadataCache()
```

Because the port is unbound, `resolve()` raises every time: the `except` branch is the **only**
path, the `isinstance` line is unreachable, and the screen gets a fresh empty cache that nothing
will ever write to. A reader sees defensive code and assumes the normal path works.

`trading` has the same idea wired correctly — `IFuturesSymbolMetadataCache` is bound
(`binance_bot_module.py:321`) and written by `FuturesMetadataProvider`, which is why order
rounding on the live path works. The `market_data` twin is the one that was never connected.

**Why it is cheap to fix:** `PythonBinanceClient.get_available_symbols()`
(`adapters/binance/client.py:330`) already fetches the whole `exchangeInfo` payload and discards
everything except the symbol names. The same entries carry every filter the verification needs,
and the parser that reads them sits in the same package. The fetch is already paid for.

## 3. Positive proof the fix runs

`bug-fix-rule.md` §3: absence of the old symptom is weak evidence, so this is the new mechanism
firing through the real logging config, with the branch that had never executed in production
producing a real answer either way.

```
--- BEFORE the warm: what the screen showed since BOT-095E1 ---
  status='UNVERIFIED_MISSING'  -> Not verified against exchange rules (no metadata for this trading pair yet).

--- the warm (the line the sync worker now runs) ---
2026-09-16 13:03:57,530 - App.SymbolMetadata - INFO - Symbol metadata refreshed: 2 symbols cached.

--- AFTER the warm: the branch that had never executed ---
  status='VERIFIED'  is_valid=True  issues=()
  -> Verified against Binance exchange rules (Min notional: 5.0 USDT, Step: 1e-05, Tick: 0.01).

--- and it really evaluates: a value below min notional is now refused ---
  status='VERIFIED'  is_valid=False
  -> Does not meet the exchange's order rules: Order value 0.50 is below the exchange's minimum
     required value (5.00).
```

The last block is the one that matters: the feature does not merely stop saying "not verified", it
now *disagrees* when the numbers do not satisfy the exchange. The log line is at `INFO` under
`App.SymbolMetadata` — once per refresh, never per symbol, because a catalog is ~2,500 entries and
`SignalLogHandler` mirrors every `App.*` INFO record to the UI's queued log model (`BUG-042`,
`ONBOARDING` §8 trap 9).

## 4. Why nothing caught it

Worth its own screen, because five checks were green over it and one of them is the epic's own:

| Net | Why it was silent |
| :--- | :--- |
| The parser's unit test | constructs its own payload and asserts the parse — a producer's test cannot notice it has no callers |
| The adapter's unit test | constructs its own cache and asserts `put`/`get` — same shape |
| The coordinator's tests | inject `get_market_metadata` directly, so they exercise both branches and prove the logic; none asks who fills the cache in production |
| `mypy` | `container.resolve()` returns `Any`, and `src/presentation/` is excluded wholesale (`EPIC-002A` §2) — the same two conditions as `CS-001` |
| `ruff` | sees an unused *import*, never a function with no callers |
| `test_a_bus_subscriber_is_constructed.py` (`CS-002`'s guard) | scans **bus subscribers**. This is a port with no binding, which is the same disease in a different organ |

That last row is the point: `CS-002` was written for exactly this failure — *"proving a class works,
and calling that proof the program works"* — and installed a guard narrow enough to miss the next
instance.

The measurable version of the rule this needs: **a type that application code `resolve()`s must be
bound somewhere.** Measured across `src/` and `scripts/`, 43 names are resolved and only three are
never bound: `IThreadManager` and `Scheduler`, both registered by the **Engine** rather than by app
code, and `ISymbolMarketMetadataCache` — this bug, alone in its category.

## 5. Fix

Two objects, mirroring `trading`'s working twin rather than inventing a shape (`ONBOARDING` §12.5
principle 5 — the survey found the precedent and extended it):

| Piece | What it does | Why not merged into one |
| :--- | :--- | :--- |
| `ISymbolMarketMetadataCache` — **now bound** (`composition/adapter_bindings.py`) | the store, read on the Qt main thread | a cache read must never be able to make a network call — that is `BUG-045`/`BUG-107`'s rule |
| `ISymbolMetadataProvider` — **new published port** (`composition/port_bindings.py`) | `get_or_fetch()` / `refresh()`, cache-first, may leave the process | fetching is the half that needs a worker thread |

`IExchangeClient` gained `get_symbol_metadata()`, and that is the cheap part: its
`get_available_symbols()` **already** fetched the whole `exchangeInfo` payload and dropped every
filter one line later. Both now read one private `_exchange_info_entries()`, so the two derived
facts cannot drift, and the fix costs **no new request weight**. All four implementers were updated
together — the real client, the two `scripts/` shutdown probes and the contract test's own subclass
— which is `ONBOARDING` §8 trap 11, and the test double caught itself.

**Where the fetch happens, and why there.** `DataSyncCoordinator.run_sync()` — the Backtest screen's
existing background worker — calls `get_or_fetch(config.symbol)` after a successful sync. That
worker is already off the main thread and already about the symbol the user is about to backtest, so
no new thread, no new action identity, nothing for `async-ui-action-rule.md` to govern. The
main-thread check then reads the cache with a plain `get()`, which is a dictionary lookup.

A metadata failure there is logged at `WARNING` and swallowed, deliberately and narrowly: the sync
has already succeeded, the candles are on disk, and the only cost is the honest *"not verified yet"*
the screen already shows. Turning a cosmetic gap into a failed sync would be a worse lie than the
one this bug was.

**The presenter lost its pseudo-fallback entirely** — no `try`, no `isinstance`, no constructed
adapter. A missing binding must fail loudly at construction instead of degrading into a permanently
negative answer, because that silence *is* the defect. Boundary allowlist **36 → 35**: the entry for
`backtest_presenter -> modules.market_data.adapters.persistence.symbol_market_metadata_cache` is
retired, which also closes `EPIC-025D` item 2. It is the third way an entry has ever left that file
— by a **fix**, after 2.1b's (the file moved) and 0.5's (a consumer went onto a port).

## 6. What was considered and rejected

- **Deleting the verification instead.** `EPIC-025` precedent supported it — PR 3.1a deleted a whole
  unwired use case the same day — but it would have thrown away working, tested filter logic for a
  check the user wants. Put to the user on 2026-09-16; they chose the fix.
- **Widening `get_available_symbols()` to return the metadata.** Rejected: every name-reader (the
  symbol picker, Data Management's auto-discover) would then carry a payload it never looks at.
- **Teaching the cache to fetch on a miss.** One object instead of two, and it would put a network
  call behind a `get()` that promises "if present" — the surprise `BUG-045` and `BUG-107` are about.
- **Fetching where the check runs.** `refresh_market_rule_verification()` is called on every capital
  keystroke on the Qt main thread. A fetch there is an HTTP round trip on the UI thread.
- **Fetching at boot, or inside `SymbolCatalogService`.** Boot would cost every session a request
  for a screen most users never open (`market_data.boot()`'s own docstring makes that promise), and
  the catalog service only reaches the exchange when its stored list is empty or refreshed by hand —
  so a user with a cached symbol list would never get filters at all.

## 7. Regression test

`tests/unit/shell/test_market_metadata_wiring.py` — four tests against the graph
`create_app(ConfigManager())` really builds, which is the only tier that could have failed: every
existing test in this area passed by injecting the collaborator production never supplied
(`CS-003`). **Confirmed red before the fix**, with exactly the defect as the reason:

```
E   sagittarius_engine.exceptions.DependencyResolutionError: Cannot instantiate abstract class
    <class '...contracts.i_symbol_market_metadata_cache.ISymbolMarketMetadataCache'>
4 failed
```

and green after. Beyond the resolve, it pins the two things that would re-break it silently: the
cache must be **one instance** app-wide (a per-caller cache is the defect wearing a binding — the
sync warms it on a worker and the screen reads it on the main thread), and resolving the provider
must leave `IExchangeClient` **unbuilt**, asked of the container's own instantiation record rather
than inferred.

Three more, at the tier that owns the wire —
`tests/unit/presentation/ui/screens/backtest/coordinators/test_data_sync_coordinator.py`: a
successful sync warms the symbol's filters; a metadata failure does **not** turn into a failed sync;
a failed sync never reaches the warm. Probed by deleting
`self._warm_symbol_metadata(config.symbol)` from `run_sync`, which fails exactly the first of them.

And the port's own contract suite,
`tests/unit/modules/market_data/contracts/test_symbol_metadata_provider_contract.py`, run against
**both** implementations (HLD §10.3 rule 1): a known symbol comes back as itself, an unknown one is
`None` and never a placeholder, the second read costs no round trip, a **stale** entry is refetched
(`BUG-098`, where the futures twin shipped `is_stale()` and never called it), and `refresh()` reports
its count rather than raising on an empty catalog.
