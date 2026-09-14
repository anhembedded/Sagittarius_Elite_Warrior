# EPIC-025A — Phase 0: the module mechanism plus `modules/market_data` (Walking Skeleton)

- **Status:** ✅ Code complete 2026-09-14 — all seven pull requests merged (0.1, 0.2, 0.3, 0.4a,
  0.4a-2, 0.4a-3, 0.4b-1, 0.5; the last as #214). **One item outstanding and it is the user's:**
  running the app once — Trading loads history, Dev Board "Start Live" syncs and streams, Data
  Management syncs a symbol, CLI `sync`/`stream` work. §1.9 audits §2's "done when" clause by
  clause. Kept here until that run happens, because the epic README §3 ends every phase with
  *the app running*, not with a green gate.
- **Repository:** Elite
- **Blocks:** B, C, D, E
- **Read first:** HLD §1–§3 (cut criteria, context map, the contracts of `market_data`), §4
  (contribution points), §6 (guards); ADR D2, D3, D5, D9, D11.

## 1. What to do

**The mechanism (nothing migrates except `market_data`):**

1. `src/core/` — `core/contracts/` (the application-side kernel contracts: `IContributionRegistry`
   and the `Contribution*` descriptors) and `core/vo/` (the Published Language: only value objects
   that already have two or more consumers in two modules — HLD §2.4).
2. `src/shell/` — Martin's "Main": `modules.py` lists the `BoundedContextModule`s explicitly;
   `create_app()` moves here from `src/main.py`; `binance_bot_module.py` is **not deleted** in this
   phase, it only loses its `market_data` part.
3. `BoundedContextModule(IExtension)` (HLD §3.1) and `IContributionRegistry` (HLD §4).
4. The three AST guards under `tests/unit/architecture/`: `test_module_boundaries.py` (allowlist
   **= as found**, shrink-only), `test_module_domain_is_qt_free.py`, `test_module_declarations.py`
   (the two-way check of the module list against `modules/` on disk).
5. Remove the hard-coded tuple of five screen modules in `app_bootstrapper.py`; the shell takes
   them from `screen` contributions — the four still-legacy screens through `LegacyScreenAdapter`
   (SDD, boot step 6).
6. `core/contracts`: `IPlaceHost` (implemented by `ui_kit.PageShell`), `IConfigWriter` (adapter over
   `ConfigManager` in `shell/`), `errors.py::ContributionError`; one shared `ConfigManager` for the
   GUI and headless paths (declared behaviour change: headless `--dev` starts working).
7. Commit `tools/measure_duplicate_members.py` (the 59-duplicates script over old and new trees) and
   `tests/unit/architecture/allowlist_module_boundaries.txt` (10 `(importing, imported)` pairs, no
   line numbers); move the five existing guards into `tests/unit/architecture/`.
9. **Tests (HLD §9, ADR D18):** retarget every path-scanning guard to the new paths with a
   non-emptiness assertion, gather the architecture guards under `tests/unit/architecture/`,
   capture the backtest golden master, record the collected-test count as the baseline; move the
   `market_data` tests by `git mv` with bodies unchanged.
8. **Make the skeleton walk with N = 2:** move one existing consumer onto a `market_data` port —
   `screens/trading/coordinators/chart_coordinator.py:145` calls `IMarketDataSync` instead of
   dispatching `SyncMarketDataCommand` — so a real cross-boundary port call exists in Phase 0.

**The Walking Skeleton — `modules/market_data/`** (HLD §3.2): `domain/` (Kline, the symbol catalog,
shards, gaps, coverage, `MarketDataVenue`), `application/` (the `sync/` and `database/` use cases,
the klines query, the market stream), `contracts/` (`IHistoricalKlines`, `ISymbolCatalog`,
`IMarketStream`, `IMarketDataSync`, `IRangeCoverage`, DTOs, the events `MarketTickEvent` and
`SingleSyncProgressEvent`), `adapters/` (`persistence/`, `binance/market/`), `ui/` (the Data
Management mode rebuilt as QtWidgets — HLD §11: its four sole-owned QML files become a `QTableView`
panel and a kline-inspector `QDialog`; no `.qml`. **This sentence used to name a time-range dialog
and a timeframe picker instead — see §1.7: those two widgets are shared with four other screens and
cannot be rebuilt from inside a Data Management pull request**), the CLI
commands `sync` and `stream`. Also in this phase (ADR D21 as executed by **D21a**): remove
`qdarktheme` from `requirements.txt` and delete `_apply_theme()` with its two `ui.theme.*` keys, so
every standard control renders in the OS theme from Phase 0 on. `Palette`, `seed_app_theme()` and
`kit/style.py` are **not** deleted here — the 35 surviving `.qml` files need
`configure_app_qml()` (`BOT-132`) and `kit/style.py` has 52 call sites across the screens that
Phases 1–4 rebuild; they go in Phase 4 with their last consumer, and the remainder shrinks under
`tools/measure_app_styling.py` + `test_app_styling_only_shrinks.py`. `support/binance_gateway` is extracted in the same phase because
`market_data` needs it.

## 1.1 Baselines measured in PR 0.1 (2026-09-13)

Every number below was produced by a script or a test in this repository, on the tree as it stood
before any Phase 0 code moved. The guards that hold them fail when the number grows; each phase
records the new value in its own pull request (HLD §6.2).

| Metric | Source | Value as found |
| :--- | :--- | :--- |
| Duplicated member names, `dashboard` ↔ `trading` | `tools/measure_duplicate_members.py` | **59** (also: backtest+dashboard 22, dashboard+data_management 10, backtest+data_management 4, settings+trading 4, data_management+trading 1; 131 names live in more than one screen package) |
| Boundary allowlist entries | `tests/unit/architecture/allowlist_module_boundaries.txt` | **10** pairs (5 `application → infrastructure`, all `futures_trading_client`; 5 `presentation → infrastructure`) |
| Screens importing `infrastructure/` | the same allowlist | **2** (`backtest_presenter`, `settings_presenter`) |
| `.qml` files under `src/` | `tests/unit/architecture/baseline_qml_files.txt` | **35** |
| App-level styling left by hand (PR 0.2) | `tools/measure_app_styling.py`, held by `baseline_app_styling.json` | **52** `apply_role()` calls in 26 files · **151** `setStyleSheet()` calls in 22 files · **33** files importing `Palette` · **229** `Theme.*` bindings in 35 `.qml` files |
| Path-scanning guards registered with a non-empty root | `tests/unit/architecture/test_scanned_roots_are_not_empty.py` | **30** guard files, 37 scanned roots |
| Backtest golden master | `tests/integration/golden/backtest_golden_master.json` | 600 hourly bars, `ema_crossover` 12/26, 13 trades (9 in-sample, 3 out-of-sample), final balance 9211.71 from 10000 |
| Tests collected (`pytest --collect-only -q`, everything but `tests/testnet`) | the gate's own invocation | **3948** before PR 0.1 (26 of them sanity); **4059** after it (the 111 added are the safety net itself: 108 architecture guard cases and 3 golden-master tests), **4183** after PR 0.2 (124 more: the two new architecture guards, the styling ratchet, and the mechanism's own unit tests under `tests/unit/shell/`). Every later phase reports its delta |
| `presentation/ui/common/` | `ls` | 25 files |
| `binance_bot_module.py` | `wc -l` | 750 lines |

