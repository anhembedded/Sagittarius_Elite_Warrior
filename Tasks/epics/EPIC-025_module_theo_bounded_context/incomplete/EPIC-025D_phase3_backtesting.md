# EPIC-025D — Phase 3: `modules/backtesting`

- **Status:** 🟡 In progress since 2026-09-16 — **items 2 and 4 done**. Item 4 is PR 3.1a: the three
  dead use cases are gone, and re-measuring them first is what turned a cleanup into a finding (§3).
  Item 2 fell out of **`BUG-127`**, the live defect §3.4 found underneath it: the presenter's import
  of `market_data`'s adapter existed only to serve a path that binding the port removed, so fixing
  the bug retired the allowlist entry (36 → 35) and the layering item together. Items 1 and 3 — the
  12,309-line move and the Anticorruption Layer — are open, and item 1 is the whole weight of this
  phase.
- **Repository:** Elite
- **Blocked by:** C · **Blocks:** E
- **Read first:** HLD §3.4; ADR D12. This is the **largest phase by line count** (the backtest
  screen is 12,309 lines in 74 files) but the **least entangled**: it depends only on
  `market_data.contracts` and `strategy.contracts`.

## 1. What to do

1. `modules/backtesting/`: `domain/backtesting` (`PaperExchange`, `_OpenPosition` — **not** merged
   with `LivePosition`, HLD §1 C3), `use_cases/backtest`, the backtest mode — its eleven QML modals
   rebuilt as `QDialog`s and its panels as docks (HLD §11).
2. ✅ **done by `BUG-127`'s fix** — fix the existing layer violation at `backtest_presenter.py:43`
   (an import of `infrastructure/persistence`) by going through `market_data.contracts`. The stated
   coordinates were stale (§3.3) and the real violation was the presenter naming `market_data`'s
   *adapter*; it is gone, and the allowlist entry with it (**36 → 35**). It came out of a bug fix
   rather than a move, because the import only existed to serve a path that a proper binding
   removed — see §3.4.
3. Build the Anticorruption Layer: `backtesting/adapters/` translates `PaperExchange` state into
   `strategy.contracts.StrategyContext`. (Round-3 correction: `strategy_context.py` does **not**
   import backtesting today; the wrong-direction import is `trading → backtesting` and is handled
   under ADR O4 before Phase 1.) `backtesting` sizes paper fills through `strategy.contracts.ISizingPolicy` (ADR D17), so backtest and live sizes are one number by construction.
4. ✅ **PR 3.1a** — delete the dead use cases `RunBacktestCommand`, `StopBacktestCommand` and
   `BacktestState` (bound in the composition root, dispatched by nobody). Done, with the
   measurement and the hazard in §3. The clause's second half — *"fill and marker overlays go
   through `IChartHost`"* — is a separate, unrelated sentence about the chart and is **not** done;
   it travels with item 1, the screen's move.

## 2. Done when

- A backtest runs end to end with **bit-identical** results on the same data (the trade log before
  and after is compared — this is a pure refactoring).

---

## 3. PR 3.1a — the deletion, and what re-measuring it turned up

### 3.1 The claim held, and it was worth checking anyway

