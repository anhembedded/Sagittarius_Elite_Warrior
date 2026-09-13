# §6 — Enforcement and migration

## 6.1 Three guards — architecture fitness functions

A rule only survives when a test enforces it. This repository has proven that three times over
(`test_quick_widget_only_in_embed.py`, `test_only_the_session_factory_constructs_binance_client.py`,
`test_one_event_is_not_subscribed_by_two_presenters.py`). The guards below are written with
**`ast`**, never with regular expressions (`BOT-133`: the regex version flagged the API's own
documentation). They live in `tests/unit/architecture/`.

| Guard | Rule | Allowlist |
| :--- | :--- | :--- |
| `test_module_boundaries.py` | `modules/X/**` may import only: `modules/X/**`, `modules/Y/contracts/**`, `support/*/contracts/**` (plus `support/ui_kit/**` and `support/charting/**` from `ui/`), `core/**`, the Engine, the standard library and third parties. `core/**` imports nothing from `modules/*` or `support/*` at runtime (`TYPE_CHECKING` blocks are ignored by every guard). `support/*` imports nothing from `modules/*`; it **may** import `core/contracts` (`ui_kit.PageShell` implements `IPlaceHost`). `shell/**` may import every `contracts/` and every `module.py`. **Strangler period (Phases 0–4):** the legacy tree `src/{domain,application,infrastructure,presentation}` may import `modules/*/contracts/**`, `core/**` and `support/**`; `modules/**` never imports the legacy tree except through the allowlist during its own phase | **Ratchet**: `allowlist_module_boundaries.txt` records the violations as they stand in Phase 0, one entry per `(importing_module, imported_module)` pair with **no line number** (ArchUnit's frozen-rule identity), so unrelated edits do not churn it; the test fails on any pair **outside** the allowlist **and** on any listed pair that no longer exists (shrinking is mandatory) |
| `test_module_domain_is_qt_free.py` | no runtime import of `PySide6` or `sagittarius_engine.extensions.pyside_mvc` under `modules/*/{domain,application}`, `core/**`, `support/indicators/**`; `TYPE_CHECKING` blocks ignored (that is how `core/contracts` names `QWidget` and `QtEventBridge`) | none |
| `test_module_declarations.py` | (a) every package under `modules/` appears in `shell/modules.py` and vice versa; (b) declared `dependencies` equal the set of modules whose `contracts/` are actually imported (surplus and shortfall both fail); (c) `register()` does not call `resolve()` (spying container); (d) no abstract type is claimed by two modules (`registrations()`); (e) `contribute()` calls no factory and imports no module under `modules/*/ui/widgets/` (`sys.modules` snapshot); (f) the UI map has no factory contributed to an unknown surface or place | none |

The existing layer guard (`architecture-rule` §3) is generalised in Phase 0, in the same pull
request, to the paths `modules/*/{domain, application, adapters, ui}`.

**The sanity tier gains zero tests** (`testing-rule.md` §1). Sanity already scans "every navigable
route, every screen package on disk"; surfaces and the `screen` contributions fit that scan as is.

## 6.2 Completion metrics — measured by script, written into each phase's pull request

| Metric | How it is measured | Phase 0 | 1 | 2 | 3 | 4 |
| :--- | :--- | :-: | :-: | :-: | :-: | :-: |
| Duplicated method names, `trading` ↔ `dashboard` | an AST script comparing Presenter / ViewModel / View member names | 59 | **0** | 0 | 0 | 0 |
| Lines in the boundary allowlist | `wc -l` | N (as found) | fewer | fewer | fewer | **0** |
| `presentation/ui/common/` | `ls` | 25 files | 16 | 13 | 12 | **deleted** |
| `binance_bot_module.py` | `wc -l` | < 750 | < 400 | < 250 | < 150 | **deleted** |
| Screens importing `infrastructure/` | the guard | 2 | 2 | 2 | 1 | **0** |
| Boundary allowlist entries (`(importing, imported)` pairs) | the guard | **10** (12 symbols, 10 statements, 10 files) | fewer | fewer | fewer | **0** |

## 6.3 Migration — Strangler Fig, with the Walking Skeleton first (ADR D5)

A **Strangler Fig** migration grows the new structure around the old one and retires the old one
piece by piece, so the application keeps running at every step. A **Walking Skeleton** is the
thinnest possible end-to-end slice built first, to prove that every layer connects before the
heavy pieces are moved.

| Phase | Task | Content | Does the app run? |
| :-: | :--- | :--- | :-: |
| 0 | `EPIC-025A` | `core/`, `shell/`, `BoundedContextModule`, `IContributionRegistry`, the three guards (allowlist = as found), `support/binance_gateway`, and **`modules/market_data`** end to end | ✅ Data Management plus CLI `sync` / `stream` |
| 1 | `EPIC-025B` | `modules/trading`; Trading and Dev Board become surfaces; the first `dev_probe`; the 59 duplicates removed | ✅ the user runs Testnet: manual orders, cancel, enable/disable, PnL |
| 2 | `EPIC-025C` | `modules/strategy` (Core); `claim_symbol`; `StrategyContext` in the right direction | ✅ arm / disarm / tick → order |
| 3 | `EPIC-025D` | `modules/backtesting`; the `PaperExchange` ACL; dead use cases deleted | ✅ backtests bit-identical |
| 4 | `EPIC-025E` | `support/{charting, indicators, ui_kit}`; `ui/common` and `binance_bot_module.py` deleted; settings becomes a surface; ADR D6 revisited | ✅ |
| 5 | `EPIC-025F` | Engine `EPIC-001D` / `TASK-043`; `ScreenRegistry` → `NavigationService`; the conformance suite | ✅ |

Constraints in every phase: one pull request; `ci-local.ps1 -Full` green (grep the log file);
**no change in business behaviour** (the declared exceptions: the default route, the `dev.mode` gate
including the backtest FPS overlay, and one shared `ConfigManager` so that headless `--dev`
starts working — §4.2 and the SDD); the regression tests for `BUG-112 / 116 / 117` stay green; the user runs
Testnet after Phases 1 and 2.

## 6.4 Risks

| Risk | Level | Handling |
| :--- | :-: | :--- |
| `TradingSessionState` is mutable and touched by 3 Presenters plus `trading_view_model.py`, **7** handlers (execute, enable, disable, cancel, emergency stop, arm, disarm), 4 services, the websocket thread and the composition root — about 20 source files (re-measured in round 3; the first estimate was half of that) | 🔴 | Phase 1: `trading` owns it; the outside sees only `TradingSessionSnapshot` and `TradingSessionChangedEvent`; `settings_presenter.py:143` stops reading it directly; the symbol lease lives under its existing lock |
| 3,020 test functions in 393 files mirror the old layout (re-counted in round 3) | 🟠 | moved phase by phase, in the same pull request as the code; tiers unchanged |
| `binance_bot_module.py` reborn as a god file in `shell/` | 🟠 | each module does its own `register()`; `shell/modules.py` is only a **list**; guard (a) |
| A new Engine API missing from the installed build | 🟡 | `engine_capabilities.py` (`BOT-133`) |
| The scheduler cannot cancel a job | 🟡 | `PositionRefreshService` already no-ops while the session is disabled; recorded for the Engine |
| Effort estimate | — | not yet reliable; only Phase 0 can be estimated. Re-estimate after Phase 0 |
