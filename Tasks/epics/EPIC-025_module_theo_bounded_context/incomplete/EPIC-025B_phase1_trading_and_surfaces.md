# EPIC-025B — Phase 1: `modules/trading`; Trading and Dev Board become composition surfaces

- **Status:** 🟡 In progress. The two `market_data` ports this phase was given are **done** — PR
  1.1a `IHistoricalKlines` (#217, plus its review cleanup #218) and PR 1.1b `IMarketStream` (#219)
  — as is PR 1.2 (`ISymbolCatalog`, `IRangeCoverage`, #220), which completed `market_data`'s
  published set. **Every pull request this phase planned is done**: 1.3a (`modules/trading` exists),
  1.3b (the three ports), 1.3c-1..1.3c-5 (every consumer onto them, the factory split, the CLI
  inversion), 1.4 (the surfaces), 1.5 (Welcome and developer mode) and 1.6a–1.6g, which started
  Phase 4's `support/*` extraction early because `ui_kit` and `charting` had to exist before the two
  screens could move. What is left is in §2 and is **not code**: the user's Testnet run, and the
  duplication criterion the user carried out of this phase. The pull-request cut and what each one
  retires live in the epic [`README`](../README.md) §"the cut"; `TRACKING.md` carries the per-PR
  log, which is the only place a per-PR number is safe to read.
- **1.3 was cut in two, and the halves are in the order the guard allows, not the order first
  proposed.** The epic's table had 1.3 publishing three ports *and* moving the code in one pull
  request, ~3000–4900 lines over the live-order path. Splitting it was the user's call
  (2026-09-15); putting the **move first** was forced by measurement:
  `tests/unit/architecture/boundaries/rules.py` refuses the new tree any legacy import outside the
  allowlist, and all three ports need types that were in the legacy tree — `IOrderSubmission` needs
  `OrderPreview`, `ITradingSession` needs `EnableTradingResult`, `IAccountSnapshot` needs
  `ExchangeConnectionStatus`. `market_data` could publish `IMarketDataSync` at PR 0.5 only because
  PR 0.4a had already moved its code in. So **1.3a is trading's 0.4a** (the move, allowlist 20 →
  80) and **1.3b is its 0.5** (the ports, allowlist → 13).
- **Repository:** Elite
- **Blocked by:** A · **Blocks:** C
- **Read first:** HLD §3.4 (the contracts of `trading`), §4.2–§4.5 (the Trading and Dev Board
  surfaces, `dev_probe`); ADR D4, D12. **The highest-risk phase of the epic**: `TradingSessionState`
  is mutable state shared by three Presenters, three handlers and the websocket thread.

## 1. What to do

1. ✅ **PR 1.3a** — `modules/trading/`: today's `domain/trading`, `use_cases/trading` (except
   arm/disarm, which go to `strategy` in Phase 2 and are kept on the allowlist until then),
   `use_cases/queries` and `application/ports` (both were **entirely** trading's, measured — the
   cut was cleaner than this line assumed), the trading side of `infrastructure/binance` (futures
   REST and the user-data stream), `PositionRefreshService` (`BUG-117`), `PositionStateReconciler`,
   `EquityCurveRecorder` and `TradingSessionState` — `trading` **owns** the positions read model.
   Trading's own value objects, the six order enums, `FuturesSymbolMetadata` and the seven events
   it raises went into `contracts/` rather than `core/vo`, on HLD §2.4's rule measured the same way
   `SymbolMarketMetadata` was: a type reaches the Published Language on two consumers in two
   *modules*, and until `strategy` exists trading is the only module among its importers. That
   choice is why 26 would-be allowlist entries do not exist — the legacy tree may import
   `modules.*.contracts` freely. Credentials handling stayed: `IExchangeCredentialsProvider` is
   `support/binance_gateway`'s, not trading's.
   **Not done in 1.3a, and written down rather than dropped:** the DI registrations stay in
   `binance_bot_module.py`, because `ExchangeSessionFactory` is built once and that one instance
   answers both this context and `market_data` — moving them means two factories where there is
   one, a behaviour change ADR D12 keeps out of a move. `module.py`'s docstring carries the whole
   argument; 1.3b splits the factory one-per-context and the registrations follow it.
2. `contracts/`: `IOrderSubmission`, `ITradingSession` (including `claim_symbol` /
   `release_symbol`), `IAccountSnapshot`; the DTOs `PositionSnapshot`, `OpenOrderSnapshot`,
   `TradingSessionSnapshot`, `AccountSnapshot`; the existing events `OrderFilledEvent`,
   `PositionChangedEvent`, `PositionClosedEvent`, `EquitySampledEvent` (names unchanged — a rename
   is not a pure refactor) plus the new `TradingSessionChangedEvent`; `contracts/errors/` with
   `SymbolAlreadyLeased`.
3. Contributed widgets (HLD §11, QtWidgets, OS theme): the positions and open-orders **panels**
   (`QTableView` on the existing view models), the session **status tile** and the Enable /
   Disable / Emergency-stop **actions** (one `QAction` each, on the toolbar), the equity **panel**,
   the **Order dialog** (F9; Dev Board only per D15), and the chart as the trading **central
   widget** — **one** factory each, returning a panel (View + Presenter that owns its
   Coordinators), under `modules/trading/ui/{panels,dialogs}/`. Two surfaces → two instances; no
   Coordinator in DI (ADR D12). `ITradingSession` gains the symbol lease under the existing lock. `trading` keeps only the
   exchange's part of sizing — lot/tick rounding and `TradingLimitPolicy` — and its import of
   `MarginRiskPolicy` stays on the allowlist until Phase 2 (ADR D17).