Item 4 said the three were "bound in the composition root, dispatched by nobody". Measured rather
than trusted, because Phase 2 twice found a note of exactly that shape wrong (`declare_cli()` in PR
2.1g, `claim_symbol`'s "no caller at all" in PR 2.1f). This time the note was right:

| Name | References outside its own four files | Dispatched? |
| :--- | :--- | :--- |
| `RunBacktestCommand` + `RunBacktestCommandHandler` | `binance_bot_module.py:475` (`bind`) | no |
| `StopBacktestCommand` + `StopBacktestCommandHandler` | `binance_bot_module.py:476` (`bind`) | no |
| `BacktestState` | `binance_bot_module.py:433` (`singleton`) | — read only by the two dead handlers |

The two commands the Backtest screen actually dispatches are `RunStaticBacktestCommand` and
`RunHistoricalTickBacktestCommand`, both from `execution_coordinator.py`.

### 3.2 The finding: the loop could have placed a real order from historical data

`RunBacktestCommandHandler._run_simulation_loop()` republished each stored candle as a
`MarketTickEvent` through `IEventPublisher`, which `binance_bot_module.py:420` binds to
`EngineEventPublisher(app.event_bus)` — the **real** bus, not a private one. Since PR 2.1c-2 that
event is `StrategyModule`'s own subscription, so the chain a single dispatch would have run is:

```
dispatch(RunBacktestCommand)
  -> stored candles
  -> emit MarketTickEvent on the app bus
  -> MarketTickEventHandler            (strategy's, subscribed by StrategyModule.boot())
  -> LiveStrategySession.dispatch_tick()
  -> StrategyEngine.on_tick()
  -> LiveTradingCoordinator.handle(signal)
  -> trading's IOrderSubmission.submit()
```

Only the three safety gates and the armed state stood between that and a live order — never "this
candle came from a backtest", which is the distinction `MarketTickEventHandler`'s own docstring says
the design relies on *not* needing, because no backtest code path was supposed to reach it. One did;
nobody had called it. The deletion removes the path rather than documenting it, which is why this
item is worth being Phase 3's first step instead of travelling with the 12,309-line move.

### 3.2 bis Assertion inventory of the four deleted tests

**Subject deleted; behaviour exists nowhere else.** That is HLD §9.3's category-3 sentence, verbatim,
because that section tells the reviewer to check for it rather than to re-derive it — and it is true
of all four: each asserted the replay loop itself, and the loop is gone. The one line of it that
reads like a general rule, *"an empty repository must publish nothing"*, is not an exception but an
improvement, as the table's last column says.

Two files, four tests:

| Deleted test | Asserted | Where that guarantee lives now |
| :--- | :--- | :--- |
| `test_run_backtest_handler_emits_events` | one `MarketTickEvent` per candle, with the candle's fields | nowhere, by design — this is the behaviour being removed |
| `test_run_backtest_handler_throttling` | `time.sleep(replay_speed_ms/1000)` once per candle | nowhere, same |
| `test_run_backtest_no_data` | an empty repository publishes nothing | **improved**: `test_run_static_backtest.py::test_no_historical_data_emits_failed_event_and_returns_none` asserts a *named failure* instead of an absence |
| `test_stop_backtest_handler` | `BacktestState.is_running` flips `True → False` | nowhere — and the live cancel path is a different mechanism entirely: a `CancellationCheck` callable on the command plus `BacktestCancelled` as an explicit outcome, covered in `test_run_static_backtest.py` and `test_run_historical_tick_backtest.py` |

### 3.3 Item 2's stated location is stale, and the violation moved rather than vanished

Item 2 reads *"fix the existing layer violation at `backtest_presenter.py:43` (an import of
`infrastructure/persistence`)"*. That import is **gone** — `grep -rn infrastructure
src/presentation/ui/screens/backtest/` returns nothing. What is there instead, and what the
boundary allowlist still carries as one line, is

```
presentation.ui.screens.backtest.backtest_presenter -> modules.market_data.adapters.persistence.symbol_market_metadata_cache
```

— the presenter reaching past `contracts/` for `InMemorySymbolMarketMetadataCache`, the module's own
adapter. So item 2 is still real and still worth its own pull request; only its coordinates changed,
and this section is the correction.

### 3.4 …and item 2 sits on top of a live defect, filed as `BUG-127`

Reading that import's purpose found something else. The presenter does:

```python
try:
    resolved_cache = container.resolve(ISymbolMarketMetadataCache)
    self._market_metadata_cache = (
        resolved_cache if isinstance(resolved_cache, ISymbolMarketMetadataCache)
        else InMemorySymbolMarketMetadataCache()
    )
except Exception:
    self._market_metadata_cache = InMemorySymbolMarketMetadataCache()
