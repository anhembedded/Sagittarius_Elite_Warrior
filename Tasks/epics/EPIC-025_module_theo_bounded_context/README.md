# EPIC-025 — Split the application into bounded-context modules on the Engine's `IExtension` microkernel

- **Status:** 🔴 Backlog — spec round 1 completed 2026-09-11; **no sub-task starts** until question
  ❓ O1 in the [ADR](DECISION_2026-09-11_module_boundaries.md) §3 is answered (round 2).
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
4. **A Walking Skeleton inside a Strangler Fig**: `market_data` is migrated together with the
   mechanism in Phase 0; `trading` follows immediately, because that is where the 59 duplicates and
   the real bugs are.
5. **The Engine receives mechanism, the application keeps policy**; every new Engine API becomes a
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
| **A** | [Phase 0 — mechanism plus `modules/market_data` (Walking Skeleton)](incomplete/EPIC-025A_phase0_mechanism_and_market_data.md) | ❓ O1 (round 2) | 🔴 |
| **B** | [Phase 1 — `modules/trading`; Trading and Dev Board become surfaces](incomplete/EPIC-025B_phase1_trading_and_surfaces.md) | A | 🔴 |
| **C** | [Phase 2 — `modules/strategy` (Core domain)](incomplete/EPIC-025C_phase2_strategy.md) | B | 🔴 |
| **D** | [Phase 3 — `modules/backtesting`](incomplete/EPIC-025D_phase3_backtesting.md) | C | 🔴 |
| **E** | [Phase 4 — `support/*`; dissolve `ui/common/`](incomplete/EPIC-025E_phase4_support_and_dissolve_common.md) | D | 🔴 |
| **F** | [Phase 5 — Engine `EPIC-001D`: `NavigationService`, regions, screen lifecycle](incomplete/EPIC-025F_phase5_engine_navigation.md) | E · the Engine-side task | 🔴 |

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
- Per-module QML: deferred (ADR D6).