4. `screens/trading` and `screens/dashboard` become the **modes** `surfaces/trading/` and
   `surfaces/dev_board/`: each a nested `QMainWindow` with dock areas, toolbars and a status bar,
   a perspective saved per user, widget registration by contribution only, **zero business logic**. Dev Board is
   gated by `dev.mode` and hosts `dev_probe`s; the first probe is trading's "Exchange API tester",
   which calls the real adapter.
5. The 9 items in `ui/common/` used only by these two screens move into `modules/trading` (the
   strategy-related ones move in Phase 2).
6. The **Welcome** surface (ADR D13, D14): `shell/surfaces/welcome/` — app name and version, the
   environment banner, a **Start** button raising `StartRequested`, and a **Developer mode** toggle
   that writes `dev.mode` to `user_config.json` and offers **Restart now** (`QProcess.startDetached`
   of the same executable and arguments, then quit). Welcome becomes the default route; Dev Board's
   `is_default` is removed, and the `dev_board` surface plus every `dev_probe` register only when
   `dev.mode` is true at boot (`--dev` still wins for that run).
7. The manual-order card is contributed to `dev_board.rail` only (ADR D15); a unit test constructs
   it outside Dev Board with only `trading`'s ports, proving that adding `trading.rail` later is a
   one-line change.

## 2. Done when

- ~~The script counting duplicated member names between `trading` and `dashboard` reports
  **59 → 0**~~ — **carried out of Phase 1 by user decision 2026-09-16**
  ([`DECISION_2026-09-16`](../DECISION_2026-09-16_the_duplication_criterion_waits.md)).
  `test_presenter_duplication_only_shrinks.py` holds it shrink-only, and
  `tests/unit/architecture/baseline_presenter_duplication.json` is where the current figure lives —
  read it there rather than from this sentence. It stood at 59 from `PRO-004` until **PR 2.1e**,
  which extracted `StrategyCardViewModel` out of the two live view models and took the pair to
  **39** (and the whole-app census 132 → 115) — the first fall in that number, and it came from
  Phase 2 rather than Phase 1, which is exactly what carrying the criterion out predicted. The
  number goes to zero when both screens reach `modules/trading/ui/`, and after PRs 1.6a–1.6g that
  move was
  measured at 42 remaining legacy imports, of which 31 could go now and **11 could not**: six are
  QML packages ADR D21 **deletes** in Phase 4 rather than moves, four are
  `components/strategy_params`, which needs `BaseStrategy` from Phase 2's `modules/strategy`, and
  one is `components/strategy_overlay`. Reaching zero early therefore meant writing those 11 as
  **new** lines in a shrink-only allowlist — spending the epic's one invariant to hit a number
  four pull requests early — so the criterion waits for the work it is actually blocked on
  instead. It is still counted and still guarded; it is no longer Phase 1's gate.
- The user runs Testnet: placing a manual order, cancelling, enabling and disabling trading, PnL
  updating — all behave as before (the regression tests for `BUG-112 / 116 / 117` stay green).
- The app opens on Welcome; Start lands on Trading; with `dev.mode=false` **no probe is
  constructed**; the toggle plus restart brings the probes back. ✅ done by PRs 1.5a–1.5b, proven
  by `tests/unit/shell/test_contribution_assembly.py::test_a_gated_surface_drops_the_contribution_and_the_app_still_boots`
  and `tests/integration/presentation/ui/test_main_window_state.py`.

  **The half of this line that said "the sidebar shows no Dev Board" is struck, and it is a
  contradiction this list had with the spec rather than work left undone.**
  [`SPEC-011`](../../../Docs/SPEC/SPEC-011_start_the_app_and_choose_developer_mode.md) §6 states the
  opposite as a *promise*: the Dev Board screen is always present, only its contributed probes
  follow the switch — because the screen still carries manual order entry and the strategy
  controls, and **nothing on the Trading surface carries them**. Measured, not assumed:
  `grep -rn "manual_order" src/presentation/ui/screens/trading/` is empty, while
  `dashboard_presenter.py` holds the manual-order action, its ownership tracker and the
  armed-symbol block reason. So gating the screen today removes a capability the actor has, which
  ADR D12 forbids as an undeclared behaviour change and which no amount of test coverage makes
  acceptable.

  What it is really blocked on, therefore, is not a gate but **a home on the Trading surface for
  manual order entry and the strategy controls** — a feature placement, and the user's call, not a
  measurement. It travels with the screens into `modules/trading/ui/`, which
  [`DECISION_2026-09-16`](../DECISION_2026-09-16_the_duplication_criterion_waits.md) put in Phase
  2 + Phase 4.

  The mechanism for it is designed and measured, so that step is a small one when it comes:
  `ContributionRegistry.contribute()` already evaluates `surface_is_open()` for a **panel**, and
  `contribute_screen()` evaluates nothing at all — so a `ScreenContribution` gains the
  `surface_id` of the surface it hosts (every one of the six has exactly one: `welcome`,
  `trading`, `dev_board`, `settings`, `backtest`, `data_management`, and the route is *not* it —
  the Dev Board's route is `dashboard`), and the registry reuses the same evaluator. One gate
  concept, one evaluator, and a second gated screen later is one line in `SURFACES`
  (`architecture-rule.md` §7.2.1 — a seam, not a variant). Three tests in
  `test_screen_wiring.py` pin today's five routes at `dev_mode=False` and become parametrised over
  the flag at that point.
