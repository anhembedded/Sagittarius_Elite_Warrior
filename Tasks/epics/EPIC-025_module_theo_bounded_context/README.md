# EPIC-025 — Split the application into bounded-context modules on the Engine's `IExtension` microkernel

- **Status:** 🟡 **Phase 1 in progress**; Phase 0 ✅ closed 2026-09-15 (spec approved by the user after three
  rounds and an independent review; ADR D1–D22).
- **Repositories:** Elite (Phases 0–4) · Engine (Phase 5, tracked as `TASK-043` there, referencing
  `EPIC-001D`).
- **Origin:** [`PRO-004`](../../proposal/PRO-004.md) — the user (2026-09-10): *"hiện tại chúng ta
  không có chia module theo kiểu DDD, nên mọi thứ đang rất là lung tung và đạp chân lẫn nhau. Tui
  muốn redesign lại khá lớn."* ("Right now we have no DDD-style module split, so everything is
  messy and steps on everything else. I want a fairly large redesign.") Acceptance criterion:
  *"không ngại đập đi xây lại, không ngại risk, chỉ sợ bad design, không thể mở rộng, khó bảo trì"*
  ("not afraid to tear down and rebuild, not afraid of risk; only afraid of bad design, of not being
  able to extend, of being hard to maintain").
- **North star:** [`Docs/HLD/`](../../../Docs/HLD/README.md) — the official High-Level Design. This
  epic only summarises the decisions and divides the work into phases; it **does not repeat** the
  analysis or the evidence. Every sub-task reads the HLD and the ADR first.
- **Tracking (Gantt):** [`TRACKING.md`](TRACKING.md) — one bar per pull request and review, updated in the
  pull request that closes a bar.
- **How to execute a step (any AI):** [`.agents/Skills/epic-025.prompt.md`](../../../.agents/Skills/epic-025.prompt.md)
  — reading order, invariants with check commands, the per-step checklist, when and how to ask.
- **Absorbs:** [`EPIC-024C`](../EPIC-024_modularize_trading_core_va_giao_dich_thu_cong/cancelled/EPIC-024C_modularize_trading_core.md)
  (cancelled 2026-09-11; the reason is at the top of that file).

---

## 1. Decisions already made (in full: ADR D1–D12)

1. **Four bounded contexts** — `market_data` / `trading` / `strategy` (Core) / `backtesting` — plus
   **four support packages** — `charting` / `indicators` / `ui_kit` / `binance_gateway` — plus kernel
   services. Trading and Dev Board are **two legitimate screens**, and both are *composition
   surfaces* built from widgets the modules contribute; Dev Board is gated by `dev.mode` and gains
   a `dev_probe` contribution point for exploring unclear exchange APIs.
2. **A module is an Engine `IExtension`** plus two UI hooks (`contribute`, `subscribe`). No new `IModule`.
3. **The shell stays QtWidgets, with an explicit module list in `shell/`** and no auto-discovery.
4. **QtWidgets only, the OS theme, panels and dialogs instead of cards** (ADR D20–D22, HLD §11) —
   the UI of each module is rebuilt in the phase that migrates it; no separate UI epic.
5. **A Walking Skeleton inside a Strangler Fig**: `market_data` is migrated together with the
   mechanism in Phase 0; `trading` follows immediately, because that is where the 59 duplicates and
   the real bugs are.
6. **The Engine receives mechanism, the application keeps policy**; every new Engine API becomes a
   line in `engine_capabilities.py`.

## 2. Goals — measurable

| Metric | Today (measured 2026-09-10) | When the epic is done |
| :--- | :--- | :--- |
| Method / member names duplicated between `screens/trading` and `screens/dashboard` | **59** | **0** |
| Items in `presentation/ui/common/` | 25 files / 2,015 lines | the directory **no longer exists** |
| Lines in the composition root (`binance_bot_module.py`) | 750 | a module list in `shell/`, ≤ 100 lines |
| Screens importing `infrastructure/**` (violating `architecture-rule` §3) | 2 | 0 |
| Allowlist of module-boundary violations (`test_module_boundaries.py`) | = as found in Phase 0 | **empty** |
| New sanity-tier tests | — | **0** (`testing-rule.md` §1) |

## 3. Order of work

Each phase is **one pull request**, CI green, **the app running** (the user running Testnet is the
most effective bug channel — it must not be lost). No change in business behaviour (ADR D12).

| # | Task | Blocked by | Status |
| :-: | :--- | :--- | :---: |
| **A** | [Phase 0 — mechanism plus `modules/market_data` (Walking Skeleton)](completed/EPIC-025A_phase0_mechanism_and_market_data.md) | — | ✅ **closed 2026-09-15** — 8 PRs merged (last #214) and the user's own app run confirmed all four checks |
| **B** | [Phase 1 — `modules/trading`; Trading and Dev Board become surfaces](incomplete/EPIC-025B_phase1_trading_and_surfaces.md) | A | 🟢 **every pull request done** — 1.1a, 1.1b, 1.2, 1.3a, 1.3b, 1.3c (×5), 1.4a, 1.4b (×2), 1.4c (×4), 1.4d, 1.5 (×2); allowlist 34 → 23, QML 35 → 27. **Two things it does not close, both measured, both needing a decision:** the two screens cannot move into `modules/trading/ui/` until `support/ui_kit` and `support/charting` exist (Phase 4 — they need 24 and 44 imports from `presentation/ui/*`, and the seven `ui/common` feeds have only the two legacy Presenters as consumers), so the "59 duplicated members → 0" criterion stands at 59 with a ratchet on it; and the Dev Board's *screen* is not gated on `dev.mode` while it still carries manual order entry. **The first of those two is now being paid down inside this phase rather than waiting for Phase 4:** PR 1.6a starts `support/ui_kit` from its clean leaf (`assets/`), because every remaining route out of Phase 1 — the screens into `modules/trading/ui/`, `ui/common`, Phase 2's strategy cards — runs through that package |
| **C** | [Phase 2 — `modules/strategy` (Core domain)](incomplete/EPIC-025C_phase2_strategy.md) | B | 🔴 |
| **D** | [Phase 3 — `modules/backtesting`](incomplete/EPIC-025D_phase3_backtesting.md) | C | 🔴 |
| **E** | [Phase 4 — `support/*`; dissolve `ui/common/`](incomplete/EPIC-025E_phase4_support_and_dissolve_common.md) | D | 🔴 |
| **F** | [Phase 5 — Engine `EPIC-001D`: `NavigationService`, regions, screen lifecycle](incomplete/EPIC-025F_phase5_engine_navigation.md) | E · the Engine-side task | 🔴 |

## 3.2 Phase 0 as pull requests

| PR | Content | The user checks |
| :-: | :--- | :--- |
| 0.1 | safety net first, no app code: the duplicate-members script and its baseline, the boundary allowlist as found, the backtest golden master, the collected-test count, non-emptiness on every path-scanning guard, the no-new-QML ratchet | the allowlist entries; the golden-master dataset |
| 0.2 | the mechanism: `core/`, `shell/`, `BoundedContextModule`, registry, `DoubleClaimCheck`, `LegacyScreenAdapter`, one `ConfigManager`, the `dev.mode` gate; theme layer removed (OS theme) | the app opens as before, now in the OS theme |
| 0.3 | `support/binance_gateway` | — |
| 0.4a | `modules/market_data` end to end **behind its existing UI**: domain, application, contracts, adapters, the module registered in `shell/modules.py`, CLI `sync` / `stream`, contract suites and verified fakes. The Data Management screen keeps its current QML widgets and now consumes the module's contracts | CLI `sync` still syncs a symbol |
| 0.4b | Data Management rebuilt as QtWidgets (HLD §11): a `QTableView` panel with four `QAction`s and a kline-inspector `QDialog`; four `.qml` files deleted (**not** the time-range and timeframe pickers — those are shared with four other screens, EPIC-025A §1.7). The screen itself stays in the legacy tree until Phase 4: moving it needs `support/ui_kit`/`support/charting`, or it costs 35 imports pointing back at the legacy tree (EPIC-025A §1.8) | Data Management: sync a symbol, inspect klines |
| 0.5 | ✅ the skeleton walks: `IMarketDataSync` published with a frozen request DTO, a verified fake and an 11-guarantee contract suite; **four** consumers moved onto it, not the two this row planned — `chart_coordinator`, `stream_lifecycle_controller`, `data_sync_coordinator`, `sync_coordinator` — because all four were building the same command (allowlist 38 → 34). `BUG-120` fell out on the way: the fake's own query helper was verified by nothing | Trading chart still loads history; Dev Board Start Live still syncs |

## 3.3 Phase 1 as pull requests (cut 2026-09-14, after Phase 0's measurements)

`TRACKING.md` says the Phase 1+ bars are re-cut once Phase 0's numbers are in. They are, and the
answer is that Phase 1 cannot be one pull request either: `EPIC-025B` itself calls it **the
highest-risk phase of the epic**, and the measurements say why.

| Measured 2026-09-14 | Value |
| :--- | :--- |
| Member names duplicated `screens/trading` ↔ `screens/dashboard` | **59** (Phase 1's own "done when": → 0) |
| `screens/dashboard` | 15 files, **5,013 lines** — becomes a surface with *zero* business logic |
| `screens/trading` | 9 files, 2,467 lines — same |
| `domain/trading` + `use_cases/trading` + `infrastructure/binance` | 50 files, **3,693 lines** to move |
| Allowlist entries Phase 1 retires | **23 of 34** (see the split below) |

**The cut follows PR 0.5's shape, because that shape is now proven rather than argued:** publish
the port, move every consumer onto it, leave the code where it is; move the code in a later pull
request. 0.5 retired four allowlist entries with all four consumers still sitting in the legacy
tree, which is the property that makes each step independently shippable with the app running.

| PR | Content | Retires | Risk |
| :-: | :--- | :-: | :--- |
| **1.1a** | `IHistoricalKlines` — the first of the two ports `EPIC-025A` §1 assigns here, on PR 0.5's template, with the six readers of stored candles moved onto it. It removes `chart_coordinator._load_history`'s `getattr(response, "data", response)` probing (`architecture-rule` §2.1's forbidden shape) and three more guards like it | 6 | low — one module, six consumers, the template exists |
| **1.1b** | `IMarketStream` — the second of the two ports, with the trading chart and the Dev Board moved onto it. Split out of 1.1 **after** 1.1a was written, not planned that way: the consumer move alone touched 28 files and repaired 65 tests that a stubbed dispatcher had been keeping green, and a second port in the same diff would have doubled a review without adding a way for it to fail | 4 | low |
| **1.1c** | ✅ **Done as 1.3c-5, and not the way this row planned it.** The plan was to move `interactive_shell.py` into `shell/`; 1.1b tried that and reverted, measured — the move traded these 2 entries for 2 new lines in `baseline_shell_legacy_imports.txt`, one shrink-only ratchet growing so another could shrink. What retired them instead was the inversion `IContributionRegistry` already makes for panels: `BoundedContextModule.declare_cli()` + `shell/cli_registry.py`, module declares and shell collects, with the shell staying exactly where it is. `exchange-status` remains a hand-written entry there, because its handler formats through `presentation.enum_labels` and a module may not import the legacy tree — it goes when `EnumLabels` moves to `support/` in Phase 4 | 2 | — |
| **1.2** | `ISymbolCatalog` + `IRangeCoverage`, completing HLD §3.4's published set for `market_data` (all five ports now published). **Four**, not six: the two `-> adapters` lines cannot go with them, and the allowlist comment says why — `exchange_session_factory` needs one factory per context, which is 1.3's with `modules/trading`, and `backtest_presenter`'s metadata-cache fallback needs the screen rebuilt, which is Phase 3 | 4 | low |
| **1.3a** | ✅ **The move.** `modules/trading` **behind its existing UI**: `domain/trading`, `use_cases/trading` (less arm/disarm), `use_cases/queries` and `application/ports` (both wholly trading's, measured), the trading half of `infrastructure/binance`, and the four trading services move in. Trading's value objects, order enums and the events it raises go to `contracts/`, which is what keeps 26 further entries out of the allowlist. No port published — see below for why that order is forced. Closes the five `application -> infrastructure` entries this guard was written for, by making the import intra-module | **+60** (20 → 80) | medium — a move, and `git diff -M` reads it as renames |
| **1.3b** | ✅ **The ports published.** `IOrderSubmission`, `ITradingSession`, `IAccountSnapshot`, bound from inside the module, with Settings and both `exchange-status` entry points as the first consumers. Two things this row planned did **not** happen, both measured away: `LivePosition` → `PositionSnapshot` (the existing records are already frozen and flat, so the DTO would have been field-for-field identical) and the symbol lease (**deferred to Phase 2**, where `strategy` is its first consumer — `architecture-rule` §7.2.1) | 24 (80 → 56) | **high** — `TradingSessionState` is mutable state read by 21 files, four of them presentation |
| **1.3c** | ✅ **The consumers, in five slices.** One row here, five pull requests in fact, because the risks are different in kind and the first attempt at doing them together measured 72 failures: **1.3c-1** both big Presenters and `arm`/`disarm` onto `ITradingSession`; **1.3c-2** every order path onto `IOrderSubmission`, which gained a fourth method (`validate()`, the `/order/test` dry run) and took `submit_order` into the module; **1.3c-3** the Dev Board onto `IAccountSnapshot.open_positions()` plus a new `IEquityCurve`; **1.3c-4** the `ExchangeSessionFactory` split one factory per context, four pull requests after the allowlist first scheduled it; **1.3c-5** the CLI table as a contribution (1.1c). `TRACKING.md`'s status log carries each slice's own measurement | 33 (56 → 23) | **high**, and it was: see the reverted first attempt |
| **1.4** | Trading and Dev Board become surfaces on a nested `QMainWindow`: contributed panels / dialogs / actions, perspective per user. **This is where the duplicated presentation members were to go to their target** — they have not: 1.4d measured that the move needs Phase 4's `support/*` first, and put a ratchet on the number instead. **Four slices**, for the same reason 1.3c had five — the mechanism can fail without a screen, and each screen can fail without the other: **1.4a** ✅ the surface host itself (`workbench_surface.py` and `surface_building.py`, so `IPlaceHost` finally has an implementation — no screen moved; written in `shell/`, moved to `support/ui_kit` by 1.4b-1); **1.4b** Trading's positions and open-orders tables off QML-in-`QQuickWidget` onto `QTableView` panels the module contributes — in two steps, because the first one is a move and the second is UI: **1.4b-1** ✅ the host and its builder move to `support/ui_kit` behind a new `IContributionTable` read port (measured: a legacy screen and a module's `ui/` both have to render a surface, and the guard refuses `support -> shell` and `presentation -> shell` alike, so `shell/` was the one place neither could reach), **1.4b-2** ✅ the panels themselves — `QTableView` + `QAbstractTableModel` in `components/order_book/`, the 4 `.qml` files deleted (QML baseline 31 → 27, `qml_theme_refs` 204 → 188), the per-row "Huỷ" button replaced by one `QAction` with a confirmation. **Module ownership did not move with them, measured:** the legacy Presenters feed these tables through `set_positions`/`set_open_orders`, a legacy file may import a module only through `contracts/`, and a module-owned feed would need an authoritative open-orders read off the UI thread (`IAccountSnapshot` publishes positions only) — so `modules/trading/ui/` waits for the feed to move, which is 1.4d's with `ui/common`; **1.4c** the Dev Board becomes a surface, in three steps: **1.4c-1** ✅ what the host still needed before a real screen could move onto it (the environment-banner row — the one band every screen gets from its shell that nobody contributes; `IContributionTable.surface()`, so a renderer with only an id need not name the shell's surface list; `fill_surface()`, for a screen that built its own host), **1.4c-2** ✅ `DashboardView` onto the host — the `PageShell` and its one `QSplitter` are gone, the chart column is the central widget, and Positions / Open orders / Equity / Controls are docks with the log at the bottom and the ticker and websocket pill in the status bar, **1.4c-3** ✅ `DevBoardPanel` stopped being a widget: it builds the five cards and the View places each in its own dock, with the manual-order card as a dialog on `F9`; **1.4c-4** ✅ the first panel a module contributes: `trading`'s session probe on the Dev Board, plus the wiring that was missing under it — **nobody had ever called `contribute()`** — and the laziness guard `test_module_declarations.py`'s docstring had promised since PR 0.2; **1.4d** ✅ the duplication number got its **ratchet** — and the claim that it was stale was my own error, corrected here: `tools/measure_duplicate_members.py` shipped in Phase 0 and still measures exactly the **59** this epic claims (I had measured 34 with a narrower definition of my own — two Presenter *files* instead of the two screen packages, and without the "and in no third package" rule — before finding the committed tool, which is the "survey before you invent" rule catching me). What was missing was a guard, not a number: `test_presenter_duplication_only_shrinks.py` now holds 59 and the 132 across every pair, shrink-only. **The `ui/common` move itself waits for Phase 4**, measured: all seven files have exactly the two legacy Presenters as consumers, and a legacy file may import a module only through `contracts/` | 0 | **high** — the largest UI change in the epic |
| **1.5** | The **Welcome** surface (ADR D13, D14) as the default route, and the `dev.mode` toggle with Restart. Two steps: **1.5a** ✅ the surface itself — the first screen the shell owns, contributed as a `ScreenContribution` like every other, default route, and **Start** as an intent on the bus so *Main* decides where it goes; **1.5b** ✅ the developer-mode switch with Restart — and the Dev Board's *screen* deliberately **not** gated yet: measured, that screen still carries manual order entry and the strategy controls, `dev.mode` ships as `false`, so gating it now would take live manual trading away from the user until those controls have a home on the Trading surface. Its *surface* is gated already, so the switch does have a visible effect: the `trading` module's probe appears and disappears with it. The first `dev_probe` moved to 1.4c-4, where the contribution path it proves was built | 0 | medium |
| **1.6a** | ✅ **`support/ui_kit/assets/` — Phase 4's extraction starts, from the bottom.** Not in the original cut: Phase 1 closed with the two screens unable to move into `modules/trading/ui/` until `support/ui_kit` and `support/charting` exist, and both were scheduled for Phase 4 — so the epic's own "59 duplicated members → 0" criterion, and Phase 2's `strategy` cards after it, sit behind a package four phases away. Measured before cutting: `support/charting` **cannot** go first (`chart_card` imports `domain.indicator_scripts` and seven `presentation.ui.*` packages), while `assets/`, `kit/`, `qml/embed`, `qml/kit`, `theme_bootstrap.py` and `constants.py` import **only each other** — so `ui_kit` is extractable now, bottom-up, and `assets/` is its one clean leaf: 4 files whose imports are stdlib, PySide6, the Engine and itself, with 40 consumers. The move costs **zero** allowlist entries in either direction — a legacy file may import `support/**` whole (`rules.py::_legacy_may_import`), and nothing in `assets/` points back. Retargeted with it: the palette guard (now scanning **both** UI trees — scanning only one would stop watching the other's files), its row in `scanned_roots_registry.py`, the icon rule in `ui-presentation-rule.md`, `palette.prompt.md`, `tools/measure_app_styling.py`'s `PALETTE_MODULE`, and two test files to the `unit/support/ui_kit/assets/` mirror | 0 (it retires no allowlist entry — it unblocks the ones that need `ui_kit` to exist) | low — a move with no behaviour change (ADR D12), proven by 40 consumers still importing the same names |
| **1.6b** | ✅ **The widget `kit/` — 28 files, and what leaving `presentation/` turns on.** `assets/` going in 1.6a made `kit/` a leaf: re-measured, it depends on nothing inside `presentation/ui` at all, while 41 files outside it depend on `kit`, and `qml/kit`, `qml/DataTable`, `components/sidebar` and `components/environment_banner` each wait on it. Zero allowlist entries again, and the styling census is unchanged (149 / 27 / 188) — `style.py` and `page_shell.py` travel along and are still scheduled for deletion by HLD §11 / ADR D21, because a package is the unit that moves and splitting one across two trees mid-migration is worse than carrying two doomed files. **Two things the move switched on, both deliberate:** `pyproject.toml` excludes `src/presentation/` from mypy **wholesale** (the PySide6 `@Property` false-positive class, EPIC-002A §2), so crossing into `support/` put 28 files under the type checker for the first time — 3 errors, none of them that false-positive class, all fixed rather than re-excluded per `pyproject`'s own rule: a `QByteArray.data()` typed `bytes \| bytearray \| memoryview` where only the first has `.decode()`, and two size hints reading `self.layout()`, which is `QLayout \| None`, so the hints now read the layout the constructor built. And the `N802/N803/N815` per-file ignore for Qt overrides had to follow the widgets: without it the move would have had to rename 14 Qt overrides, a behaviour change dressed as a move. Three more guards retargeted, each probed by breaking it: the card-layer guard's relocated `_KIT_DIR` (its `test_the_kit_is_not_a_hiding_place` is what failed and said so), the same guard's scan widened to both trees — the legacy tree is down to **one** Card, so it was one move away from inspecting nothing — and the `QQuickWidget`/theme-seeding guard, whose two rules are about what the running application does and did not stop applying because a file crossed into `support/` | 0 | low — a move (ADR D12), with 3 typing fixes and 3 guard retargets named in the body |

Why each pull request has exactly one reason to fail: 1.1 and 1.2 are `market_data` work that
cannot break trading; 1.3a moves trading code with every consumer still calling it exactly as
before, so a regression is in the move and nowhere else; 1.3b changes how those consumers call it,
with the code already where it belongs; only then do the screens change shape, with every
dependency already a contract.

**A correction to this table, measured 2026-09-15.** Row 1.3 used to read *"publish the ports **and**
move the code"*, and the paragraph above used to say the ports come before the module — on PR 0.5's
proven shape (*publish the port, move the consumers, leave the code; move the code later*). For
`trading` that order is not merely riskier, it does not **build**:
`tests/unit/architecture/boundaries/rules.py` refuses the new tree any legacy import outside the
allowlist, and every type the three ports need — `OrderPreview`, `EnableTradingResult`,
`ExchangeConnectionStatus` — was in the legacy tree. `market_data` could publish a port at 0.5
only because PR 0.4a had already moved its code in; 0.5 was never the *first* step for a context,
it was the second. So 1.3a is trading's 0.4a and 1.3b is its 0.5, and the allowlist growing at
1.3a is the same repayment-in-advance 0.4a's jump from 8 to 41 was.

### The eleven entries Phase 1 does **not** retire

Data Management's eleven lines reach `market_data`'s database maintenance, gaps, scan, audit and
bulk sync. `EPIC-025A` §1.8 re-keyed eight of them to Phase 1 on the reasoning that *a port call
retires the entry wherever the file lives* — true mechanically, and wrong here, because HLD §3.4
marks every one of those operations **Internal**: its selection rule is that a port is public when
it has a consumer in **another module**, and theirs is the Data Management screen, which §1.8
sends into `modules/market_data/ui/` in Phase 4. Publishing seven ports to serve a consumer that
is about to move inside the module would publish internals to satisfy a counter.

**Decided:** they are re-keyed to **Phase 4**, retired by the screen move, which is where §1.8 was
already sending the screen. The allowlist file carries the reason. This keeps HLD §3.4's
public/internal split intact and leaves Phase 4's own "done when" — *the guard allowlist is
empty* (`EPIC-025E` §2) — as the only place that number is claimed.

## 3.1 Engine milestones (HLD §8 — the harvest)

| Step | Trigger | Content | Tracked in the Engine repository as |
| :-: | :--- | :--- | :--- |
| E0 | now | `ScheduledJob.cancel()` | note on `TASK-043` |
| E1 | after **B** | lift `BoundedContextModule`, `IContributionRegistry`, descriptors, `Place`, `SizeHint` | `TASK-043` items 2, 5 |
| E2 | after **C** | lift the surface runtime (region host, per-place models) | `EPIC-001D` objective 2 |
| E3 | with **F** | `NavigationService`, screen lifecycle + conformance suite, `create_quick_widget(import_paths=)` | `TASK-043` items 1, 3; `EPIC-001D` objectives 3–5 |

Each lift = one Engine PR (`b` bump) + one app PR (delete the copy, add the
`RequiredEngineCapability`). The lift criterion is HLD §8.3; a lift that does not meet it waits.

## 4. Deliberately out of scope

- No microservices or multiple processes; no hot reload; no third-party plugins (every module is
  first-party, so no public semantic versioning of contracts).
- No one-database-per-module — the SQLite store stays shared; each module owns a **schema namespace**.
- No change to `EPIC-016`'s `ScreenRegistry` / `AbstractScreenModule` before Phase 5.
- A designed colour theme: deferred (ADR D21) — the OS theme until then.
