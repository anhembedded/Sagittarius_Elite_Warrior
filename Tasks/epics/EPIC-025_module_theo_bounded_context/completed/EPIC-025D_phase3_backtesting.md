# EPIC-025D — Phase 3: `modules/backtesting`

- **Status:** ✅ Done (2026-09-19). All four items done — item 4's second half (fill/marker overlays)
  re-checked against real code and closed with a finding, not assumed; see its own entry below and
  §9. Item 4 is PR 3.1a: the three dead use cases are gone, and re-measuring them first is what
  turned a cleanup into a finding (§3). Item 2 fell out of **`BUG-127`**, the live defect §3.4 found
  underneath it: the presenter's import of `market_data`'s adapter existed only to serve a path that
  binding the port removed, so fixing the bug retired the allowlist entry (36 → 35) and the layering
  item together. Item 1's Half A shipped here (§6, §7) and Half B — the screen — shipped in Phase 4
  as PR 4.4d (`screens/backtest`, 79 files, into `modules/backtesting/ui/`), exactly where §4's
  measurement said it belonged; item 3 is **measured out** (§8, decided unnecessary rather than
  built, the same call PR 2.1c made for `IStrategyCatalog`). §4 is the measurement that said how
  item 1 splits: the screen's 74 files carry 29 imports of QML packages ADR D21 *deletes* in Phase
  4, so they travelled with those deletions the way Phase 1's two screens did (the user's
  `DECISION_2026-09-16`). §2's bit-identical criterion re-verified 2026-09-19: the golden-master and
  hand-verified-trade tests this phase's own PRs (3.1b, 3.1c) ran against are part of the green full
  `tests/unit`/`tests/integration` runs `TRACKING.md`'s `p4-4.4f5` row already recorded, and nothing
  in Phase 4 touched `modules/backtesting`'s domain/application layers.
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

1. ✅ **Half A done — PR 3.1c** (§6). `modules/backtesting/`: `domain/backtesting`
   (`PaperExchange`, `_OpenPosition` — **not** merged with `LivePosition`, HLD §1 C3) and
   `use_cases/backtest` are in, as `contracts/` (11 files), `domain/` (6) and `application/` (8).
   **Half B — the backtest mode, its eleven QML modals rebuilt as `QDialog`s and its panels as
   docks (HLD §11) — is Phase 4's**, measured rather than deferred for room: §4.1 counted 74 files
   whose 29 QML imports name packages ADR D21 **deletes** rather than moves. **Half B ✅ shipped as
   `EPIC-025E` PR 4.4d** (2026-09-18, `screens/backtest` + `base_event_logger.py` into
   `modules/backtesting/ui/`, flat) — confirmed 2026-09-19 by reading that phase's own `TRACKING.md`
   row (`p4-4.4d`) and `git log`, not re-narrated from this line.
2. ✅ **done by `BUG-127`'s fix** — fix the existing layer violation at `backtest_presenter.py:43`
   (an import of `infrastructure/persistence`) by going through `market_data.contracts`. The stated
   coordinates were stale (§3.3) and the real violation was the presenter naming `market_data`'s
   *adapter*; it is gone, and the allowlist entry with it (**36 → 35**). It came out of a bug fix
   rather than a move, because the import only existed to serve a path that a proper binding
   removed — see §3.4.
3. ✅ **Satisfied, and the layer is not built — §8.** The item asked for
   `backtesting/adapters/` translating `PaperExchange` state into
   `strategy.contracts.StrategyContext`. Measured: nothing outside `modules/strategy` constructs a
   `StrategyContext` — `StrategyEngine` builds it, from a candle and a `PositionSide | None` — so
   `backtesting` hands the engine **one fact** about its own state, `exchange.current_side`, through
   `IStrategyEngine.on_tick()`. **PR 3.1b's port is the translation surface**, and building the
   folder would require *publishing* `StrategyContext`, a type carrying an indicator map with
   `MACDValue` and `SupportResistanceValue` in it — exactly what PR 2.1c refused for
   `IStrategyCatalog`, and it would make the boundary worse rather than better. `backtesting` sizes
   paper fills through `strategy.contracts.ISizingPolicy` (ADR D17), so backtest and live sizes are
   one number by construction.