### The two PR 0.1 review questions, settled by the decision doctrine

The executor put two questions to the user: should any of the ten allowlist pairs be fixed earlier
than the phase that owns it, and should the golden master use captured Binance klines instead of a
generated series. The user's reply (2026-09-13: *"có rule ra quyết định mà, bạn check mà ra quyết
định đi"* — "there is a decision rule; check it and decide") was the correct correction: neither
question belongs to the three groups `ONBOARDING.md` §7 reserves for asking. They are settled here.

1. **The allowlist stays exactly as found.** Which phase removes which pair is already fixed by
   HLD §6.3 and the ADR: the five `futures_trading_client` imports go when `modules/trading` owns
   the client behind `ITradingSession` (Phase 1), the payload mapper and the endpoint table when
   `support/binance_gateway` exists (Phases 0–1), the metadata cache with `modules/backtesting`
   (Phase 3). Fixing one early would put application code into a pull request whose own definition
   is "no app code", and would spend the Phase 1 risk budget in Phase 0 (HLD §6.4). Sequencing that
   the design already records is not a business question.
2. **The golden master keeps its generated dataset.** This is a characterisation test (Feathers,
   *Working Effectively with Legacy Code*; the golden-master/approval pattern as ApprovalTests
   implements it), and that pattern wants a self-contained deterministic input committed beside the
   recorded output. Captured exchange data would add an external dependency, a licence question and
   a larger fixture while proving nothing extra: the test asserts that Phase 3 **reproduces** the
   result, not that the result is realistic. Acceptance against real market data already has a tier
   of its own — `tests/testnet` — and `testing-rule.md` §1 forbids moving a test between tiers.

The golden master's dataset is a seeded random walk (seed `20260913`) with a weak sine drift and
±1.5 % per-bar noise, chosen so the 12/26 crossover whipsaws enough to produce losing trades and a
real drawdown, not only a trend ride. It is a *regression* fixture, not a benchmark: its point is
that Phase 3 reproduces these exact numbers, whatever they are.

## 1.2 What PR 0.2 shipped (2026-09-13)

The mechanism, with no bounded context migrated yet — that is PR 0.4's job. Ten files under
`src/core/` and `src/shell/`, 1 311 lines including their docstrings, and the app boots and runs
exactly as before (`--self-check` green, 4 153 tests passing).

| Piece | File | What it settles |
| :--- | :--- | :--- |
| The contribution descriptor | `core/contracts/contribution_descriptor.py` | one shape for every contributed widget; `factory` is the only Qt-typed field and is typed under `TYPE_CHECKING` |
| Places and size hints | `core/contracts/place.py`, `size_hint.py` | the ten places of HLD §4 and three size buckets, as enums |
| A whole screen | `core/contracts/screen_contribution.py` | the one exception to the single shape, reusing `NavMetadata` unchanged |
| The registry port | `core/contracts/i_contribution_registry.py` | the entire surface area of "a module adds UI": two calls, nothing returned |
| The module base class | `core/bounded_context_module.py` | `IExtension` plus `contribute()` and `subscribe()`, both defaulting to nothing; `module_id` and `dependencies` |
| Navigation metadata | `core/contracts/nav_metadata.py` | moved out of `presentation/ui/registry/models/` — it is shared vocabulary now, not registry-internal |
| Writing config | `core/contracts/i_config_writer.py` + `shell/config_writer.py` | the port that replaces `settings_presenter.py`'s `isinstance(self.config, ConfigManager)` downcast |
| The surfaces | `shell/surfaces.py` | the six surfaces, what each `accepts`, and `dev_board`'s gate |
| The registry | `shell/contribution_registry.py` | validation rules 1–4 at contribute time; a gated-off surface drops with a log line |
| The module list | `shell/modules.py` | empty, on purpose: the two-way declaration guard is live before the first module |
| Registering modules | `shell/module_registration.py` + `registering_container.py` | the spying container: `resolve()` during `register()` fails by name, and every claim is recorded |
| No double claim | `shell/double_claim_check.py` | the second module to claim one abstract type fails before `boot()` |
| The composition root | `shell/composition_root.py` | `create_app()`, moved out of `src/main.py` |
| One configuration | `shell/app_config.py` + `dev_mode.py` | one loader for both entry points, and `dev.mode` decided once per run |
| The legacy screens | `shell/legacy_screens.py`, `legacy_screen_adapter.py`, `screen_wiring.py` | the five screens the strangler still carries, as `ScreenContribution`s; the hard-coded tuple is gone from `app_bootstrapper.py` |

