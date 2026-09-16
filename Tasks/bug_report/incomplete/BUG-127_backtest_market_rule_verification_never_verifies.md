# BUG-127 — the Backtest screen's exchange-rule check has never checked anything

- **Reported:** 2026-09-16 (found while measuring `EPIC-025D` item 2, not by a user)
- **Severity:** 🟠 P2 — no wrong number is shown and no money is at risk; a shipped feature simply
  does nothing, and its failure mode is a message that looks like a normal "not yet" state
- **Status:** Open. Root-caused and reproduced by measurement against the real object graph; the
  fix is not written, because it needs a decision recorded in *Suggested next steps*.

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

## 3. Why nothing caught it

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

## 4. Fix

Not written yet. See below.

## 5. Suggested next steps

1. **Install the check first**, since it is independent of the fix's shape and closes the blind
   spot rather than this one instance: a guard that every `resolve()`d type is bound, exempting the
   two Engine-registered services by name. It fails on this bug today, so it lands with a one-entry
   ratchet naming `BUG-127` as its exit.
2. **Then the mechanism.** The clean shape mirrors `trading`'s working twin: a `market_data`
   adapter that fetches `exchangeInfo` **lazily and once**, parses every entry, fills the cache,
   and is bound in `modules/market_data/composition/port_bindings.py`. The Backtest presenter then
   resolves the port and loses both the adapter import and the pseudo-fallback — which also retires
   the boundary-allowlist line
   `presentation.ui.screens.backtest.backtest_presenter -> modules.market_data.adapters.persistence.symbol_market_metadata_cache`
   and settles `EPIC-025D` item 2.
3. **The open decision, which is why this is filed rather than fixed:** reaching the metadata needs
   a way to read the raw `exchangeInfo` entries, and `IExchangeClient.get_available_symbols()`
   deliberately returns `list[str]`. Adding a method to that port means updating its three real
   implementers (`PythonBinanceClient` and the two `scripts/` shutdown probes) plus its contract
   suite — `ONBOARDING` §8 trap 11's exact shape, bounded but not a two-line change. The
   alternative is deleting the verification feature outright, which `EPIC-025` precedent supports
   (PR 3.1a deleted a whole unwired use case the same day) and which throws away working, tested
   validation logic. **That choice is the user's**, and it is a behaviour change either way: fixing
   it means the screen starts really checking and may begin refusing a capital/symbol combination
   it has always waved through in silence.

## 6. Regression test

Not written yet — it belongs with the fix (`bug-fix-rule.md` §4 and §6). The tier is settled,
though: it must construct the **real** object graph and assert the cache is reachable and non-empty
for a known symbol, because every existing test in this area passes by injecting the collaborator
that production never supplies. A unit test of the coordinator cannot reproduce this.