4. ✅ **PR 3.1a** — delete the dead use cases `RunBacktestCommand`, `StopBacktestCommand` and
   `BacktestState` (bound in the composition root, dispatched by nobody). Done, with the
   measurement and the hazard in §3. **The clause's second half — *"fill and marker overlays go
   through `IChartHost`"* — closed 2026-09-19, and not the way this line originally expected. See
   §9 for the finding: the shared `IChartHost` port never got built, and reading the code shows it
   was never needed.**

## 2. Done when

- A backtest runs end to end with **bit-identical** results on the same data (the trade log before
  and after is compared — this is a pure refactoring).

**Re-verified 2026-09-19, not re-narrated**: §8.3 already recorded the golden-master and
hand-verified per-trade tests passing unchanged through 3.1b/3.1c/3.1c-2; the full `tests/unit`
(4883 passed) and `tests/integration` (161 passed, including the order-submission path) runs this
epic's own `TRACKING.md` `p4-4.4f5` row recorded on 2026-09-19 are the same suites, run after every
later phase's changes, still green — `modules/backtesting`'s domain/application layers were
untouched by anything after PR 3.1c-2. Half B (the screen, `EPIC-025E` PR 4.4d) and item 4's
`IChartHost` question (§9) are the two items this phase's status line had left unclosed; both are
closed above.

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
refuse a capital/symbol combination it used to pass over in silence), and `fix-bug-rule.md` wants
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
  `.claude/ONBOARDING.md` §13 bans. It now reads **2 files / 4 tests**, and names the thing the row
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
| ~~3.1c~~ ✅ | move **Half A** into `modules/backtesting/`, with its tests, tier unchanged. Done — §6. The estimate was 26 files and *~15 counted entries*; it shipped as **26 files / 2,676 lines** and **three** entries, because putting the boundary-crossing types in `contracts/` *with* the move absorbed 30 of the 33 inbound imports | **29 → 32** |
| ~~3.1c-2~~ ✅ | split `paper_exchange.py`, which was **472 lines** against §5 rule 4's 400-line ceiling. §5.5 committed this to 3.1c and it is deliberately a second commit rather than a larger first one: a pure move and a class split are two logical changes (`commit-rule.md` §4), and PR 2.1c/2.1c-2 set that shape in Phase 2. The seam §5.5 named is the file's own: a broker's **books** (cash, positions, trades, the signal → fill dispatch) on top of the **arithmetic against `BrokerSimulationConfig`** that the three policies do. Done — §7, and the file held **three** things rather than two | unchanged |
| ~~3.1d~~ ❌ | item 3's Anticorruption Layer — **measured out, §8.** Not deferred and not descoped: the boundary it was to protect is already clean (`backtesting` reads four `strategy.contracts` modules and nothing else, zero allowlist lines in that direction), and the layer would need `StrategyContext` published, which PR 2.1c's rule forbids. `IStrategyCatalog`'s outcome, a second time | unchanged |
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

### 5.5 What the review of this pull request found

Two findings, both on its own work:

**The `sizing_policy=` wiring was pinned by nothing, and could not be.** Deleting
`sizing_policy=self._sizing_policy` from the static handler left **37** tests green — the fourth
time in five pull requests that the E12 probe has earned its keep. The reason is worth recording,
because it is a different reason from the previous three: the injected object and
`PaperExchange`'s default are the *same implementation*, so no behavioural test can tell them apart.
An "assert it was called" test would have been the obvious answer and a bad one — it pins a call,
not a promise (`domain-truth-rule.md`).