**Two corrections found while building it**, both recorded because the next reader would hit them:

1. `DoubleClaimCheck`'s first implementation read the container after each module registered. That
   cannot work: `singleton(IKlines, SqliteKlines)` and `singleton(IKlines, RestKlines)` both report
   `Registration(concrete=None, lifetime="singleton")`, because a class handed to `singleton()`
   becomes a lazy factory whose return type is unknowable until it runs. A unit test caught it, and
   the fix is the spying container the SDD's register-versus-boot table already called for.
2. `ScreenRegistry.register()` did not reconcile sidebar sections — `register_module()` did, one
   level up. A screen arriving as a *contribution* has no module behind it, so the sidebar silently
   lost its section. The reconciliation moved into `register()`, which is now the single path both
   kinds of screen take.

**Deliberately not in PR 0.2**, with the reason:

- **`core/vo/`** — HLD §2.4 admits a value object only once two modules consume it. Phase 0 has
  none, so the package does not exist yet.
- **Gating the Dev Board screen off.** The mechanism is there (`Surface.gated_by`, validation rule
  3, `resolve_dev_mode`), but `dashboard` is still the default route and Welcome does not exist yet
  (ADR D13). Turning the gate on now would leave a run with no default route. Phase 1 flips it when
  Welcome becomes the default and Dev Board becomes a surface.
- **Moving the GUI boot into `shell/`.** `app_bootstrapper.py` still owns `QApplication`, the
  window and the watchdog; it now calls the shell for configuration, developer mode and screens.
  Its permission to do so is one named entry point in the boundary rules, and it moves in Phase 1
  with the surface host.

## 1.3 What PR 0.3 shipped, and the two files it deliberately left behind (2026-09-14)

`support/binance_gateway` exists: nine modules moved, no behaviour changed, and the boundary
allowlist shrank from **10 pairs to 8** because two of them stopped being violations rather than
being excused.

| Moved to | What |
| :--- | :--- |
| `support/binance_gateway/contracts/` | `MarketDataVenue`, `TradingVenue` (two closed Binance-specific enums — HLD §2.4 round 3), `ExchangeCredentials`, `ITradingSessionFactory` + `ITradingSessionClient`, `IExchangeCredentialsProvider` + `CredentialsSource` + `ResolvedCredentials`, `binance_endpoints` (venue → `testnet` flag / `klines_type`, and reading the configured venue) |
| `support/binance_gateway/adapters/` | `EnvFirstCredentialsProvider`, `SecretsFileSource` |
| `tests/unit/support/binance_gateway/{contracts,adapters}/` | the six tests that mirror them, bodies unchanged |

**The allowlist shrank by two.** `app_bootstrapper` and `settings_presenter` both reached into
`infrastructure.binance.binance_endpoints` for the venue resolvers. That module is now a support
package's contract, which every zone may import, so both lines were deleted from
`allowlist_module_boundaries.txt` — the first two entries this epic has actually retired. HLD §6.2's
"screens importing `infrastructure/`" metric goes **2 → 1** (only `backtest_presenter`'s metadata
cache is left, and it goes in Phase 3).

**Two files HLD §3.5 listed for Phase 0 did not move, each for a measured reason.** The rule they
would have broken is the one direction the strangler period keeps firm: a package in the new tree
may not reach into the legacy tree (`test_module_boundaries.py`; the shell is the single exception,
as *Main*, and even that is recorded in a shrink-only baseline).

1. **`exchange_session_factory.py` stays put, and so does `IExchangeSessionFactory`.**
   `create_market_data_client()` builds a raw `Client` **and** wraps it in `PythonBinanceClient`
   (`infrastructure/binance/client.py`), which is market_data's own adapter — it is built out of
   `MarketData` candles, so it belongs to `modules/market_data/adapters/binance/`, not to a generic
   SDK gateway. Moving the factory now would make a support package import the legacy tree; moving
   `client.py` with it would make the gateway own a market-data shape. The real fix is the one HLD
   §2.3 already describes — the gateway mints a **raw session**, and market_data's own adapter wraps
   it — and that is PR 0.4's work, when `modules/market_data/adapters/binance/` exists and
   `IExchangeClient` splits into `IHistoricalKlines` / `ISymbolCatalog`. Doing it here would be a
   redesign inside a pure move.
2. **`binance_error_translator.py` stays put until Phase 1.** It maps a `BinanceAPIException` onto
   `OrderRejectionReason`, which is `trading`'s vocabulary and has no home outside the legacy tree
   until `modules/trading` exists. The alternatives were a support-to-legacy import (forbidden) or
   promoting `OrderRejectionReason` into `core/vo`, which HLD §2.4's own admission rule refuses: it
   is business vocabulary of one context, not a neutral value object.

Both deferrals are recorded in the HLD §3.5 mapping table as their own rows, with the phase that
finishes them, so the next reader sees the plan and not a gap.

## 1.4 PR 0.4 is split in two (decided 2026-09-14)

