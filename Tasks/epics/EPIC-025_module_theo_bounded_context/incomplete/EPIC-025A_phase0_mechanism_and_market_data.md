# EPIC-025A — Phase 0: the module mechanism plus `modules/market_data` (Walking Skeleton)

- **Status:** 🟡 In progress since 2026-09-13 — PR 0.1 (baselines and guards) first; the PR plan is in the epic README §3.2
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
Management mode rebuilt as QtWidgets — HLD §11: its four QML widgets become a `QTableView` panel,
a kline-inspector dialog, a time-range dialog and a timeframe picker; no `.qml`), the CLI
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

## 2. Done when

- The app runs exactly as before; Data Management goes through the registry; CLI `sync` and
  `stream` work.
- The guard allowlist has shrunk by exactly the `market_data` entries; `ci-local.ps1 -Full` is green
  (the log file grepped, not the console).
- The sanity tier has **zero** new tests.