What the injection actually buys is ADR D17's promise that a **second** sizing rule bound in the
container reaches a real backtest, and that *is* observable. `test_the_injected_sizing_policy_is_
what_sizes_the_paper_fills` runs the same candles twice — once with the real rule, once with an
`ISizingPolicy` that delegates to it and halves the result — and asserts the trade quantities
differ. Cut the wire and both runs use the default, the quantities match, and it fails. Re-probed:
exactly that test, and only it.

**`paper_exchange.py` was 468 lines and this pull request made it 480**, against `architecture-rule`
§5 rule 4's 400-line ceiling. The added lines were all comment, which is not an excuse: the file was
already 68 over and the direction was wrong. Trimmed to 470 — the same content, one paragraph
instead of three, with the full account here in §5.2 where it belongs. **The file is still 70 over
the ceiling, and that is PR 3.1c's to fix**, not a comment's: it is the one file in Half A that
genuinely holds two abstraction levels (a broker's books, and the matching/fee/margin policies it
delegates to), and the move is when splitting it costs nothing extra.

---

## 6. PR 3.1c — the move, and a number that came out five times smaller than measured

### 6.1 What moved

26 files, 2,676 lines, into three trees whose names are the whole design decision:

| Tree | What | Why there |
| :--- | :--- | :--- |
| `contracts/` (11 files) | `BacktestResult`, `Trade`, `BacktestMetrics`, `ExitReason`, `BacktestCancelled`, `OutOfSampleValidation`; `BrokerSimulationConfig`, `CommissionType`, `Currency`; `BacktestCompletedEvent` / `BacktestFailedEvent` under `contracts/events/` | every one of them is read from **outside** the context — by the Backtest screen, which does not move until Phase 4 |
| `domain/` (6 files) | `PaperExchange`, `_OpenPosition`, `out_of_sample_split`, and the three fill policies under `domain/policies/` | the paper broker's own rules; nothing outside names them |
| `application/` (8 files) | both runners (`run_static_backtest/`, `run_historical_tick_backtest/`) and `progress_throttle` | the use cases, and they stay internal — see §6.3 |

Plus `module.py`, the one file `shell/` may import, appended to `shell/modules.py` as the **fourth
and last** module: three suppliers (`market_data`, `strategy`, `trading`) and no customer, which is
what made this the least entangled phase and is checked rather than claimed —
`test_module_declarations.py` reads the imports actually present and fails on both surplus and
shortfall.

Two consequences outside the module are worth naming because a reader will go looking for them:
`src/application/` is **empty** and gone from disk, and `src/domain/` holds exactly one file —
`value_objects/market_type.py`, whose only production consumer is
`presentation/ui/components/market_picker/catalogue.py`, so it travels with that component in
Phase 4.

### 6.2 33 inbound imports became 3 allowlist entries

§4 measured 33 imports reaching into the moving code from 17 files, and the pull-request table
above predicted *"~15 counted entries"*. It shipped as **three**, and the reason is not restraint:
almost all 33 read the *answers* a run produces, and those went into `contracts/` **with** the move,
so they became legal imports rather than counted violations. This is PR 1.3b's first half repeated
exactly — it took `trading`'s inbound count 61 → 41 without touching a single consumer — and it is
worth stating as a rule, because the estimate was wrong by 5× in the same direction both times:

> A move that carries its boundary-crossing types into `contracts/` costs almost no allowlist. A
> move that leaves them in `domain/` pays for every consumer, one line at a time.

The three that remain are the one thing `contracts/` cannot absorb: the Backtest screen **builds
this module's commands and dispatches them** through `ICommandDispatcher`. That is the
transitional shape this epic exists to retire, and HLD §3.4 records its exit — *"if a CLI
`backtest` command appears, `IBacktestRunner` is added then"*. It is `IMarketDataSync`'s arc
exactly (PR 0.4a moved the code, PR 0.5 published the port, four callers stopped building the
command), so these three retire with that port, at the latest when the screen moves in Phase 4.