The plan had one pull request carrying both the module extraction and the QtWidgets rebuild of Data
Management. Those are two different kinds of risk — a move that must change no behaviour, and a UI
rewrite that changes what the user sees — and bundling them means a red gate cannot tell you which
half broke. `architecture-rule.md` §5's bias applies to pull requests as much as to files:
splitting needs no permission.

| | Content | Risk it carries |
| :-- | :--- | :--- |
| **0.4a** | the module: `domain/`, `application/`, `contracts/`, `adapters/`, registration in `shell/modules.py`, CLI `sync` / `stream`, contract suites and verified fakes. Data Management keeps its current widgets and consumes the module through its contracts | a pure move — every existing test must still pass, unchanged |
| **0.4b-1** | the two QML islands inside Data Management rebuilt as a `QTableView` panel and a `QDialog`; four `.qml` files deleted | the first visible UI change of the epic; the QML baseline drops by four |
| **0.4b-2** | ~~the screen moves to `modules/market_data/ui/` and is contributed through `ScreenContribution`~~ — **deferred to Phase 4** (§1.8): the move needs `support/ui_kit`, or it costs 35 backward imports | — |

The user's Phase 0 checkpoint ("Data Management: sync a symbol") lands on **0.4b**, with the CLI
check on 0.4a.

## 1.5 What PR 0.4a shipped (2026-09-14)

`market_data` is a module. `shell/modules.py` lists one entry where it listed none, and the app
boots through it: the database, both repositories, the live stream, the exchange client, and all
fourteen commands and queries are now claimed by `MarketDataModule.register()` instead of by
`binance_bot_module.py`.

### What moved, and where the shape changed

Sixty-odd files moved by `git mv` with their bodies untouched. Four things were *not* a plain move,
and each one was forced by a rule rather than chosen:

| What | From | To | Why not a plain move |
| :--- | :--- | :--- | :--- |
| `backtest_range_coverage.py` | `application/services/` | three files | One file held a published DTO, two builders, and three time helpers — three audiences, measured: the DTO has three UI consumers, the builders none outside the module, the helpers one. §5 rule 1 forbids the mix, and the boundary rule forbids a consumer importing anything but `contracts/`. |
| the four engine-adapter ports (`i_cqrs`, `i_command_dispatcher`, `i_config_reader`, `i_event_publisher`) | `application/ports/` | `core/contracts/` | Every module's handlers need them (`i_cqrs` alone has 29 importers). Left in the legacy tree they made the module import *backwards*, which the boundary rule refuses outright and which no allowlist entry should ever excuse. |
| `MarketTickEvent`, the sync events | `domain/events/`, `application/events/` | `modules/market_data/contracts/events/` | An event belongs to the context that raises it (§6). Only market_data can say a tick arrived. |
| `SymbolMarketMetadata` | `domain/entities/` | `modules/market_data/contracts/` | Published by its owner, **not** promoted to `core/vo`: the admission rule wants two consumers in two *modules*, and today market_data is the only module among its four importers. Promoting on "it looks shared" is the guess the rule exists to prevent. |

`rate_limiter.py` had exactly one importer, inside the module, so it moved in as module-internal
rather than staying a shared service nobody shared.

### The lifecycle moved with the context

`MarketDataModule` implements `boot()` and `shutdown()`, which `binance_bot_module.py` used to do
on its behalf: registering the live-stream hosted service, disposing the SQLite engines, closing the
exchange client. What stayed behind is the user-data stream, because trading owns it.

### Two things deliberately left standing

- **`exchange_session_factory.py` stays in the legacy tree.** One instance answers both
  market_data's `IExchangeSessionFactory` and trading's `ITradingSessionFactory`; splitting a shared
  instance changes behaviour, and 0.4a is a move. `EPIC-025B` splits it, one factory per context.
  The port itself did move — to `modules/market_data/contracts/`, because it returns
  `IExchangeClient`, which is a market-data shape (this is the file PR 0.3 §1.3 deferred).
- **`MarketDataModule.shutdown()` resolves `IExchangeClient` unconditionally.** Carried over
  verbatim so the move stayed a move — but it is a defect: the binding is lazy, so a session that
  never asked for market data *constructs* a client here, a network call, purely in order to close
  it. Fixing it needs the container to answer "was this singleton ever instantiated?", which
  `IContainer` does not offer. That is an Engine-side ask, not an app change; the module's docstring
  points here so the wart is not rediscovered as a surprise.

### The allowlist went up, and that is the ratchet working

8 entries → 41. Not a regression: those imports all existed before, invisible, because caller and
callee sat in one tree. Moving `market_data` out turned each legacy screen that dispatches one of
its commands into a **counted** violation with a named exit phase. Meanwhile the number the epic
actually cares about — imports pointing from the new tree back into the legacy tree — is **zero**,
and the boundary guard now fails if it ever stops being zero.

| Block | Count | Deleted by |
| :--- | :-: | :--- |
| `application`/`presentation` → `infrastructure.binance.futures_*` (pre-existing) | 7 | `EPIC-025B` |
| legacy → `modules.market_data.adapters` (reaching past the contracts) | 2 | PR 0.4b, `EPIC-025B` |
| legacy → `modules.market_data.application` (the transitional dispatch surface) | 32 | PR 0.4b, PR 0.5, Phase 1 |
| **new tree → legacy tree** | **0** | — |

### What 0.4a did *not* ship: the CLI, deferred to 0.4a-2

§1.4 scoped CLI `sync` / `stream` into 0.4a. It is not here, and the reason is worth recording
because it is the same reason twice over.

