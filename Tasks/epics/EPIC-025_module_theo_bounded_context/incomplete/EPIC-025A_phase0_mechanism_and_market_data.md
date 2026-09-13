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
commands `sync` and `stream`. Also in this phase (ADR D21): remove `qdarktheme` from
`requirements.txt`, delete `seed_app_theme()` and `kit/style.py`, retire the palette guard; the
app renders in the OS theme from Phase 0 on. `support/binance_gateway` is extracted in the same phase because
`market_data` needs it.

## 2. Done when

- The app runs exactly as before; Data Management goes through the registry; CLI `sync` and
  `stream` work.
- The guard allowlist has shrunk by exactly the `market_data` entries; `ci-local.ps1 -Full` is green
  (the log file grepped, not the console).
- The sanity tier has **zero** new tests.