The count moved **29 → 32**, and the allowlist file carries the same argument inline, because the
reviewer's first question about a grown ratchet is *why this many and not more*.

### 6.3 `register()` binds nothing, and that is a measurement rather than an omission

Both command handlers stay registered in `binance_bot_module.py`, the strangler root the boundary
scan skips by name. Moving a *registration* while the dispatcher and the screen both stay put buys
a second place to look for one fact — the accidental complexity ADR D2 exists to avoid — and a
binding nothing resolves differently is the dead wiring `BUG-120` was. `ISizingPolicy` is
**resolved** here rather than bound: `strategy` owns that binding (ADR D17), and this module is the
consumer PR 3.1b's binding was waiting for, which §5.2 predicted in those words.

`contribute()`, `declare_cli()` and `subscribe()` are all absent, and `module.py`'s docstring gives
each one its measurement rather than leaving a reader to assume scope ran out.

### 6.4 The retargeted guard, and the rule it nearly took with it

`test_application_layer_structure.py` scanned `src/application/`, which this pull request emptied.
A path-scanning guard whose subject has left **passes faster rather than failing**, and
`test_scanned_roots_are_not_empty.py` is what caught it — the second time that registry has earned
its row in this epic. The guard was retargeted onto `src/modules/*/application/`, measured before
retargeting (105 files across four modules, zero misnamed CQRS files, zero `I*` classes), and it
gained its own `test_the_guard_has_a_subject`.

The retarget also made one of its rules **stricter** and that is the interesting half. In the legacy
tree the question was *"is this interface under `application/ports/`"*; a module has no `ports/` at
all, because its abstractions are its `contracts/` (HLD §3.2). So the rule is now *no `I*` class
under `application/`, full stop*.