The four CLI files are small (198 lines). But `sync_cli_handler` and `stream_cli_handler` import
`presentation/cli/cli_parser.py` (`build_handler_parser`) and
`presentation/cli/handlers/i_cli_command_handler.py` (`ICliCommandHandler`) — the CLI's framework
seam, which still lives in the legacy tree. Moving the two commands into
`modules/market_data/cli/` without moving that seam first would create exactly the backwards
import this pull request spent its effort driving to zero, and allowlisting it would be excusing a
violation the same commit created.

So 0.4a-2 is: extract the seam into `support/cli_kit` (the `ICliCommandHandler` port plus the
config-driven parser builder — the CLI analogue of `support/ui_kit`, and app-wide infrastructure
that every context's commands need), then move `sync` / `stream` into the module's own `cli/`.
That retires 5 allowlist entries. Splitting it out rather than bolting it onto a pull request that
already moves ~250 files is `architecture-rule.md` §5's bias applied to pull requests, the same
call §1.4 made when it split 0.4 in two.

### Verification

`ci-local.ps1 -Full` **PASS**, log file grepped: 4163 passed, 4 skipped, coverage 94.85%, no
`FAILED|ERROR|Traceback|ResourceWarning`. Merged as pull request #213.

The gate earned its place twice on this pull request, and both failures were the right kind:

- `tests/integration/test_app_integration.py` hand-rolled the boot sequence with `BinanceBotModule`
  alone — a faithful copy of the composition root right up until the sequence changed. It now calls
  `register_modules(app, MODULES)`, the same function the composition root calls, so the next
  context to move needs no edit there.
- `tests/sanity/conftest.py` patched a module path written as **two adjacent string literals across
  two lines**, which a line-by-line rewrite cannot see. The lesson generalises: a sweep for stale
  paths must join adjacent literals first, or it reports a clean tree that is not clean.

Five mypy baseline entries in `pyproject.toml` were **re-keyed** to the new paths — not dropped,
which would have hidden 21 pre-existing SQLAlchemy `Column[T]`-vs-`T` errors, and not fixed, which
would have made a pure move unreviewable.

## 1.6 What PR 0.4a-2 shipped: the CLI, by inverting who parses (2026-09-14)

§1.5 deferred CLI `sync` / `stream` because moving them would have recreated the backwards import
0.4a had just eliminated. This is that debt repaid, and the fix was not where the deferral note
guessed it would be.

### The survey changed the design

§1.5 proposed extracting `support/cli_kit`. That was wrong, and the vocabulary caught it: HLD §1.2
and §2.2 enumerate **exactly four** support packages, and `Docs/VOCABULARY` says `shell/` holds
"the CLI assembly". A fifth support package would have needed a spec change to justify a file move.

So the doctrine's first step applied instead — survey before inventing. How does an established
tool let a plugin contribute a command?

| Tool | Who declares arguments | Who parses | What the command receives |
| :--- | :--- | :--- | :--- |
| Django `BaseCommand` | the command (`add_arguments(parser)`) | the framework | `handle(**options)` — parsed |
| Click / Typer | the command (decorators) | the framework | parsed values as parameters |
| `argparse` subparsers | the parent parser | the parent parser | `set_defaults(func=...)`, called with the namespace |

Unanimous, and the opposite of what this repository did. `ICliCommandHandler.handle(arg_str: str,
app)` made every handler re-split the line the shell had just split, build its own parser from
config, and repeat the same three `except` blocks — and *that* is why a command owned by
`market_data` could not live in `market_data`: to parse, it had to import the legacy CLI package.

The user chose this direction on 2026-09-14 over the `support/cli_kit` option. It changes a public
contract, which `ONBOARDING.md` §7 group 1 reserves for the user rather than the agent.

### The change

```
BEFORE                                      AFTER
InteractiveShell.default()                  InteractiveShell.default()
  shlex.split(line)                           shlex.split(line)
  " ".join(words[1:])   <- re-joins!          _parse(cmd_name, words[1:])   <- parses, once
       |                                           |
  handler.handle("--symbols BTC", app)        handler.handle(Namespace(symbols="BTC", ...), app)
       |                                           |
  shlex.split again                           (nothing left to do)
  build_handler_parser(config, name)          |
  parse_args / 3 except blocks           <- x3 handlers, copied
       |                                           |
  one real line of work                       one real line of work
```

`ICliCommandHandler` moved to `core/contracts/`, because the implementations belong to modules and
nothing may import the shell — the same inversion `IContributionRegistry` already uses.

### What it bought

| Measure | Before 0.4a-2 | After | Target |
| :--- | :-: | :-: | :-: |
| Allowlist entries | 41 | **38** | -> 0 |
| Parsing sites | 3 (one per handler) | **1** | 1 |
| `except` blocks for argparse | 6 | **2** | in one place |
| New tree -> legacy tree imports | 0 | **0** | 0 |

Five dispatch entries left; two handler-class entries arrived, because
`InteractiveShell.handlers` still hard-codes `{"sync": SyncCliHandler, ...}`. Those two are cheaper
and they have a named exit: Phase 1 moves `interactive_shell.py` into `shell/` and replaces the
hard-coded table with a declaration on each module, collected from `MODULES` the way `contribute()`
already works. It could not happen here — the shell also drives trading's `exchange-status`
handler, still in the legacy tree, and `shell/`'s own legacy-import baseline only shrinks.

### Tests followed the behaviour, not the file

Three cases left the handler tests for `test_interactive_shell.py`: a missing required argument,
`-h`, and an unknown flag. They were always assertions about argparse, made through whichever
handler happened to own a parser; they are now asserted once, where the parsing is. What stayed
with each handler is what it actually decides — and one case proves the split is not cosmetic:
`--interval` is declared as a free-form string, so argparse cannot reject `INVALID`; `TimeFrame()`
does, inside the handler. Parsing moving out did not make the handlers validation-free.

### Verification

The full gate (`scripts/ci-local.ps1 -Full`), with its log grepped for
`FAILED|ERROR|Traceback|ResourceWarning` — the console is not evidence, because Qt's offscreen mode
dumps harmless `TypeError`s after pytest's summary line.

## 1.7 What PR 0.4b-1 shipped: the last QML left Data Management (2026-09-14)

Data Management holds no `.qml` file any more. Its two QML islands — the shard status table and
the candle-lookup modal — are a `QTableView` with four `QAction`s and a `QDialog`, and the four
`.qml` files behind them are deleted (ADR D20). The screen around them was already QtWidgets
(`EPIC-005E`), so this pull request is the two islands and nothing else. Moving the screen into
`modules/market_data/ui/` was planned as 0.4b-2 and is **deferred to Phase 4** — §1.8 measures why.

### The spec named the wrong four files, and the inventory said so before any code moved

§1 of this document says Data Management's *"four QML widgets become a `QTableView` panel, a
kline-inspector dialog, a time-range dialog and a timeframe picker"*. The count is right and the
list is wrong. `TimeframePicker/*` and `TimeRangePicker/*` are **shared** — Backtest, Dashboard,
Settings, the chart card and the market picker all load them — so rebuilding them here would have
rebuilt four other screens' widgets from inside a Data Management pull request. The four files
that are sole-owned by this screen, and therefore the four that went, are:

| Deleted | Lines | Replaced by |
| :--- | :-: | :--- |
| `qml/DatabaseStatusTable/DatabaseStatusTable.qml` | 94 | `data_management_widgets/database_status_panel.py` |
| `qml/DatabaseStatusTable/DatabaseStatusRow.qml` | 148 | the model's six columns, rendered by `QTableView` |
| `qml/KlineInspectorTable/KlineInspectorTable.qml` | 74 | `data_management_widgets/kline_inspector_dialog.py` |
| `qml/KlineInspectorTable/KlineInspectorRow.qml` | 112 | the model's eight columns, rendered by `QTableView` |

The two shared pickers stay until their last consumer is rebuilt — the same ratchet logic ADR D21a
applies to `Palette` and `kit/style.py`, and the reason the QML baseline is a shrink-only list
rather than a deadline.

### The row buttons became actions, which is the rule and not a preference

```
BEFORE (QML)                                  AFTER (QtWidgets)
DatabaseStatusTable.qml                       DatabaseStatusPanel
  PanelHeader + TextField (search)              QLabel + QLineEdit (search)
  DataTable                                     QToolBar: 4 QActions
    ListView                                    QTableView (6 columns, sortable)
      DatabaseStatusRow  x N                      + the same 4 QActions as its
        4 Buttons each  <- 4N controls              context menu  <- 4 controls
```

`QAction` had **zero** occurrences in `src/` before this pull request; these four are the app's
first. That is the Consistency principle made literal ("one `QAction` per user action, carrying its
shortcut, its menu entry and its toolbar button"), and it is why the buttons could not simply be
moved into cells: a control per row is the shape QML forces, not the shape the desktop has.

Three consequences worth naming, because each is a behaviour change a reviewer should look for:

- **an action now acts on the selected row**, so the panel has a selection model where the QML
  table had none. A regression test pins that the action follows the selection rather than the row
  order.
- **`Inspect gaps` greys out instead of disappearing** on a healthy shard (`visible: !isHealthy`
  before). An action that vanishes teaches the reader nothing.
- **`Clear` asks first.** The QML row fired `clear` straight at the Presenter on one click; a
  destructive action must confirm and name its consequence (`Docs/HLD/11_desktop_workbench.md`
  §11.5). The confirmation is injectable, so the tests drive it without a modal.

### Two models that were `QAbstractTableModel` in name only

Both tables already had a real Qt model — and both declared `columnCount() == 1` and served custom
QML roles, because a `ListView` delegate drew the columns itself. A `QTableView` asks for
`DisplayRole` per `(row, column)` plus `headerData()`, neither of which existed. So the columns
moved out of the deleted delegates and into the models, which is where the sorting came from too:
`SORT_ROLE` carries the comparable value behind each cell, because `"1,234"` sorts before `"9"` as
text and `"15m"` before `"1h"` before `"1m"`. The first version of that returned a
`(healthy, text)` tuple and the sort silently did nothing — a `QVariant` Qt cannot order — which is
recorded in the model rather than quietly fixed.

### What was deleted because nothing read it

`KLineInspectorTableModel` paginated in memory: `set_page`, `set_page_size`, `jump_to_date`,
`total_pages`, four view-model properties, three view-model slots, a `ConfigKeys` entry and the
Presenter block that read it. None of it had reached a widget since `EPIC-015` removed pagination
from the QML port, so the page size in a user's config file has had no effect for weeks. Deleting
it changes nothing the user can see; keeping it would have meant a `QTableView` bound to a model
that hides 99% of its rows.

### Numbers

| Measure | Before 0.4b-1 | After | Target |
| :--- | :-: | :-: | :-: |
| `.qml` files in the app | 35 | **31** | -> 0 (Phase 4) |
| `Theme.*` bindings inside `.qml` | 229 | **204** | -> 0 |
| `.qml` files under `screens/data_management/`'s ownership | 4 | **0** | 0 |
| `QAction` declarations in `src/` | 0 | **4** | grows with every rebuilt screen |
| Bare-Qt-base findings | 2 | **2** (+2 `base-exempt`) | see the note below |
| Lines, this pull request | — | **+2021 / -3149** | net -1128 |
| New tree -> legacy tree imports | 0 | **0** | 0 |
| Allowlist entries | 38 | **38** | -> 0 (0.4b-2 retires 8) |

### One guard pointed the other way, and was answered rather than raised

`tests/unit/presentation/ui/test_widget_guards_hold.py` locks the number of classes deriving a bare
`QWidget`/`QDialog` at 2, because `EPIC-007E`/`007F`'s rule was "inherit the kit's
`Card`/`Panel`/`Overlay`". ADR D20–D22 reversed that for new desktop widgets: a dialog **is** a
`QDialog`, and the kit's bases paint the card chrome ADR D21 removed. Both new classes therefore
carry `# base-exempt: <reason>` — the guard's own escape hatch — and the ceiling stays at 2, so an
old-style widget still cannot slip back in. The reversal is written into that file's docstring;
raising the number instead would have hidden it.

The colour guard was answered the same way, by **not** adding a colour: the candle table's
bullish/bearish cells read `chart_card/theme.py`'s existing `BULL_COLOR`/`BEAR_COLOR`, already
documented there as "not chrome — a candle body is green because it closed up". One constant, two
widgets; the alternative was a second hex literal for the same idea, which this repository has been
bitten by often enough.

### Two questions for the user, both about what the app offers rather than how it is built

Neither is a consequence of this rebuild; both were found by the inventory that preceded it, and
both are the user's call under `ONBOARDING.md` §7 because they change what the app promises:

1. **The integrity audit is live and unreachable.** `AuditDatabaseIntegrityQuery` is bound, handled
   and tested, `DataManagementViewModel` exposes `requestRunAudit` and five audit properties, and
   the Presenter runs it — but no widget has a button for it. Expose it as a fifth `QAction`, or
   record it as deliberately deferred?
2. **Jump-to-date in the candle table is gone with the pagination.** The old `jump_to_date()`
   answered "which page holds 2024-05-01"; with a virtualized table the useful version is "scroll
   to and select that candle", which is a new feature, not a migrated one.

### Verification

The full gate (`scripts/ci-local.ps1 -Full`), with its log grepped for
`FAILED|ERROR|Traceback|ResourceWarning`. The first run of it was **red on four tests** — the two
widget guards above, the colour guard, and one test asserting the deleted modal's `objectName` —
and all four were real: two rule conflicts to resolve explicitly, one invented colour, one stale
name.

## 1.8 Why PR 0.4b does not move the screen into `modules/market_data/ui/` (2026-09-14)

§1 of this document puts Data Management's rebuilt UI in `modules/market_data/ui/`, and the
boundary allowlist said its eight `data_management.*` entries retire "PR 0.4b, when that screen is
rebuilt". The rebuild is done (§1.7) and the move is **not**, because it cannot be done in Phase 0
without inverting the one number this epic watches.

### The measurement

The screen is 22 Python files. Of their imports, 12 point at `modules/market_data/application/`
(the eight allowlisted dispatch pairs) — but **35 distinct pairs point at the legacy presentation
tree**:

| Where a moved `modules/market_data/ui/` would still have to import | Pairs |
| :--- | :-: |
| `presentation.ui.common.*` (action ownership, app defaults, the sync-progress feed and report, `qml_property`) | 11 |
| `presentation.ui.constants` | 6 |
| `presentation.ui.assets` (`Palette`, the icon loader) | 4 |
| `presentation.ui.components.*` (log panel, symbol picker, timeframe picker, the chart's candle colours) | 6 |
| `presentation.ui.kit` (`PageShell`, `ConfirmOverlay`, `apply_role`) | 2 |
| `presentation.ui.qml.*` (the two shared pickers' dialog hosts, the progress banner) | 3 |
| `presentation.ui.state.*` (state scope, container lookup, the UI state coordinator) | 3 |
| `presentation.ui.registry` (`AbstractScreenModule`) | 1 |

Allowlist arithmetic: **38 − 8 + 35 = 65**, and the metric the epic reports in every pull request —
*imports pointing from the new tree back into the legacy tree* — goes from **0 to 35**. That
number is enforceable because it has no exceptions; spending it on a directory move buys nothing a
user can see.

### It is not a gap in the plan, it is the plan's own order

HLD §6.1 already anticipates what a module's UI needs: `_UI_SUPPORT_ZONES` in
`tests/unit/architecture/boundaries/rules.py` lets `modules/<name>/ui/` import
**`support/ui_kit` and `support/charting` whole**, not merely through their `contracts/`. Those two
packages are Phase 4 (`EPIC-025E` — "`support/*`; dissolve `ui/common`"), and they are precisely
the destination of eight of the nine rows above. The move is therefore a Phase 4 step that was
written down as a Phase 0 one.

### What this changes, and what it does not

- **Deferred:** the `git mv` into `modules/market_data/ui/`, `MarketDataModule.contribute()`
  offering the screen, and removing `DatabaseScreenModule` from `LEGACY_SCREEN_MODULES`. They land
  with `support/ui_kit`, in Phase 4.
- **Re-keyed:** the eight `data_management.*` allowlist entries now name **Phase 1**, the same exit
  as the other 30 dispatch entries — a port call replaces the dispatch, which retires the entry
  wherever the file happens to live. The allowlist comment carries this measurement.
- **Unchanged:** the user's Phase 0 checkpoint. "Data Management: sync a symbol, inspect klines"
  runs on the rebuilt screen either way; where the file sits is invisible to it.
- **Rejected, and recorded so it is not re-proposed:** contributing the screen from
  `MarketDataModule.contribute()` while the code stays in the legacy tree. It costs 2 backward
  entries instead of 35, but it buys a declaration rather than a behaviour, and "zero" stops being
  a rule the moment it is worth two.

## 2. Done when

- The app runs exactly as before; Data Management goes through the registry; CLI `sync` and
  `stream` work.
- The guard allowlist has shrunk by exactly the `market_data` entries; `ci-local.ps1 -Full` is green
  (the log file grepped, not the console).
- The sanity tier has **zero** new tests.

---

## 1.9 What PR 0.5 shipped: the skeleton walks (2026-09-14, merged as #214)

Phase 0's last pull request, and the one that answers §1's own opening question — *does the
mechanism work, or does it only look like it does?* A module whose directory layout is correct but
that nobody calls through a port has proved nothing.

**The port.** `modules/market_data/contracts/i_market_data_sync.py` publishes one sentence —
*make sure this symbol's history is on disk* — behind `IMarketDataSync` with a frozen
`MarketDataSyncRequest`. Four screens used to build `SyncMarketDataCommand` and dispatch it, which
means importing `modules/market_data/application/`, the boundary rule's one prohibition. They now
name only the contract:

| Consumer | Screen |
| :--- | :--- |
| `chart_coordinator` | Trading |
| `stream_lifecycle_controller` | Dev Board |
| `data_sync_coordinator` | Backtest |
| `sync_coordinator` | Data Management |

Four, where §3.2 of the epic README planned two: all four were building the same command, so
moving one and leaving three would have published a port while keeping the violation.

The request carries the six fields the callers actually set — measured, not guessed:
`days_back_if_empty` is on the command and no caller has ever passed it, so it stayed internal.
`pydantic` does not cross the boundary; `MarketDataSyncService` translates the request into the
module's own command and dispatches it, which keeps one execution path for every sync (the same
`InFlightSyncGuard`, the same progress events). `composition/port_bindings.py` is a fourth binding
table and the only one whose audience is another bounded context.

**`BUG-120`, and why it is recorded here rather than only on the bug board.** Reviewing this PR
with `.claude/skills/pr-review/` found that the four consumers' new tests asserted less than the
old ones, not more: `FakeMarketDataSync.was_asked_for()` was their only positive claim, and
hard-coding it to `return True` left **152 tests green**. HLD §10.3 makes a fake *verified* by
running the port's contract suite against it — which verifies the surface the **port** declares,
and says nothing about what a fake adds on top. That gap belongs to the epic, not to one fake:
Phase 1 publishes two more ports, and `IExchangeClient`, `ILiveStreamService` and
`ISymbolMarketMetadataCache` still have no suite at all. It is now closed by
`tests/unit/architecture/test_fake_helpers_are_verified.py`, which requires every member a fake
declares beyond its port to be exercised beside the contract suite.

Then the guard turned out to have the same hole — a port named through `contracts/__init__.py`
resolved to no file, and the fake was skipped in silence — which is worth writing down as the
shape of the mistake rather than the mistake itself. Three times in one day: `BUG-118` (a test
that could not fail), `BUG-120` (a helper that could not fail), the guard against `BUG-120`. None
was visible by reading the code; each needed breaking the line and running.

### Phase 0's measurements, against §1.1's baselines

| Metric | As found (PR 0.1) | After PR 0.5 | Target |
| :--- | :--- | :--- | :--- |
| Tests collected (excl. `tests/testnet`) | 3948 | **4390** | grows with real coverage |
| New sanity-tier tests | 26 | **26** | **0 added** ✅ (`testing-rule.md` §1) |
| `.qml` files under `src/` | 35 | **31** | shrink-only ✅ |
| Boundary allowlist entries | 10 | **34** | see below |
| Screens importing `infrastructure/**` | 2 | 2 | 0 by end of Phase 1 |
| `presentation/ui/common/` | 25 files | 25 files | dissolved in Phase 4 |
| `binance_bot_module.py` | 750 lines | gone; `modules/market_data/module.py` is **135** | — |

### §2's "done when", audited honestly

- **"The guard allowlist has shrunk by exactly the `market_data` entries"** — this criterion cannot
  be met as written, and the reason is not a regression. It was written before PR 0.4a, which moved
  ~60 files into `modules/market_data/` and thereby turned every legacy screen's *same-tree* import
  of a market_data command into a *visible, counted* violation: 10 → 41. The honest reading is the
  one the allowlist file's own header now carries: 41 → 38 (PR 0.4a-2) → **34** (PR 0.5), shrink-only
  from the peak, with each remaining line keyed to the phase that retires it. Phase 1's target of an
  **empty** allowlist is unchanged and is the number that matters.
- **"`ci-local.ps1 -Full` is green (the log file grepped, not the console)"** — ✅ `RESULT: PASS`,
  4360 passed, 4 skipped, coverage 95.12%, both greps clean; GitHub `Lint & Test` green on
  `e0c91be9`.
- **"The sanity tier has zero new tests"** — ✅ 26, unchanged through all seven pull requests. The
  tier earned it: deleting `bind_published_ports(container)` from `module.py` fails
  `test_every_navigable_route_constructs`, because the four Presenters resolve the port through the
  real container. A feature added zero tests here and is still covered.
- **"The app runs exactly as before; Data Management goes through the registry; CLI `sync` and
  `stream` work"** — proved by tests at every tier, **not yet by a human running the app.** That is
  the user's own checkpoint (epic README §3: each phase ends with *the app running*), and it is the
  one item of Phase 0 still outstanding: Trading loads history, Dev Board "Start Live" syncs and
  streams, Data Management syncs a symbol, CLI `sync`/`stream` still work.
