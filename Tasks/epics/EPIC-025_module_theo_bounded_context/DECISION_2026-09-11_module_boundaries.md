# ADR — Module boundaries by bounded context, on the Engine's existing `IExtension` microkernel

**Epic:** [`EPIC-025`](README.md)
**Source:** [`PRO-004`](../../proposal/PRO-004.md) · The official design: [`Docs/HLD/`](../../../Docs/HLD/README.md)
**Date:** 2026-09-11
**Status:** 🟢 **Approved — rounds 1 and 2**; **round 3 applied 2026-09-13** after an independent
design review ([`Tasks/reports/EPIC-025_design_review.md`](../../reports/EPIC-025_design_review.md)),
see §7. O4 decided as **D17** (2026-09-13). Open: O2 (Engine API, Phase 5) only.

> [!IMPORTANT]
> Read the status column, not the prose (the convention of `EPIC-016`'s ADR).
>
> | Label | Meaning |
> | :--- | :--- |
> | ✅ **Established** | Confirmed on the real code tree; cited as `file:line` |
> | 🔵 **Proposed** | Settled in the review session; **not yet** implemented |
> | 🟢 **User decision** | Decided by the user directly; quoted verbatim, then translated |
> | 🤖 **Agent decision** | Delegated by the user (*"hãy dựa vào rule tự ra quyết định mà ra quyết định"* — "decide it yourself, based on the decision rule") and decided under `ONBOARDING.md` §7: a named pattern, broad precedent, no fear of redesign |
> | ❓ **Open** | Blocks the implementation of the phase named alongside until answered |

---

## 1. Context — the user's three questions and three lines of measured evidence

The user posed the problem as exactly three questions (2026-09-10): **where to cut** (macro —
strategic DDD), **how each piece is organised inside** (micro — Clean Architecture), and **how to
plug pieces into an application whose number of modules is not known in advance** (plugin —
Microkernel and the Dependency Inversion Principle; Robert Martin's "Main" component). The
acceptance criterion, verbatim: *"không ngại đập đi xây lại, không ngại risk, chỉ sợ bad design,
không thể mở rộng, khó bảo trì"* ("not afraid to tear down and rebuild, not afraid of risk; only
afraid of bad design, of not being able to extend, of being hard to maintain").

Evidence measured on `src/` (664 files, 74,371 lines), detailed in `PRO-004` §1–§2 and drawn in
[`as_is.puml`](../../proposal/PRO-004_assets/as_is.puml):

- Screens importing another screen's internals: **0**. The disease is **not** "imports everywhere". ✅
- **59** method and member names duplicated between `screens/trading` and `screens/dashboard`; 9
  items in `ui/common/` are used by exactly those two screens. ✅
- `binance_bot_module.py` is **750 lines** and the only registration point for every service; no
  unit of code owns a bounded context. `BUG-117`, `BUG-112` and `BOT-126` are the price already
  paid. ✅

---

## 2. Decisions

### D1 — Cut by bounded context: four business modules, three support packages, a kernel 🟢 User decision

The user approved the cutting criteria (HLD §1, C1–C6) and the context map (HLD §2): *"1. OK"*.

| Kind | Unit | Distillation |
| :--- | :--- | :--- |
| Bounded context | `strategy` | **Core domain** — the reason the app exists |
| Bounded context | `trading`, `market_data`, `backtesting` | Supporting |
| Support (technical, no business language) | `charting`, `indicators`, `ui_kit`, `binance_gateway` | Generic |
| Kernel service (injected, never a module) | DI, bus, config, log, threads, scheduler, navigation, health | — |

`strategy` is **separated from** `trading`; the cost of keeping them merged was `BUG-112`.
Account/Equity **deliberately** stays inside `trading` until a second real consumer appears
(`architecture-rule.md` §6.3).

### D2 — The module contract is the Engine's `IExtension` + `ExtensionDescriptor`; **no** new `IModule` 🤖 Agent decision · ✅ Established

The Engine already has `IExtension` (register / boot / shutdown), `ExtensionDescriptor(dependencies,
optional_dependencies, priority)` and an `ExtensionManager` with topological sort, fail-fast on
cycles and rollback; the Engine's own `IModule` / `BaseModule` are **legacy**. A third contract
would mean three module concepts side by side (`IExtension`, the legacy `IModule`,
`AbstractScreenModule`) — exactly the kind of bad design the user fears. A bounded-context module is
an `IExtension` plus two application-side UI hooks (`contribute`, `subscribe`) — HLD §3.1.

### D3 — The shell stays QtWidgets; the module list is **explicit** in `shell/`; no auto-discovery 🤖 Agent decision · ✅ Established

- `qml-rule.md` §0: *"QML can be nested inside QtWidgets. Qt does not support the reverse"* — the
  shell and the chart are QtWidgets permanently. The `StackView` of the original sketch becomes
  `QStackedWidget` (already present through `PresenterManager`). A microkernel does not require a
  QML shell.
- `EPIC-017` rejected auto-discovery. The module list is **code** in `shell/` (Martin's "Main"),
  with a two-way guard: every package under `modules/` is in the list, and every list entry exists
  on disk.

### D4 — Trading and Dev Board are **two legitimate screens**, and both are *composition surfaces* 🟢 User decision

Verbatim: *"Trading là màn hình use-case thật, còn Dev Board chỉ là màn hình để developer test and
discover API. Nên có nhiều cái tụi nó sẽ trùng lặp."* ("Trading is the real use-case screen; Dev
Board is only the screen where the developer tests and discovers APIs. So a lot of what they show
will overlap.") And: *"'discover API' → có nghĩa là khi bạn dev nếu API nào của sàn chưa rõ, thì sẽ
tạo 1 UI để test API đó."* ("'discover API' means: while developing, if some exchange API is
unclear, you build a UI to try that API out.")

Design consequences (HLD §4):
- **Neither** screen contains business logic. Both *lay out* widgets that modules **contribute**;
  there is one `_run_enable`, one `LiveOrderBookCoordinator`, one owner of the positions read model.
- Dev Board is gated by `dev.mode` and gains a contribution point **`dev_probe`**: a module that
  needs to explore an unclear exchange API contributes a probe widget that calls the module's own
  real port or adapter and shows the raw request and response. A probe is **the module's** code
  (`modules/X/ui/dev_probes/`), not Dev Board's — Dev Board is only where it hangs.
- "59 duplicates → 0" is the **completion criterion** of Phase 1, measured by a script, not by
  impression.

### D5 — Migration order: a Walking Skeleton inside a Strangler Fig 🤖 Agent decision

The user: *"Tôi không chắc, tôi đâu có bỏ công điều tra, bạn mới là người làm việc đó."* ("I am not
sure — I did not do the investigation, you did.")

| Phase | Content | Why here |
| :-: | :--- | :--- |
| 0 | Mechanism: `core/`, `BoundedContextModule`, `IContributionRegistry`, the three guards (allowlist as found), `shell/` listing the modules; **plus `modules/market_data`** | Walking Skeleton: `market_data` is the **thinnest context that touches every channel** (persistence, REST, websocket, one screen, CLI), so it proves the pattern end to end at the lowest risk |
| 1 | `modules/trading`; Trading and Dev Board become surfaces | Removes the 59 duplicates earliest; it is where real bugs are being found (`BUG-111` → `117`) |
| 2 | `modules/strategy` | The Core domain, separated from a `trading` that is already a surface |
| 3 | `modules/backtesting` (12,309 lines of UI) | Depends only on the `contracts/` of `market_data` and `strategy` |
| 4 | `support/{charting, indicators, ui_kit}`; `ui/common/` dissolved | After every consumer is a module |
| 5 | Engine `EPIC-001D` (`NavigationService`, regions, screen lifecycle) | Phases 0–4 **do not need** new navigation — today's `ScreenRegistry` suffices |

Each phase is one pull request, with CI green and the app **running** (the most effective bug
channel is the user running Testnet; it must not be lost).

### D6 — Per-module QML: **deferred**; `src/presentation/ui/qml/` remains the official place 🔵 Proposed

Letting a module own its QML requires (a) an explicit amendment of `qml-rule.md` §0.2 (the
`EPIC-003` precedent for amending a rule) and (b) a per-`QuickSurface` import-path mechanism on the
Engine side (today each `QQuickWidget` creates its own `QQmlEngine` inside `create_quick_widget()`
with one hard-coded import path). No consumer is blocked by its absence → revisit in Phase 4/5 when
the Engine does `EPIC-001D`. Meanwhile: a widget's Python wrapper lives in the module; the `.qml`
file stays under `qml/<Widget>/`.

### D7 — Tests stay organised by **tier** (`tests/{unit, integration, sanity}`), mirroring the module path inside each tier 🤖 Agent decision

`ci-local.ps1`, `testing-rule.md` and the sanity tier are all built on tiers. Co-locating
`modules/X/tests/` pays off only when a module really leaves the repository, which nothing needs
yet. The choice is **reversible** later and blocks no phase. The sanity tier **gains no tests**
(`testing-rule.md` §1).

### D8 — `EPIC-024C` is absorbed into `EPIC-025` → `cancelled/` 🔵 Proposed

The scope of 024C (Market Connector / Market Order / Strategy Engine) is a **subset** of D1; doing
it separately would build the module mechanism twice (`ONBOARDING.md` §12.5.1 forbids that). The
reason is written at the top of the 024C file.

### D9 — `core/vo` is called a **Published Language**, not a "Shared Kernel" ✅ Established

`architecture-rule.md` defines the Shared Kernel as **exactly two Engine symbols** (`IDomainEvent`,
`BaseEvent`), and a test locks that. Reusing the term for something else would break a rule that
is already enforced. Admission to `core/`: only a type with at least two consumers in two different
modules.

### D10 — The Engine receives **mechanism**, the application keeps **policy** 🟢 User decision + ✅ Established

The user: *"Tôi muốn Engine hỗ trợ scalable nhiều context/screen, vì Engine đó sẽ là core engine
trong sự nghiệp của tôi, tôi sẽ tái sử dụng cực nhiều."* ("I want the Engine to scale to many
contexts and screens, because that Engine will be the core engine of my career; I will reuse it
enormously.") The Engine's `ui-architecture.md` §1: *"Runtime — Engine owns: Shell, regions,
navigation, screen lifecycle"*; `EPIC-001D` (backlog) has planned exactly this since 2026-08-23. No
parallel build on the application side. Every new Engine API becomes one line in
`engine_capabilities.py` (`BOT-133`). The detailed split: HLD §5.

### D11 — Enforcement: three AST guards; the allowlist **may only shrink** 🔵 Proposed

`test_module_boundaries.py`, `test_module_domain_is_qt_free.py`, `test_module_declarations.py`,
written with `ast` (the `BOT-133` lesson: a regex matched the API's own documentation). The
violations as found are recorded in Phase 0; each phase shrinks the list; the test fails if it grows.

### D12 — Migration constraint: pure refactoring, no change in business behaviour ✅ Established

Inherited from `EPIC-024C` §4: *"modularize là đổi ranh giới code, không đổi logic nghiệp vụ"*
("modularising changes code boundaries, not business logic"). Coordinators remain owned by their
Presenter and injected through the constructor — never DI-discovered (`async-ui-action-rule.md` §2).

---

## 3. Still open — and what each blocks

| # | Question | Blocks | Answered in |
| :-: | :--- | :-: | :--- |
| ❓ O1 | The **final** list of contribution-point kinds and the schema of each | Phase 0 (`IContributionRegistry`) | Round 2 — HLD §4 is a draft |
| ❓ O2 | The concrete Engine API for `NavigationService` and regions (`EPIC-001D`) | Phase 5 | Round 2 — the Engine-side task |
| ❓ O3 | Per-module QML (D6) | nothing | Phase 4/5 |

---

## 4. Consequences

- `binance_bot_module.py` shrinks to a **module list** in `shell/` — no longer a god file.
- `presentation/ui/common/` **disappears** in Phase 4: the 9 items used only by trading and
  dashboard go to `modules/trading` / `modules/strategy`; the 5 genuinely shared items go to
  `support/ui_kit` or the kernel.
- `EPIC-016`'s `ScreenRegistry` / `AbstractScreenModule` **stay unchanged** until Phase 5 — modules
  contribute screens through exactly that mechanism.

---

## 5. Addendum 2026-09-12/13 — build-or-buy survey (HLD §7) 🟢 User decision

The user asked whether anything we plan to build already exists; HLD §7 records the survey, with
`tach` and `import-linter` run against the real tree. The user's decision (2026-09-13): *"keep the
plan the same, not substitute with lib"*. Consequences:

- D11 stays as written — hand-written `ast` guards. The twelve violations the trial run found are
  the Phase 0 allowlist. `TASK-043` item 4 (the Engine's generalised `import_boundary`) stays.
- Everything surveyed is reference only: PySide6-QtAds (regions), ccxt (a second venue),
  nautilus_trader (the backtest-equals-live reference), finplot (charting), lato and pluggy
  (module patterns). None is a dependency of this epic.
- The one small Engine addition without a dependency, `ScheduledJob.cancel()`, is noted on
  `TASK-043`.

---

## 6. Round-2 decisions, 2026-09-13 🟢 User decision

These answer the three questions HLD §4.2 and §4.5 had left open. Each is a change in
**user-visible behaviour** and is therefore recorded as the user's decision, verbatim.

### D13 — A Welcome (launch) screen is the first screen; it is owned by the shell

Verbatim: *"thêm 1 module màn hình login đơn giản, hiện tên app đẹp đẹp, có cái nút 'login' hay
start... gì đó là được. tôi muốn 1 màn hình giữ chân á mà."* ("add a simple login-screen module:
show the app name nicely, with a 'login' or 'start' button or the like. I want a screen that
greets and holds the user.")

- A new surface `shell/surfaces/welcome/`: the app name and version, the environment banner
  (venue), one primary action **Start**, and the dev-mode switch of D14. It is the **default
  route**; Start navigates to Trading. Dev Board is no longer the default (it was
  `is_default = True`).
- By the workbench rule (HLD §4.6) this is a **shell surface, not a bounded-context module**: it
  is about the application itself, like Settings; it owns no business language and no data.
- The primary action is named **Start**, not "Login", until there is something to authenticate
  (`domain-truth-rule.md`: the UI promises only what the engine delivers — there are no user
  accounts today; exchange credentials live in `secrets.local.json`). The surface is designed so
  that a real login (profile selection, credential unlock) can replace the button later without
  moving anything else: the button dispatches a single `StartRequested` intent that the shell
  handles.

### D14 — Dev Board is hidden unless `dev.mode`; the Welcome screen has the switch; a restart applies it

Verbatim: *"Dev Board ẩn khi dev mode, màn hình login có nút để switch dev mode, có thể cần
restart để enable load module."* ("Dev Board is hidden by dev mode; the login screen has a button
to switch dev mode; a restart may be needed to enable loading the module.")

- The `dev_board` surface and every `dev_probe` are registered **only when `dev.mode` is true at
  boot** (today `dev.mode` gates nothing on Dev Board — measured in HLD §4.2).
- The Welcome screen shows a **Developer mode** toggle. Toggling writes `dev.mode` to the writable
  `user_config.json` (the app's existing config mechanism, `BUG-117` follow-up) and shows "takes
  effect after restart" with a **Restart now** button. Restart relaunches the same executable and
  arguments (`QProcess.startDetached` + quit) — the standard desktop pattern; no hot-loading of
  modules (ADR "deliberately out of scope": no hot reload).
- `--dev` on the command line keeps working and still wins over the file for that run.

### D15 — No manual-order card on Trading; the design keeps the door open

Verbatim: *"không có nhé, nhưng phải thiết kế cân nhắc lỡ sau này có thể mở rộng."* ("no — but
the design must allow extending it later.")

- The manual-order card stays a `trading`-owned widget contributed to `dev_board.rail` only.
- Extension later is **one line** in `modules/trading/module.py::contribute()` — adding
  `trading.rail` as a second place — because of §4.6 rule 2 (one widget, many places). To keep
  that true, the card depends only on `trading`'s own ports (`IOrderSubmission`, `ITradingSession`)
  and never on anything Dev-Board-specific; a test constructs it outside Dev Board.

### D16 — The Engine track is a harvest: build lift-ready in the app, lift on a written criterion 🔵 Proposed

Raised by the user on 2026-09-13 (*"plan sao tui chưa thấy nói tới sẽ làm gì với engine nhỉ?"* —
"why does the plan not say what will be done with the Engine?"). HLD §8 answers it:

- The mechanism (`BoundedContextModule`, the contribution registry, the surface runtime,
  navigation) is built inside the app under `core/contracts/` and `shell/workbench/` with **no
  application import** and the Engine's package layout, then **lifted** into
  `sagittarius_engine/extensions/workbench/` — Fowler's *Harvested Framework*, the pattern the
  Engine's own `EPIC-001D` argues for when it warns against choosing abstractions early.
- **Lift criterion** (all three): zero app imports (guard); used by ≥ 2 surfaces or ≥ 2 modules of
  this app; API unchanged for one whole phase.
- Engine schedule E0–E3 aligned with app phases (HLD §8.4): E0 `ScheduledJob.cancel()` now; E1
  after Phase 1 (module base + registry + descriptors); E2 after Phase 2 (region host, per-place
  models); E3 at Phase 5 (`NavigationService`, screen lifecycle, conformance suite).
- Supersedes HLD §5.3's "until a second application needs it": the second *surface* of this
  application is the evidence.

The SDD for Phase 0 ([`Docs/SDD/`](../../../Docs/SDD/README.md)) fixes the descriptor shape (one
`ContributionDescriptor` for every place, `ScreenContribution` as the sole exception) and the
registry validation rules — this closes ❓ O1 pending the user's review.

---

## 7. Round 3 — disposition of the independent design review (2026-09-13)

The user asked a second AI to review the spec against the prompt in the session log; its report is
[`Tasks/reports/EPIC-025_design_review.md`](../../reports/EPIC-025_design_review.md). Every code
claim in it was re-verified here before acting (the `grep`s are in the session). **Verdict on the
review: high quality** — the measurements it repeats hold exactly, and of its seventeen ranked
findings sixteen are correct as stated; the one partial miss is 7.3's framing (see O4). The
dispositions:

| # | Finding | Disposition | Where |
| :-: | :--- | :--- | :--- |
| 1 | SDD-03 made a Coordinator DI-discovered (breaks `async-ui-action-rule` §2, D12; changed behaviour) | **Accepted.** A factory returns a card = View + Presenter; the Presenter owns its Coordinators and its `ActionOwnershipTracker`; two surfaces = two instances (today's behaviour); shared truth is the feed, never an object. The review's alternative (`SurfaceSession`) was not taken — the existing Presenter-owns rule already answers it | SDD "Ownership", SDD-03 |
| 2 | `dev.mode=false` could not boot: non-probe `dev_board` contributions raised | **Accepted.** Rule 3 now drops every contribution to a declared-but-gated surface; an *unknown* surface id still raises (typo protection) | SDD rules 1, 3; SDD-02b |
| 3 | `core/contracts` failed its own Qt-free guard (`QWidget`, `QtEventBridge`) | **Accepted.** `TYPE_CHECKING`-only imports; every guard ignores `TYPE_CHECKING` blocks | SDD descriptor; HLD §6.1 |
| 4 | `shell/workbench` could not import `PageShell` and stay lift-ready | **Accepted.** `IPlaceHost` ABC in `core/contracts`; `ui_kit.PageShell` implements it; `support → core.contracts` edge added; lift criterion 1 reworded | HLD §8.2, §8.3, hld-01a, SDD-01b |
| 5 | Support packages and the shell contributed UI without a hook or a `module_id` | **Accepted.** Support packages never contribute; the module that wants the widget contributes it; the shell contributes its own surfaces under `contributor_id="shell"`; `module_id` keeps one meaning | SDD descriptor; hld-03b; HLD §4.6.4 |
| 6 | "Dead, zero references" wrong for `rate_limiter`, `position_state_reconciler`, `strategy_factory` (+ `system_error_feed`) | **Accepted.** Re-measured; the delete list now names only the two order events and `StatGrid`; the rest are live with owners | HLD §3.5 |
| 7 | The cited `strategy_context → backtesting` import does not exist; the real cycle is `trading → backtesting` at `position_sizing_bridge.py:21` | **Accepted; decision pending — O4 below** | HLD §2.3 |
| 8 | No threading contract for ports while the order path runs on the websocket thread | **Accepted.** Threading contract per kind; lease under the session lock; claim-then-execute atomic | SDD "Threading contract" |
| 9 | "59 → 0" satisfiable by `git mv`; script not in the repo | **Accepted.** `tools/measure_duplicate_members.py` committed in Phase 0 over old and new trees; baseline recorded | SDD "Measured baselines"; EPIC-025A |
| 10 | Global integer `order` with fail-fast collision; two uniqueness keys | **Accepted with a different fix.** `order` is a sort key with a stable tie-break `(order, contributor_id, factory.__qualname__)`; uniqueness key is the descriptor identity. VS Code's `group@order` strings were considered and not adopted (ints are enough once collisions are tolerated) | SDD rule 2 |
| 11 | `contribute()` must not import widget modules | **Accepted.** Lazy factory bodies; guard (e) on `sys.modules`. The review's `factory_ref` (module path string) was not adopted — it loses typing for a property the lazy rule already gives | SDD "Lazy factories"; HLD §6.1 |
| 12 | `--dev` survives the restart; `sys.argv[1:]` drops the script path | **Accepted.** Restart keeps `argv[0]`, strips `--dev`/`--debug` when turning developer mode off | SDD "dev.mode and restart"; SDD-05 |
| 13 | No guard rule for the legacy tree during the strangler period | **Accepted.** Legacy may import `modules/*/contracts`, `core`, `support`; `modules/**` never imports legacy except through the allowlist during its own phase | HLD §6.1 |
| 14 | No bridge from `AbstractScreenModule` into the registry in Phase 0 | **Accepted.** `LegacyScreenAdapter` wraps each remaining screen module into a `ScreenContribution`; deleted in Phase 4 | SDD boot step 6; SDD-01b |
| 15 | Second venue not local (`MarketDataVenue`/`TradingVenue` in `core/vo`); two strategies not local (single-slot `LiveStrategySession`) | **Accepted.** Venues (and `ExchangeCredentials`, `VenueAlignment`) move to `support/binance_gateway/contracts`; `LiveStrategySession` keyed by symbol from Phase 2 with `symbol` on `ArmedStrategySnapshot` and the arm/disarm events — a seam, not a variant | HLD §2.4; EPIC-025C |
| 16 | "Owner id" named three mechanisms; the lease's cited precedent had inverted semantics | **Accepted.** Three vocabulary rows (fencing / stream namespace / exclusive lease); the `ActionOwnershipTracker` comparison deleted; `lease_owner` removed from the public port | VOCABULARY §1; HLD §3.4; SDD |
| 17 | Minor: `system_controls`/`welcome` slot drift, `backtesting` tile on Trading, §5.3 residue, `ScreenContribution` fields, event names in tasks, `dev.mode` readers in backtest, file and test counts, `IConfigWriter`, `SyncHandle`/`StreamHandle`, errors in `contracts/`, `accepts` per surface, profile scope for login, persistence for a new module | **All accepted** | HLD §3.2, §3.3, §4.2, §4.6.4, §5.3, §6.2, §6.4; SDD; EPIC-025B/C/D; D13/D14 addenda below |

Two review suggestions were **accepted in the plan rather than the spec**: B/5 — Phase 0
additionally moves one existing consumer (`chart_coordinator.py:145`, `IMarketDataSync`) onto a
`market_data` port so the skeleton crosses a real boundary with N = 2 (EPIC-025A); and B/1 — the
sentence in HLD §2.2 that Core means "the reason", not "the largest".

### ❓ O4 — the `trading → backtesting` import at `position_sizing_bridge.py:21` (blocks Phase 1)

`domain/trading/policies/position_sizing_bridge.py` imports `MarginRiskPolicy` from
`domain/backtesting/policies/` — deliberate under `EPIC-021G` ("reuse backtesting's own sizing
rather than invent a second model"), and a dependency the context map (§2.1) forbids: `trading`
depends on no business module. Promoting `PositionSizing` to `core/vo` does not solve it, because
`MarginRiskPolicy` is behaviour and `core/` holds none.

| Option | Consequence |
| :--- | :--- |
| A. Duplicate `MarginRiskPolicy` into `trading/domain` | Two copies of one rule that must stay identical; the drift disease this repository has caught twice |
| B. A `support/risk` package holding sizing and margin mathematics | Puts business rules in a support package, which HLD §1 C6 and `VOCABULARY` forbid |
| **C. Sizing belongs to `strategy`** (recommended) | Position size is *how much to bet* — a strategy decision, and `LiveStrategyConfig` already carries sizing percent and leverage. `strategy/contracts` publishes `ISizingPolicy`; `strategy` computes the quantity and puts it on the `OrderIntent`; `trading` only rounds against exchange filters and enforces `TradingLimitPolicy`; `backtesting` calls the same port. `position_sizing_bridge` moves to `strategy`. Removes the cycle, keeps `trading` free of business modules, and puts the rule where its language lives |

Option C is the recommendation under the doctrine (named pattern: the caller owns the decision,
the executor validates). It changes **which module owns** a rule, not what the rule computes, so
D12 holds.

### D17 — Position sizing belongs to `strategy` (O4 = option C) 🟢 User decision

Verbatim: *"Số 3, cũng hợp ý tôi."* ("Number 3 — that matches my thinking too."), 2026-09-13.

- `strategy/contracts/i_sizing_policy.py::ISizingPolicy` computes the order quantity from the
  account snapshot, the strategy's sizing percent and leverage, and the margin-risk rule.
  `MarginRiskPolicy` and `position_sizing_bridge` move from `domain/backtesting` and
  `domain/trading` into `modules/strategy/domain/` in Phase 2; the formula is unchanged.
- `strategy` computes the quantity and puts it on the `OrderIntent`. `trading` does only the
  exchange's part: rounding to the symbol's lot and tick filters and enforcing
  `TradingLimitPolicy`. `backtesting` calls the same `ISizingPolicy`, so backtest and live sizes
  are one number by construction.
- Until Phase 2 the existing import stays on the boundary allowlist as one entry
  (`domain.trading.policies.position_sizing_bridge → domain.backtesting.policies.margin_risk_policy`);
  Phase 1 does not touch it, Phase 2 removes it.
- What the user gains: changing how size is computed (ATR-based, Kelly, …) is one change in the
  strategy module, and backtest and live change together.

### Addenda to D13 and D14 (round 3)

- **D13:** a real login later implies a *profile*; `user_config.json` and the persisted `ui_state`
  are process-global today, and scoping them to an identity is **out of scope** here and would be
  a new decision. The `StartRequested` intent stays the only seam.
- **D14:** the restart keeps `sys.argv[0]` and strips `--dev` / `--debug` when developer mode is
  switched off; `dev.mode` is read once by one shared `ConfigManager`, which makes headless `--dev`
  effective — a declared behaviour change.

### D18 — The tests: move by default, rewrite only where the subject disappears, delete only with the subject, retarget every guard 🟢 User decision (2026-09-13: *"merge đi nào"* — "go ahead and merge", after the proposal was explained with its consequences)

Raised by the user on 2026-09-13 (*"mình chưa cần nhắc test sẽ viết lại, xóa bỏ như nào, hãy đề
xuất"*). HLD §9 is the proposal; the decision it asks for:

- **Tests travel with the code** (`git mv` + import rewrite, body unchanged); a test whose body
  must change is a rewrite and is reported as one.
- **Rewrite only** the Trading and Dev Board screen tests (13 unit files, 7 integration files),
  from an assertion inventory written first; one card, one test module; the surface's test asserts
  layout only. The count goes down because duplicated behaviour had duplicated tests.
- **Delete only** with the subject, each with the sentence "behaviour exists nowhere else" (5 files).
- **Retarget** every path-scanning guard in Phase 0 with a non-emptiness assertion, so a moved
  directory fails the guard rather than silencing it.
- **Safety net**: a backtest golden master captured in Phase 0 and held through Phase 3; the
  collected-test count recorded per phase with the delta explained; no `skip`/`xfail` added.

What "yes" commits to: Phase 0 grows by the guard retargeting and the golden master (both small),
and Phase 1's pull request will show a **net decrease** in test count that the inventory justifies
line by line.

### D19 — Test philosophy for the module architecture: test the hexagon through its ports; verified fakes and contract suites; one proof per layer 🟢 User decision (2026-09-13, same approval as D18; Hypothesis approved for `domain/` arithmetic only — the dependency is added in the Phase 0 code pull request, which is asked for like any code change)

Raised by the user on 2026-09-13 (*"xem lại triết lý test case, test layer, module hay như nào"*).
HLD §10 is the proposal. What it decides, if approved:

- Every public port ships a **fake** under `contracts/testing/` and a **contract suite** that the
  fake (unit) and the real implementation (integration) both pass; consumers test against the
  verified fake and never `Mock` a foreign port. This is the general form of the `BUG-026`/`BUG-027`
  lesson.
- **One proof per layer** (HLD §10.2): pure tests for `domain/`; ports driven with fakes for
  `application/`; the fake server and a temp database for `adapters/`; Qt-free presenter tests plus
  one `qtbot` smoke per card; layout-only tests for surfaces; one publisher/Feed test per
  cross-module event; one journey test per context-map pair; the guards for structure; the sanity
  tier unchanged; Testnet and the user for real behaviour.
- A module's **definition of done** is the checklist in HLD §10.5.
- **Hypothesis** is proposed as a test dependency for domain arithmetic only (HLD §10.6) — a test
  tool, not a mechanism, so ADR §5 does not forbid it; the user decides.

What "yes" commits to: Phase 0 writes the first contract suite and fake (for `market_data`'s five
ports) and the declaration guard; every later module follows the checklist; the review of each
phase reads §10.5, not the test count.

---

## 8. UI toolkit and theme, 2026-09-13 🟢 User decisions

### D20 — QtWidgets only; no QML anywhere; supersedes D6

Verbatim: *"Giờ xây lại các module ko dùng QML nữa, dùng Qt widget, triết lý thiết kế UX UI đúng như
1 desktop app"* ("Now rebuild the modules without QML, with Qt Widgets, with the UX/UI design
philosophy of a real desktop app"), followed by the seven principles (recorded in full in
`ui-presentation-rule.md`), and *"1. xác nhận"* confirming the three reasons in HLD §11.1. This is
the third toolkit change in the repository's history; the reasons are recorded so it is the last:
the desktop conventions are native to QtWidgets and absent from the app today (one file uses any of
them), QML islands each carry a `QQmlEngine` and produced `BUG-115`, and the Engine's QML kit is
unused by this app. `qml-rule.md` becomes historical; a guard forbids new `.qml` files.

### D21 — The OS default theme; the token and theme layer is retired

Verbatim: *"Bỏ tất cả các này (token màu/spacing/typography giữ nguyên, chỉ đổi lớp render), tụi nó
đang rất tệ, chỉ cần dùng default theme của OS là được, sau này design màu theme tính sau"* ("Drop
all of that — keeping the colour/spacing/typography tokens and only changing the render layer —
they are very bad; just use the OS default theme; a designed colour theme is for later"). No
stylesheet, palette, token set or `qdarktheme`; colour only where it carries meaning. The Engine's
tokens are not consumed by this app; whether the Engine grows a QtWidgets kit is deferred.

### D22 — Panels and dialogs replace cards; the workbench is `QMainWindow` with modes and perspectives

Verbatim: *"các card cũ cũng rất là tệ, có thể bạn nên thiết kế lại các card luôn, hoặc theo module
thì có thể sẽ không cần card luôn, bạn tự đánh giá dự án khác mà cân nhắc"* ("the old cards are
also very bad; redesign them, or per module you may not need cards at all — judge by other
projects"). Judged by precedent (HLD §11.2): MetaTrader 5 and IBKR TWS are dock-panel workbenches
with order entry in a dialog; Qt Creator has modes and saved perspectives. Decision: the **card is
retired**; a module contributes **panels** (`QDockWidget` content) and **dialogs** (`QDialog`); a
surface is a nested `QMainWindow` with a per-user perspective; the manual order is the Order dialog
(F9, Dev Board only per D15). `2. Gộp`: the rebuild is folded into `EPIC-025` phase by phase, not a
separate epic. The descriptor and registry of the SDD are unchanged; only the surface host changes.
