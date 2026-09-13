# §5 — The Engine owns mechanism, the application owns policy

The user's framing: *"Engine đó sẽ là core engine trong sự nghiệp của tôi, tôi sẽ tái sử dụng cực
nhiều"* ("that Engine will be the core engine of my career; I will reuse it enormously"). The rule
that follows is simple to state: everything that **does not know this application** goes to the
Engine; everything that knows about "trading", "Dev Board" or "Binance" stays in the application.
The Engine's own rule agrees — `ui-architecture.md` §1: *"Runtime — Engine owns: Shell, regions,
navigation, screen lifecycle"*.

## 5.1 The split

| Capability | Engine (mechanism) | Application (policy) | Engine status (measured 2026-09-11) |
| :--- | :--- | :--- | :--- |
| Module lifecycle, topological sort, fail-fast | `IExtension`, `ExtensionDescriptor`, `ExtensionManager` | `BoundedContextModule` (two UI hooks), the module list | ✅ present |
| Dependency injection | `IContainer`, `registrations()` | the double-claim check after `register()` | ✅ present; ⚠️ overwrites silently |
| Events | `IEventBus`, `MemoryEventBus` (synchronous on the caller's thread), `QtEventBridge` (hops to the main thread through `AutoConnection`) | Feed normalisers, event types | ✅ present |
| CQRS | `IDispatcher` resolves the handler from the container (**there is no registry**), middleware | internal Commands and Queries | ✅ present |
| Scheduler and hosted services | `Scheduler.every().do()`, `HostedServiceManager` | the `PositionRefreshService` job | ✅ present; ⚠️ **no job cancellation** — only `max_runs` and `stop()` |
| Route / stacked navigation | `PresenterManager` (lazy, `QStackedWidget`) | `ScreenRegistry` (`EPIC-016`) | ✅ present — sufficient for Phases 0–4 |
| **Navigation service, regions, slot/contribution registry, screen lifecycle with a conformance suite** | **`EPIC-001D`** — `NavigationService`, regions, a slot registry exposed **as models** (no dynamically named context properties), `mount / unmount / ui_mode / shutdown`, the UI runtime as a real `IExtension` | the contribution kinds (§4.3), surfaces, the `dev.mode` gate | ❌ **absent** (backlog, P2; B and C are done, so it is **unblocked**) — Phase 5 |
| QML import path per `QuickSurface` | `create_quick_widget(background=)` — a single hard-coded import path `_QML_IMPORT_PATH` | `QuickSurface` (application-side, `BOT-132`) | ❌ absent — needed for ADR D6 (deferred) |
| Import-boundary guard | `import_boundary.find_deep_imports(root, exempt_dirs)` — only checks deep imports into `pyside_mvc` | the application's three AST guards | 🟡 a narrow tool exists; **generalising** it to `find_cross_package_imports(root, rules)` is an Engine candidate (every modular-monolith app needs it) |
| `QApplication` before `boot()` ordering | — | the composition root constructs `QApplication` before `App.boot()` | ✅ proven by `examples/student_management/docs/ui_extension_lifecycle.md`: *"no engine change needed"* |

## 5.2 The Engine-side task (❓ O2 — the concrete API is settled in round 2)

**`TASK-043`** is filed in the Engine repository (backlog, referencing `EPIC-001D`), with the
minimum scope for which this application is the first real consumer:

1. `NavigationService`: `navigate(route, *, source: NavigationSource)` distinguishing `USER_INTENT`
   from `RESTORE` (this application's `BUG-104` / `BUG-107`: a restore must not trigger side
   effects); a `can_leave()` hook.
2. A slot registry: a contribution is a **descriptor plus a factory**, exposed as a model per slot
   (the `EPIC-001D` constraint); the Engine does not know which kinds exist — a kind is a string the
   application registers.
3. `create_quick_widget(..., import_paths=())` — extra import paths per widget (unblocks ADR D6).
4. A generalised `import_boundary`: rules of the form `(from_package_glob, allowed_import_globs)`,
   with a ratchet allowlist.
5. The UI runtime becomes an `IExtension` (decided on 2026-08-23 inside `EPIC-001D`).

Every new API becomes one `RequiredEngineCapability` line in the application's
`engine_capabilities.py` (`BOT-133`); the Engine bumps `b` under `release.md` (published API changed).

## 5.3 What is **not** pushed to the Engine

- The contribution kinds (`dev_probe`, `settings_section`, …): application policy.
- ~~The two hooks `contribute` / `subscribe` on `BoundedContextModule`: they stay in the application
  until a second application needs the identical shape.~~ **Superseded by §8.3** (the harvest rule):
  they lift at E1, once two modules of this application use them.
- The Binance gateway and credentials: application.