```

Two measurements, both made against the real graph rather than by reading:

- **`ISymbolMarketMetadataCache` is bound nowhere.** `create_app(ConfigManager())` then
  `container.resolve(ISymbolMarketMetadataCache)` raises `DependencyResolutionError: Cannot
  instantiate abstract class`. So the `except` branch is not a fallback, it is the only path, and
  the `isinstance` line is unreachable.
- **Nothing ever calls `put()`.** No `.put(` on that port anywhere in `src/`, `scripts/` or
  `tests/`, so the cache the presenter builds stays empty for the life of the screen.

Consequence, user-visible: `StrategyConfigCoordinator.refresh_market_rule_verification()` reads
`get(symbol)`, gets `None` every time, and takes its first branch — *"Not verified against exchange
rules (no metadata for this trading pair yet)"* — permanently. The stale check, the reference-price
calculation and the actual filter evaluation below it are unreachable in production. `BOT-095E1`
built that verification; it has never verified anything.

Filed as `BUG-127` and **fixed** on the user's decision of 2026-09-16, in its own commit rather than
folded in here: fixing it is a **behaviour change** (the screen starts really checking, and may now
refuse a capital/symbol combination it used to pass over in silence), and `bug-fix-rule.md` wants
the report and a regression test written first. Item 2 fell out of it exactly as predicted — a bound
port is what removed the presenter's reason to name the adapter at all.

What shipped, in one line each: `ISymbolMetadataProvider` is a new published port with a verified
fake and a contract suite both implementations run; the cache is bound; `IExchangeClient` gained
`get_symbol_metadata()` to expose the half of `exchangeInfo` that `get_available_symbols()` already
fetched and threw away, so there is **no new request weight**; and the fetch happens on
`DataSyncCoordinator`'s existing background worker, because the check itself runs on the Qt main
thread on every capital keystroke. The presenter's `try`/`isinstance`/`except` is gone entirely: a
missing binding must fail loudly at construction, since that silence was the defect. The full
account, including positive log evidence that the previously-unreachable branch now really refuses a
sub-minimum order value, is in
[`BUG-127`](../../bug_report/completed/BUG-127_backtest_market_rule_verification_never_verifies.md)
and [`CS-003`](../../../Docs/CASE_STUDIES/CS-003_the_port_nobody_bound.md).

`trading`'s parallel `IFuturesSymbolMetadataCache` is bound *and* written (by
`FuturesMetadataProvider`), which is why the live order path's rounding works — the twin in
`market_data` is the one that was never wired.

### 3.5 The gate

**PASS** on the first run: `logs/ci-local-20260916-122553.log`, **4896 passed / 4 skipped**,
grepped — 4 hits, all the known benign set, **0** records at WARNING or above; mypy clean on
**470** files.

Tests **4906 → 4896**, and the −10 accounts exactly: the 4 deleted tests, plus **6**
parametrisations of `test_logging_namespace_guard.py`, which is parametrised per source file and
lost one for each of the six files deleted. mypy **476 → 470** for the same six. The boundary
allowlist is **unchanged at 36** — the deleted files held no allowlisted import, which is itself
worth noting: this deletion bought no boundary debt back, it only removed code.

### 3.6 What the review of this pull request found

Two compliance gaps in its own documents, both cheap and both about a rule that names a *form*
rather than a fact:

- **HLD §9.3's category 3 requires the sentence "subject deleted; behaviour exists nowhere else" in
  the task file, and tells the reviewer to check for that sentence.** §3.2 bis carried the same
  content as a table with a "where that guarantee lives now" column — richer, and unusable for the
  check the rule actually specifies. The sentence is now there, verbatim, above the table.
- **`Docs/HLD/09`'s row said PR 3.1a "took the first three"** of a list of five, which is a count in
  prose whose unit — tests, files or subjects — the sentence never states, exactly what
  `.agents/Skills/README.md` §1 bans. It now reads **2 files / 4 tests**, and names the thing the row
  had never listed: `StopBacktestCommand`, deleted here although that row only mentioned
  `RunBacktestCommand` and `BacktestState`.

Also re-verified rather than assumed, because a deletion's characteristic failure is an import that
stops resolving and is invisible to lint, mypy and the tests (`epic-025.prompt.md` §3 step 7, which
records three such defects in PRs 1.6d–1.6f): `create_app(ConfigManager())` builds the whole object
graph and returns with 10 extensions registered. The boundary allowlist is **unchanged at 36** and no
baseline file was touched — this pull request removed code and bought back no debt.