Which left a third rule with no subject anywhere: *a file declaring an interface is named
`i_*.py`*, checked only under `application/ports/`. Dropping it with the directory would have been
the quiet half of a retarget — **a rule that stopped being checked reads exactly like a rule that
was obeyed** (`ci-rule.md` §5.5; the reviewer's question J2). It was rescued to the address its
subject moved to, as `test_contract_file_naming.py` over every `contracts/` tree in `src/` —
`support/*` packages publish ports too, so the scope is the repository's rather than one tree's.
Measured before writing: 143 contract files, 36 declaring an interface, **zero** offenders, which is
what makes a ratchet the right shape. Probed by planting an `IPlantedPort` in
`contracts/trade.py`: exactly that test fails, and only it.

### 6.5 The gate

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, **4950 passed, 4 skipped**
in 187s. The log file was grepped rather than the console: 4 hits for
`FAILED|ERROR|Traceback|ResourceWarning` — the two the parametrized test id `[ERROR]` produces and
the log-scan step's own two headings — and **0** records matching `- (WARNING|ERROR|CRITICAL) -`.

Test count **4947 → 4950**, a net **+3**, and every id accounted for by
`--collect-only` on both trees:

| Change | Δ |
| :--- | :-: |
| the 165 moved tests | 0 — same ids at new paths |
| `test_application_layer_structure.py` rewritten: 4 tests → 3 (`test_cqrs_classes_live_under_use_cases_dir`, `test_interface_classes_live_under_ports_dir` and `test_interface_files_use_i_prefix_naming` out; `test_no_interface_class_lives_under_a_modules_application_tree` and `test_the_guard_has_a_subject` in) | −1 |
| `test_scanned_roots_are_not_empty.py` — two rows retargeted, same two tests | 0 |
| `test_logging_namespace_guard.py` — per-source-file parametrization: `src/domain/backtesting/__init__.py` out, `src/modules/backtesting/module.py` in | 0 |

| `test_contract_file_naming.py` — §6.4's rescued rule: two tests (the check and its subject assertion), plus the two `test_scanned_roots_are_not_empty.py` parametrisations its registry row brings | +4 |

mypy clean on **478** source files, up from 476.

---

## 7. PR 3.1c-2 — the file held three things, and the ceiling is not the argument

§5.5 committed this split to PR 3.1c and named the seam it could see from
outside: *"a broker's books, and the matching/fee/margin policies it delegates
to"*. Reading the file for the split found a **third** thing, which is why it is
three files and not two:

| File | Lines | What changes it |
| :--- | :-: | :--- |
| `paper_exchange.py` | 472 → **397** | pyramiding, a partial close, what goes in the trade log — the **books**: cash, open positions, the log, and the dispatch from a `Signal` to an entry or an exit. It records; it does not compute |
| `fill_pricing.py` | **236** (new) | a second sizing rule (ADR D17 promises the user an ATR-based one), a venue with a different fee shape — the **arithmetic** against this run's `BrokerSimulationConfig` and `PositionSizing`, holding the four policies that do it |
| `open_position.py` | **48** (new) | a new field on a position (funding, `mae`/`mfe` — `BOT-106B` is the open task) — the **record**, pure data, `IStoppablePosition`'s sole implementer |

The 400-line ceiling (`architecture-rule.md` §5 rule 4) is what made this
urgent, and it is deliberately **not** the argument: a file can be short and
still hold two abstraction levels, so `fill_pricing.py`'s docstring argues from
§5 rule 3 and from the column above — each of the three changes for a reason the
other two do not. `code-quality-rule.md` §4's Single-Scope Cohesion is what a
reader reaches for to argue they belong together, and rule 3 is the clause that
wins: same *feature*, different *abstraction level*. It is the one place those
two rules genuinely collide, and the reviewer's D8 asks for exactly this to be
stated rather than assumed.

**Not one formula moved.** Every method on `FillPricing` is the body it had as a
`PaperExchange` private method; the four policies still do all the computing.
The class is a holder — the same shape `StrategyEngineFactory` took in PR 3.1b
and for the same reason: a caller asks in the vocabulary of a fill (*"what
capital may a LONG entry at this price use?"*) instead of assembling four
arguments out of two configuration objects at each of five call sites.

### 7.1 `_OpenPosition` became `OpenPosition`

A leading underscore means *private to this module*, and two modules now import
it, so the underscore was one commit away from being a lie. The name it must not
collapse into is `trading`'s `LivePosition` — a real exchange's answer about real
money, against a number this app mutates on every candle — and HLD §1 C3 keeps
them apart deliberately; `Docs/VOCABULARY` carries both rows and the reason.
Three docstrings that named the old spelling are corrected
(`order_matching_policy.py`, `live_position.py`, `fill_pricing.py`), as are
HLD §01's cut-criteria row, HLD §03's Internal row and `BOT-106B`, which is a
**backlog** task that would otherwise send its implementer to the wrong file.

### 7.2 The finding, measured and **not** fixed here

`PaperExchange.__init__` takes four policy parameters. Grepped across `src/`,
`tests/` and `scripts/`: `margin_policy=`, `matching_policy=` and `fee_policy=`
have **zero** callers — not one, anywhere, ever. Only `sizing_policy=` is passed
(15 sites), and that one carries ADR D17's promise.

Three constructor parameters nobody has ever passed are a seam that exists in
code and is used nowhere, which is the shape `BUG-120` and PR 2.1d's
"binding nothing resolves differently" both warn about. They are kept in this
pull request on purpose: removing them is a **signature change**, this pull
request is a split, and `commit-rule.md` §4 wants one logical change. The honest
replacement is one `pricing: FillPricing | None = None` parameter — strictly more
capable than the four it replaces, at the abstraction level the split just
created — and it is recorded here rather than done quietly, so whoever next
touches this constructor has the measurement instead of the guess.

### 7.3 The evidence

The golden master, the hand-verified per-trade tests and both integration
backtest suites pass **without one line changed** — 315 passed / 4 skipped in
132s across `tests/unit/modules/backtesting` and `tests/integration` — which is
§2's bit-identical criterion, and the only evidence a pure refactor of this file
can offer. mypy clean on 480 source files; `evaluate_intrabar_stops` is generic
in the position type like the policy it delegates to, so `self._positions` stays
`list[OpenPosition]` rather than widening to the contract on every bar.

**No new test**, and that is `testing-rule.md` §1's other branch rather than an
omission: `FillPricing` has no behaviour of its own to pin, and a test asserting
that a delegation happened would pin a call rather than a promise
(`domain-truth-rule.md`). What the split *could* have broken is the one wiring
the pass-through carries, so it was probed rather than reasoned about: setting
`sizing_policy=None` in the constructor's hand-off to `FillPricing` fails exactly
`test_the_injected_sizing_policy_is_what_sizes_the_paper_fills` and nothing else —
PR 3.1b wrote that test for this seam, and it still guards it after the split.

### 7.4 The gate

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`,
**4952 passed, 4 skipped** in 185s, log `logs/ci-local-20260916-145719.log` grepped rather
than the console: 4 hits for `FAILED|ERROR|Traceback|ResourceWarning` (the known
benign set) and **0** records matching `- (WARNING|ERROR|CRITICAL) -`.

Test count **4950 → 4952**: `test_logging_namespace_guard.py` is
parametrized per source file, and this pull request adds two
(`fill_pricing.py`, `open_position.py`).

---

## 8. PR 3.1d — the Anticorruption Layer, measured out

Item 3 and HLD §02's own row describe a folder: *"`backtesting/adapters/` translates `PaperExchange`
into `StrategyContext`; `trading` provides one from `LivePosition`."* It is not built, and this is
the `IStrategyCatalog` outcome a second time — measured, and correctly not shipped. The measurement
is three greps.

**1. Nothing outside `modules/strategy` constructs a `StrategyContext`.** In `src/` and `scripts/`
there are exactly two construction sites, both inside that module: `StrategyEngine._process_one()`
and `StrategyEngine.on_forming_bar_tick()`. `strategy_trend_zones.py` builds one too — also
`strategy`'s, its own UI. `backtesting` builds none, and neither does `trading`.

**2. What `backtesting` actually hands the engine is one fact, not a model.** All three call sites in
the two runners read the same way:

```python
signal = engine.on_tick(candle, current_position_side=exchange.current_side)
```

`current_side` is a `PositionSide | None` from `trading/contracts` — published vocabulary, a legal
import, and the one word HLD §02 says a paper position and a live one must agree on. The engine
composes the context on the far side of the port. **`IStrategyEngine` is the anticorruption
boundary**, and PR 3.1b built it.

**3. The boundary it was to protect is already clean.** Everything `modules/backtesting` imports
from `modules/strategy`:

```
modules.strategy.contracts.i_sizing_policy
modules.strategy.contracts.i_strategy_engine
modules.strategy.contracts.signal
modules.strategy.contracts.signal_action
```

Four published contracts, nothing else, and **zero** `backtesting → strategy` lines on the
allowlist. An ACL translates a foreign model that leaks in; nothing leaks in.

### 8.1 Building it anyway would make the boundary worse

`StrategyContext` is a frozen dataclass carrying a `MarketData`, a `PositionSide | None` and
`Mapping[str, float | MACDValue | SupportResistanceValue]`. For `backtesting/adapters/` to construct
one, `StrategyContext` would have to be **published** — and a published contract may not carry a
domain type. That is PR 2.1c's rule, and it is the rule that deleted `IStrategyCatalog`: the port was
written, and all four would-be consumers turned out to need `BaseStrategy` itself. Here the indicator
map is worse than one class, because it drags `support/indicators`' value types into `strategy`'s
published surface for the benefit of a translation nobody asked for.

There is also nothing for the translation to do. The item's own phrasing is the tell — *"translates
`PaperExchange` **state** into `StrategyContext`"* — and the state in question is one enum member. A
layer whose whole job is `PositionSide → PositionSide` is the accidental complexity ADR D2 exists to
avoid.

### 8.2 The places that said otherwise, and one that was carrying a known falsehood

The claim was in the diagram, the context map, the vocabulary, the migration table and this file —
and the PlantUML note read *"today three strategies still import `domain/backtesting` — the wrong
direction — and that is the dependency this ACL removes"*, which HLD §02's own round-3 correction had
already measured as **false**. A design justified by a dependency that does not exist is the
drifted-copy disease `CLAUDE.md` records twice, one abstraction level up.

Corrected in this step: HLD §02's ASCII map and its ACL row, HLD §03's `StrategyContext` row and its
consumer column, HLD §06's Phase 3 migration row, `Docs/VOCABULARY`'s ACL definition,
`hld-01b_module_dependencies.puml`'s note, and items 1/3 plus §4.3's row here. The `binance_gateway`
ACL is untouched and remains the repository's one real anticorruption layer — it wraps a foreign
model, the Binance SDK, that genuinely does leak.

### 8.3 What this means for the phase

Phase 3's coded work is **done**: 3.1a (the deletion), `BUG-127`, 3.1b (`IStrategyEngine`), 3.1c (the
move), 3.1c-2 (the split). §2's bit-identical criterion holds — the golden master and the
hand-verified per-trade tests have passed unchanged through every one of them. Half B, the Backtest
screen, is Phase 4's by §4.1's measurement, and §4.4 already said so.

No gate: this step changes no code file (`ci-rule.md` §1's documentation exception).

## 9. Item 4's second half, closed 2026-09-19 — `IChartHost` was never built, and reading the code shows why that is correct

Item 4's original text read *"fill and marker overlays go through `IChartHost`"* — a shared,
published port under `support/charting/contracts/` that `EPIC-025E` step 1's own docstring once
listed as "not published yet" alongside `MarkerPoint`/`RegionSpan` (`info_field.py`'s docstring
still names all three). Phase 3 closed without it existing, and this phase's own status line called
that undone. Re-reading the shipped code rather than the plan says otherwise.

**What actually draws fills and markers**: `modules/backtesting/ui/coordinators/
chart_render_coordinator.py`'s `apply_after_native_fallback()` reads `self._view.chart_cards[0]` —
a real `support/charting` `ChartCard` widget the view already holds — and calls draw methods
(`set_script_regions()` etc.) on it directly. No port mediates this call at all, named `IChartHost`
or otherwise.

**Why that is not a hole**: `modules/backtesting/ui/` is exactly the kind of consumer `support/
ui_kit`/`support/charting`'s `_UI_SUPPORT_ZONES` exception exists for — a module's own `ui/`
package may import `support/charting` whole (`architecture-rule.md` §3, the same rule 4.4c's
review confirmed for `support/indicators/ui/`). A shared `IChartHost` port would only earn its
keep if drawing on the chart had to cross a *module* boundary; it does not; `ChartCard` is a
support-package widget the backtest screen constructs and owns, the identical shape every other
module's `ui/` already uses its support packages through. Building the port anyway would have been
the same mistake item 3's Anticorruption Layer and `IStrategyCatalog` both were before they were
measured out: a seam for a need that direct, already-legal construction already satisfies.

**What `IBacktestChartHost` is instead, so it is not confused for the missing port**:
`modules/backtesting/ui/ports/i_backtest_chart_host.py` — pre-existing this epic (`BOT-098F6A`) —
is a narrower thing entirely: `widget`/`symbol`/`add_to_header()`, for embedding the chart into the
view's layout and swapping hosts on a mode change. It never carried fill/marker drawing and was
never meant to.

**Item 4 is fully done.** The shared port item 4 named is correctly unbuilt; the capability it was
meant to protect (fills and markers render on the backtest chart) is real and verified by reading
the coordinator that draws them, not by trusting a docstring that only ever said "not published
yet" without saying whether it ever would be needed.

No gate: this step changes no code file (`ci-rule.md` §1's documentation exception).
