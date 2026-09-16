# EPIC-025D — Phase 3: `modules/backtesting`

- **Status:** 🟡 In progress since 2026-09-16 — **items 2 and 4 done**. Item 4 is PR 3.1a: the three
  dead use cases are gone, and re-measuring them first is what turned a cleanup into a finding (§3).
  Item 2 fell out of **`BUG-127`**, the live defect §3.4 found underneath it: the presenter's import
  of `market_data`'s adapter existed only to serve a path that binding the port removed, so fixing
  the bug retired the allowlist entry (36 → 35) and the layering item together. Items 1 and 3 — the
  12,309-line move and the Anticorruption Layer — are open, and **§4 is the measurement that says
  how item 1 splits**: the screen's 74 files carry 29 imports of QML packages ADR D21 *deletes* in
  Phase 4, so they travel with those deletions the way Phase 1's two screens did (the user's
  `DECISION_2026-09-16`). What is left for this phase is the domain-and-use-case half — 26 files /
  2,538 lines, six blocking imports, all of them what `IStrategyEngineFactory` was reserved for.
- **Repository:** Elite
- **Blocked by:** C · **Blocks:** E
- **Read first:** HLD §3.4; ADR D12, and **§4 before touching any code** — it is the measured cut,
  and it corrects two things this line said. The header's "12,309 lines in 74 files" is the
  **screen alone** (74 / 12,400 today); the context is 95 files / 14,786 lines. And "it depends only
  on `market_data.contracts` and `strategy.contracts`" is false as stated: measured, the moving code
  makes 13 imports into `modules/strategy`'s **non-contracts** packages and 33 into
  `presentation/ui`, 29 of them QML. It is still the least entangled phase — just not that
  entangled-free.

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

---

## 4. The cut, measured 2026-09-16 before any code moved

`ls`-and-`grep` are not a measurement; these numbers come from walking the AST of every file under
`src/` and `scripts/`. The header's own figure — *"the backtest screen is 12,309 lines in 74
files"* — turns out to be **the screen alone**, and it is very nearly right (74 files / 12,400
lines today). The context as a whole is larger:

| What §1 assigns to this phase | Files | Lines |
| :--- | ---: | ---: |
| `src/domain/backtesting` | 12 | 1,360 |
| `src/application/use_cases/backtest` | 9 | 1,026 |
| `src/presentation/ui/screens/backtest` | 74 | 12,400 |
| **total** | **95** | **14,786** |

### 4.1 The finding: this phase splits in two, and the halves are not the same kind of work

The 185 imports the moving code makes to things that are **not** moving separate cleanly, and the
line between them is QML:

| What it reaches for | Imports | Verdict |
| :--- | ---: | :--- |
| `core.vo`, `core.contracts`, `modules.*.contracts`, `support.*` | 105 | already permitted — nothing to unblock |
| `presentation.ui.qml.*` | **29** | **ADR D21 deletes these in Phase 4 rather than moving them** |
| `presentation.ui.common.*` (4 helpers) | 4 | Phase 4's `support/` extraction |
| `domain.value_objects.{commission_type,broker_simulation_config,currency}`, `domain.events.backtest_{completed,failed}_event` | 24 | backtesting's own vocabulary — moves with it, the 2.1b shape |
| `modules.strategy.{application,ui,domain}` | 13 | the hard refusal: module → another module's non-`contracts/` |
| `config.config_keys` | 3 | Phase 5's |

**Twenty-nine of the thirty-three `presentation.ui` imports are QML packages ADR D21 deletes.** That
is the same wall Phase 1 hit, and the user already ruled on it:
[`DECISION_2026-09-16`](../DECISION_2026-09-16_the_duplication_criterion_waits.md) kept the
shrink-only allowlist clean and let Trading and Dev Board **travel with the QML deletions in Phase
4** rather than spend the epic's one invariant to hit a number early. The backtest screen is the
third screen in that position, for the same reason, so it travels the same way. Phase 3's *code* is
therefore the other half, and it is a clean one:

| Half | Files | Lines | Blocking imports |
| :--- | ---: | ---: | :--- |
| **A — domain + use cases** (`domain/backtesting`, `use_cases/backtest`, and the five legacy value objects/events above) | 26 | 2,538 | **6**, all `modules.strategy.application`/`.domain` |
| **B — the screen** | 74 | 12,400 | 29 QML imports to packages Phase 4 deletes |

### 4.2 Half A's six blockers are what `IStrategyEngineFactory` was reserved for

`EPIC-025C` §1 item 2 says that port is published *for* `backtesting`, and this is the measurement
that says which shape it needs. The two backtest handlers reach into `strategy` for three things —
`StrategyRegistry`, `build_engine()` and the `StrategyEngine` type — and `paper_exchange.py` reads
`MarginSizingPolicy`, which is already on the allowlist with **this phase** named as its exit
(PR 2.1d's line).

**The engine has to be published as an interface, not as a class**, and PR 2.1c is why: that pull
request built `IStrategyCatalog` and then deleted it, because *a published contract must not carry
`BaseStrategy`*. `StrategyEngine` is the same kind of type. So the surface is `IStrategyEngine`
(what a backtest *drives*) behind `IStrategyEngineFactory` (what builds one from a key and
parameters).

And the surface is **two methods, not three** — measured, the way PR 1.2 measured `quote_asset` out
of `ISymbolCatalog`:

| `StrategyEngine` method | Called from outside `modules/strategy/` in `src/`? |
| :--- | :--- |
| `on_tick()` | yes — both backtest handlers |
| `on_forming_bar_tick()` | yes — the historical-tick handler |
| `run_batch()` | **no.** Only `strategy`'s own tests and `scripts/benchmark.py`. It stays intra-module |

### 4.3 The remaining pull requests

| PR | What | Allowlist |
| :--- | :--- | :--- |
| ~~3.1a~~ ✅ | delete the three dead use cases; see §3 | unchanged (36) |
| ~~item 2~~ ✅ | the presenter's adapter import, fixed as `BUG-127`; see §3.4 | **36 → 35** |
| 3.1b | publish `IStrategyEngine` + `IStrategyEngineFactory` with a verified fake and a contract suite, and move the two backtest handlers plus `paper_exchange` onto them. No files move yet — the 0.5 shape, a port with its consumers | shrinks by the 6 strategy-service lines |
| 3.1c | move **Half A** (26 files / 2,538 lines) into `modules/backtesting/`, with its tests, tier unchanged. The 2.1b shape: the screen's ~15 reads of it become counted `legacy → modules.backtesting` entries, each naming Phase 4 as its exit | grows, every line named |
| 3.1d | item 3's Anticorruption Layer — `backtesting/adapters/` translating `PaperExchange` state into `strategy.contracts.StrategyContext`. Travels with 3.1c, because the translation only has a home once the module exists | unchanged |
| → Phase 4 | **Half B, the screen.** Its eleven QML modals become `QDialog`s and its panels docks *as they move*, because ADR D21 deletes the QML rather than porting it — one piece of work, not two | shrinks |

### 4.4 What this means for the phase's own done-when

§2 asks for a backtest that runs **bit-identical** on the same data. That is testable for 3.1b and
3.1c (both are refactorings under ADR D12, and the trade log is the comparison), and it stays the
criterion. What changes is only the scope of "this phase": Half B is not abandoned, it is scheduled
where its blocker is resolved, exactly as Phase 1's two screens were. Phase 3 closes when Half A is
moved and the trade log is unchanged; the screen closes in Phase 4 with the QML it depends on.

---

## 5. PR 3.1b — two ports, and the six imports they retire

`EPIC-025C` §1 item 2 reserved `IStrategyEngineFactory` *"for `backtesting` in Phase 3"*, and §4.2
is the measurement that said what shape it needed. This is that pull request. **No file moved** —
the PR 0.5 shape: a port, and its consumers put onto it.

### 5.1 The engine is published as an interface, for PR 2.1c's reason

`StrategyEngine` holds an `IStrategy`, a dict of `IIndicator`s and an `IEventPublisher` — three of
`strategy`'s internals. A consumer naming the class would import all of them by reference, which is
why PR 2.1c built `IStrategyCatalog`, measured it, and deleted it: *a published contract must not
carry `BaseStrategy`*. So `IStrategyEngine` is the port and `StrategyEngine` now **declares** it,
which makes a signature change a type error at every consumer rather than an `AttributeError` at
runtime.

**Two methods, not three.** `run_batch()` has no caller outside `modules/strategy/` anywhere in
`src/` — only that module's own tests and `scripts/benchmark.py` — so publishing it would promise
something nobody has asked anyone to keep. That is PR 1.2's `quote_asset` reasoning applied a fourth
time.

The contract suite pins the one promise a consumer cannot see and must not flatten: `on_tick()`
**commits** indicator state, `on_forming_bar_tick()` **peeks** (`BOT-042D`). Two engines from one
factory see the same closed candles; one is asked about a forming bar three times first; their
decisions must match. A consumer that conflated the two would run a Realtime backtest whose
indicators had been advanced by bars that never closed, and nothing at its own tier could tell.
Both implementations run that suite — the fake, and the real factory over the real `StrategyRegistry`
with a recording publisher, so the asymmetry is exercised against **real** indicator state.

### 5.2 `ISizingPolicy` got its binding, and this file's own prediction came true

`modules/strategy/composition/port_bindings.py` said: *"a binding nothing resolves is dead wiring,
which is what `BUG-120` was — so it arrives in Phase 3 with the consumer that resolves it."* It did.
The two backtest handlers now resolve the port and pass it to `PaperExchange` explicitly, so the
binding is live and the second implementation ADR D17 promises the user reaches a real backtest with
no change to the paper broker.

`PaperExchange`'s **default** stays, and only its source changed. It was `MarginSizingPolicy()`
imported from `strategy/domain/policies/` — a paper broker in another bounded context reaching past
that module's `contracts/`, and the one allowlist line ADR D17 scheduled for this phase. It is now
`contracts/default_sizing_policy()`, which returns that same one implementation. Removing the default
instead would have been fifty-five edits in `test_paper_exchange.py`, every one passing the same
object — `ONBOARDING` §8 trap 5's shape — and it would not have bought anything, because what ADR
D17 actually requires is that backtest and live sizing be *one number by construction*, not that the
number arrive by injection.

### 5.3 What it cost, and the net the cost was caught by

Nine handler construction sites in five test files and **two in `scripts/`**. The `scripts/` pair is
worth naming: `ruff` was clean and every test passed, and **`mypy` is what failed the gate** —
`ONBOARDING` §8 trap 11's own words are *"missing `scripts/` is exactly what went wrong while fixing
`BUG-025`"*, and the gate running `src`+`scripts` in one command is the net that caught it here.

Every rewritten site builds `StrategyEngineFactory` from the same real registry and publisher it
already had, and passes `default_sizing_policy()` — the exact object the constructor defaulted to.
That is deliberate and it is what makes the evidence worth anything: these include the
hand-verified-trade tests and the **golden** runner, and they pass **unchanged**, which is §2's
bit-identical criterion holding across the refactor.

### 5.4 The gate

Boundary allowlist **35 → 29**: six lines retired, none added. Five were consumers holding another
context's internals (`StrategyRegistry`, `build_engine`, `StrategyEngine`); the sixth is
`paper_exchange`'s. The three `presentation.ui.screens.* -> strategy_registry` lines are **not**
among them and are a different debt — Presenters handing the registry to coordinators that construct
a strategy for its chart lines, which PR 2.1c measured and which needs the screens to move (Phase 4).
