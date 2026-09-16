# EPIC-025B — Phase 1: `modules/trading`; Trading and Dev Board become composition surfaces

- **Status:** 🟡 In progress. The two `market_data` ports this phase was given are **done** — PR
  1.1a `IHistoricalKlines` (#217, plus its review cleanup #218) and PR 1.1b `IMarketStream` (#219)
  — as is PR 1.2 (`ISymbolCatalog`, `IRangeCoverage`, #220), which completed `market_data`'s
  published set. **PR 1.3a is done: `modules/trading` exists.** Next is PR 1.3b (the three ports),
  then 1.4 (the surfaces) and 1.5 (Welcome). The pull-request cut and what each one retires live in
  the epic [`README`](../README.md) §"the cut"; `TRACKING.md` carries the per-PR log.
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
  ([`DECISION_2026-09-16`](../DECISION_2026-09-16_the_duplication_criterion_waits.md)). It stands
  at 59 with `test_presenter_duplication_only_shrinks.py` holding it shrink-only. The number goes
  to zero when both screens reach `modules/trading/ui/`, and after PRs 1.6a–1.6g that move was
  measured at 42 remaining legacy imports, of which 31 could go now and **11 could not**: six are
  QML packages ADR D21 **deletes** in Phase 4 rather than moves, four are
  `components/strategy_params`, which needs `BaseStrategy` from Phase 2's `modules/strategy`, and
  one is `components/strategy_overlay`. Reaching zero early therefore meant writing those 11 as
  **new** lines in a shrink-only allowlist — spending the epic's one invariant to hit a number
  four pull requests early — so the criterion waits for the work it is actually blocked on
  instead. It is still counted and still guarded; it is no longer Phase 1's gate.
- The user runs Testnet: placing a manual order, cancelling, enabling and disabling trading, PnL
  updating — all behave as before (the regression tests for `BUG-112 / 116 / 117` stay green).
- The app opens on Welcome; Start lands on Trading; with `dev.mode=false` the sidebar shows no Dev
  Board and no probe is constructed (asserted by a test that counts constructed factories); the
  toggle plus restart brings Dev Board back.
