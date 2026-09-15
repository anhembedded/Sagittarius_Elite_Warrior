# EPIC-025 — Split the application into bounded-context modules on the Engine's `IExtension` microkernel

- **Status:** 🟡 **Phase 0 in progress** since 2026-09-13 (spec approved by the user after three
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
| **A** | [Phase 0 — mechanism plus `modules/market_data` (Walking Skeleton)](incomplete/EPIC-025A_phase0_mechanism_and_market_data.md) | — | 🟢 code complete (7 PRs merged, last #214); awaiting the user's app run |
| **B** | [Phase 1 — `modules/trading`; Trading and Dev Board become surfaces](incomplete/EPIC-025B_phase1_trading_and_surfaces.md) | A | 🟡 in progress — 1.1a (#217, #218) and 1.1b (#219) merged; allowlist 34 → 24 |
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
| **1.1c** | `interactive_shell.py` into `shell/`, with the CLI table no longer hard-coded — **moved into 1.3**, measured: 1.1b tried the move and reverted it. `exchange-status` is trading's handler and has no owning module until 1.3, so the shell must keep importing it from the legacy tree, which trades these 2 allowlist entries for 2 new lines in `baseline_shell_legacy_imports.txt` — one shrink-only ratchet growing so another can shrink. The allowlist's own comment carries the measurement | 2 | — |
| **1.2** | `ISymbolCatalog` + `IRangeCoverage`, completing HLD §3.4's published set for `market_data` (all five ports now published). **Four**, not six: the two `-> adapters` lines cannot go with them, and the allowlist comment says why — `exchange_session_factory` needs one factory per context, which is 1.3's with `modules/trading`, and `backtest_presenter`'s metadata-cache fallback needs the screen rebuilt, which is Phase 3 | 4 | low |
| **1.3a** | ✅ **The move.** `modules/trading` **behind its existing UI**: `domain/trading`, `use_cases/trading` (less arm/disarm), `use_cases/queries` and `application/ports` (both wholly trading's, measured), the trading half of `infrastructure/binance`, and the four trading services move in. Trading's value objects, order enums and the events it raises go to `contracts/`, which is what keeps 26 further entries out of the allowlist. No port published — see below for why that order is forced. Closes the five `application -> infrastructure` entries this guard was written for, by making the import intra-module | **+60** (20 → 80) | medium — a move, and `git diff -M` reads it as renames |
| **1.3b** | **The ports.** `IOrderSubmission`, `ITradingSession`, `IAccountSnapshot`, every consumer moved onto them, `LivePosition` → `PositionSnapshot` flattened, the shared `ExchangeSessionFactory` split one-per-context with the DI registrations following it, and 1.1c's two `interactive_shell` lines (`exchange-status` is trading's to declare by then). The symbol lease is **deferred to Phase 2**, where `strategy` is its first consumer (`architecture-rule` §7.2.1) | 67 (80 → 13) | **high** — `TradingSessionState` is mutable state read by 21 files, four of them presentation |
| **1.4** | Trading and Dev Board become the surfaces `surfaces/trading/` and `surfaces/dev_board/`: nested `QMainWindow`, contributed panels / dialogs / actions, perspective per user. **This is where 59 → 0 happens**, and where the 9 `ui/common` items used only by these two screens move | 0 | **high** — the largest UI change in the epic |
| **1.5** | The **Welcome** surface (ADR D13, D14) as the default route, the `dev.mode` toggle with Restart, and the first `dev_probe` (trading's Exchange API tester) | 0 | medium |

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
