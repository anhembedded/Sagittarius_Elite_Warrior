---
name: Python Code Rules
description: Python coding standards, clean architecture principles, and code quality rules.
trigger: always_on
---

# PYTHON CODING STANDARDS & DEVELOPMENT GUIDELINES

## 1. SOLID Principles
Follow SOLID wherever it's practical — apply it to improve clarity/testability, don't force an abstraction onto a small, unlikely-to-change piece of code just to tick a box.
- **S — Single Responsibility:** One class/module has one reason to change. (See "No God Objects" below.) Split by responsibility into separate files/modules instead of piling unrelated logic into one file or one function.
- **O — Open/Closed:** Prefer extending behavior via a new class/strategy over editing existing, already-tested logic; put extension points behind an interface/ABC.
- **L — Liskov Substitution:** A subclass must work anywhere its base/interface is expected — no raising `NotImplementedError` on inherited methods, no narrowing accepted inputs or weakening guarantees the base type promised.
- **I — Interface Segregation:** Keep ports/interfaces narrow and role-specific; don't make an implementer satisfy methods it has no use for.
- **D — Dependency Inversion:** High-level modules depend on abstractions, not concrete implementations. (See "Full Abstraction & Decoupling" below.)

---

## 2. Core Architecture Principles

1. **Strong Typing & Type Safety:**
   - Always use explicit type annotations for all function signatures, parameters, return values, and class attributes.
   - Strictly avoid using `Any`. Use `Union`, `Optional`, `Generics`, or `TypeVar` where flexibility is needed.
   - Use `dataclasses` (with `frozen=True` where possible) or `Pydantic` models instead of raw dictionaries for complex data structures. Model data with proper structures (dataclasses, value objects, `Enum`) instead of loose primitives or tuples.

2. **Full Abstraction & Decoupling:**
   - Define explicit abstractions using `abc.ABC` or `typing.Protocol` for repositories, services, and external clients.
   - Adhere strictly to the Dependency Inversion Principle (DIP). High-level business logic must depend on abstractions, not concrete implementations.
   - Prefer Dependency Injection (DI) over hardcoded class instantiations inside domain logic.
   - **NO Multiple Inheritance:** Strictly avoid multiple inheritance. Use composition over inheritance, and flatten interfaces where necessary to avoid complex method resolution orders (MRO).
   - **Every `abc.ABC` implementer must stay complete, everywhere.** When a
     Port (`IExchangeClient`, `IMarketDataRepository`, ...) gains a new
     `@abstractmethod`, every concrete class implementing it must be updated
     in the same change — not just the real production implementation. Search
     `src/`, `scripts/`, **and** `tests/` for every implementer; a hand-rolled
     test double or probe script left behind an interface change instantiates
     fine until the exact moment something runs it, then fails with
     `TypeError: Can't instantiate abstract class`
     (`BUG-026`: a shutdown-probe script's fake exchange client silently fell
     behind a Port change; a second, still-unfixed instance
     (`scripts/backtest_timeframe_toolbar_e2e.py`) was only found later by
     `EPIC-002A`'s static audit — not by anyone running that script). `ruff`
     cannot catch this — verifying ABC completeness across files is a type
     checker's job, not a linter's; `mypy` (`EPIC-002`) is the mechanical
     backstop, but do not rely on the tool alone — grep for implementers
     as part of the change itself.

3. **Readability & Clean Code (Over Brevity):**
   - Follow PEP 8 guidelines. Prioritize explicit and self-documenting code over short one-liners.
   - Do NOT use complex, nested list comprehensions or multi-line `lambda` expressions when a clear `for` loop or named helper function is more readable. Do not use `lambda` for non-trivial callbacks.
   - Keep functions small, focused, and single-purpose (Single Responsibility Principle). Use explicit, descriptive variable names.

4. **Immutability & Pure Functions (No Side Effects):**
   - Strive for pure functions: functions should depend only on passed arguments and produce deterministic return values.
   - Never mutate passed arguments in-place. Return new instances or modified copies instead.
   - Strictly avoid mutable default arguments (e.g., NEVER use `def func(items=[]):`).
   - Isolate side effects (I/O, DB calls, network requests) inside dedicated adapter/boundary classes.

5. **Clean Architecture Layer Enforcement:**
   - Always strictly respect the 4 Layers: **Domain** (Pure) $\rightarrow$ **Application** (Use Cases/Ports) $\rightarrow$ **Interface Adapters** (CLI/UI Presenters) $\rightarrow$ **Infrastructure** (DB/API/Frameworks).
   - Never leak Infrastructure concerns (like `sagittarius_engine` base classes, SQLAlchemy, or API clients) into the Domain or Application layers.
   - Prioritize building reusable abstraction base layers (base cards, base dialogs, base presenters/view models) over concrete duplication.

6. **Use Case Structure (CQRS):**
   - Every Application Use Case must reside in its own dedicated directory (e.g., `src/application/use_cases/<my_use_case>/`).
   - The Command/Response definition must be separated from the Handler logic into multiple files (e.g., `command.py` and `handler.py`), and then exported cleanly via `__init__.py`.
   - Never import engine-specific interfaces (like `sagittarius_engine.extensions.cqrs.ICommand`) into the Application layer. Use the layer's own pure Python `ICommandHandler` / `IQueryHandler` interfaces.

7. **Strict Code Quality Rules:**
   - **No Magic Numbers & Named Constants:** Strictly avoid using raw numbers or magic strings in code. Define them centrally as named constants or configuration keys (`config_keys.py`, `user_config.json`, `constants.py`). Strategy/indicator parameters must be declared dynamically via parameter schemas (`input_int`, `input_float`, etc.).
   - **No Nested Loops:** Avoid deep nesting of loops (e.g. `for` inside `for` inside `while`). Extract nested logic into separate helper functions to reduce cyclomatic complexity and improve testability.
   - **No God Objects:** Strictly avoid creating massive classes or modules that know too much or do too much. Delegate responsibilities (e.g. CLI parsing, bootstrapping, event handling) into dedicated modules.
   - **Abstract Low-Level Logic:** Do not write verbose, low-level OS/File system operations (like deep `os.path` joins or byte-level manipulation) directly in application or composition root layers. Extract them into common utility classes.
   - **No Function-Local / Lazy Imports (Tuyệt đối không dùng Local Import):** All module, class, function, and type imports MUST be declared at the top of the file (top-level imports) adhering strictly to PEP 8. Never place `import ...` inside functions, methods, slots, test cases, or nested scopes (the only exception is `if TYPE_CHECKING:` guards at top level).
   - **Single-Scope Cohesion & Colocation (Gom chung các thành phần liên quan vào cùng 1 Scope / Single Source of Truth):** Tightly coupled components that define the same domain lifecycle, state machine, or feature configuration MUST be co-located within the same single file or module scope (e.g., FSM State Enum + FSM Event Enum + Transition Matrix + UI Mode mappings in a single `*_fsm_matrix.py`). Do NOT fragment tightly coupled definitions across multiple scattered files where understanding or modifying a single feature lifecycle requires jumping across 4-5 distant modules. Related enums, schemas, transition tables, and constants belonging to a single concept must reside together as a single source of truth.

8. **Async UI Action Ownership & Cancellation:**
   - Every user-initiated background action that can alter UI lifecycle state (for example backtest, sync, load, or render) MUST have an immutable action context: unique `action_id`/generation, action kind, immutable input snapshot, start time, and explicit terminal outcome.
   - Worker signals and completion callbacks MUST carry the action identity. Before changing ViewModel state, FSM state, chart data, or starting a follow-up action, the receiving slot MUST verify that the action is still active. Stale callbacks are ignored and logged; they must never overwrite a newer user intent.
   - Cancellation MUST be cooperative and idempotent. A cancelled action may not later publish success/failure UI state, and its final transition must restore the appropriate pre-action lifecycle state rather than blindly forcing `IDLE`.
   - Long-running use cases MUST propagate cancellation checks through every computational pass, including validation/split passes. Progress events must be throttled or coalesced before reaching the UI thread.

9. **Truthful Data, Validation & Snapshot Semantics:**
   - A range-coverage check MUST verify internal gaps using the timeframe cadence and normalized UTC boundaries; min/max timestamps or total row count alone do not prove coverage.
   - Exchange trading rules (minimum notional, lot size, tick size, leverage) MUST come from cached metadata for the active symbol/market. Never treat account capital as order notional and never hard-code a universal exchange filter.
   - UI history/cache snapshots MUST be immutable (no retained mutable model references), memory-bounded, and include enough provenance to describe the result honestly: configuration, data window/watermark, strategy version/parameters, fee model, and execution mode.
   - **Business Contract Before Implementation Contract:** Tests MUST first express the observable business promise, then verify the implementation. A green suite that only proves private calls, existing data structures, or an intentionally limited engine contract is not evidence that the user-facing behaviour is correct. For every critical trading journey, write deterministic acceptance coverage for the expected inputs, orders/position transitions, fills, trade side, PnL direction, and the visible table/chart outcome.
   - **Do Not Collapse Trading Semantics:** A strategy signal, order intent, execution fill, position entry, position exit, and short entry are distinct domain facts. Model and test them separately; never let an ambiguous `BUY`/`SELL` label silently stand for more than one. In a long-only engine, `SELL` is an exit of an existing LONG, not an opened SHORT.
   - **Truthful Trading UI:** Every label, icon, marker, filter, metric, and empty state MUST describe what has actually happened and what the engine supports now. A close-long marker must use a distinct exit semantic/icon from a short-entry/sell marker. Do not present a planned or unsupported capability as available; hide/disable it or explicitly label it unavailable. Test the displayed semantics, not only the underlying payload.
- Never claim instantaneous or fixed latency without a reproducible benchmark fixture. State the workload, cache condition, and measurement method; display ETA as an estimate only.
- **Renderer benchmark methodology:** A renderer comparison must drive the same immutable source payload, viewport/input sequence, event drain and completed visual grab through both implementations. Record median/p95, DPR, actual backend, environment, visual semantics and warning capture. Treat CPU/GPU frame time and business/pixel correctness as separate proofs; never improve a benchmark by dropping markers, labels, data or a final render check.
- **Backtest chart host boundary:** Use a narrow Backtest-scoped `Protocol` (`IBacktestChartHost`) and transient factory so Presenters/Backtest Views depend only on the port, never a concrete renderer directly. A host is UI-thread/view-owned and may not be singleton or hot-swapped. (A former native C++/QML host lived behind this same port and was deleted outright — the port stayed worth keeping even with one implementation.)
- **Counterintuitive Story Check:** When a story, label, default, or acceptance criterion can reasonably conflict with a user's mental model (especially a TradingView-style workflow), stop and report the observable behavior, evidence, and trade-off before finalizing the design. Do not invent a hidden user intent; encode the chosen semantics truthfully in UI copy and deterministic acceptance tests.

---

## 3. UI & Presentation Layer Rules

- **QML Standards & Declarative Guidelines (Strict Adherence to `qml-rule.md`):**
  - **Separation of Logic & UI**: QML files are purely declarative views. Business logic, calculations, domain validations, and state machines reside strictly in Python (`Presenter`, `ViewModel`, `Domain`). UI triggers ViewModel actions via slots/methods.
  - **Reactive Property Bindings**: Bind QML element properties directly to `viewModel` properties and `Theme` singletons. Never break bindings with imperative assignments inside signal handlers.
  - **Component Modularization & SRP**: Break down large monolithic QML files (> 300 lines) into focused, reusable components (`ModalDialogCard.qml`, `BotParamField.qml`, `DynamicTabBar.qml`).
  - **Declarative `States` and `Transitions`**: For elements with 3+ visual states (e.g., `IDLE`, `HOVER`, `PRESSED`, `DIRTY`, `DISABLED`), prefer declarative `states: [...]` and `transitions: [...]` over complex nested ternary expressions.
  - **Micro-Animations for Feedback**: Use subtle non-intrusive micro-animations (150ms – 250ms) via `Behavior on color / opacity / height` for smooth transitions without blocking the UI thread.
  - **Security & UI Injection Defense**: Always enforce `textFormat: Text.PlainText` on `Text` items rendering dynamic or external data (trade logs, error messages, symbol names) to prevent HTML/RichText UI injection.
- **Dynamic Responsive UI Sizing & Synchronized Table Columns:**
  - Never hardcode rigid fixed pixel dimensions (`width`/`height`) on modals, dialogs, popups, or cards. Use `preferredWidth` and `preferredHeight` dynamically clamped to available overlay boundaries.
  - All scrollable inner containers must declare `ScrollView { clip: true }` and responsive content widths.
  - For all tables and grids with headers, column widths MUST be declared centrally as a **Single Source of Truth** and bound directly to both header and row delegates to guarantee 100% synchronized alignment during window resize and splitter movements.
- **UI Icon Assets & Theme-Tinted Rendering:**
  - All visual iconography in the UI MUST be defined as clean, standardized SVG vector files in `src/presentation/ui/assets/icons/` (following Lucide/Feather icon standards). Never use raw Unicode emoji for UI icons.
  - Always render icons via the centralized theme image provider `image://icons/<name>/<token>`.
- **Domain-Driven Precision Terminology:**
  - Strategy parameters must be labeled **"Thông số Chiến lược"** (`Strategy Parameters`), distinct from general Bot system settings.
- **MVP Trio Screen Directory Layout:**
  - For a screen under `src/presentation/ui/screens/<name>/`, keep `<name>_presenter.py`, `<name>_view.py`, `<name>_view_model.py`, and QML files flat at the top level of the screen's folder. Group only helper modules into `<name>/logic/` or `<name>/helpers/` when size warrants it.
- **Coordinator Pattern for an overgrown Presenter (`PRO-001`/`PRO-002`, `EPIC-003`):**
  - When a Presenter's background-action logic outgrows one file, split it by feature slice into `<name>/coordinators/<feature>_coordinator.py` — a Presenter-owned, constructor-injected class (`thread_manager`, `dispatcher`, and the specific `view_model` signals it handles), never something that resolves its own container or is independently discoverable/DI-registered. This is a distinct, sanctioned category from the plain `logic/`/`helpers/` above — those stay pure functions/stateless transforms; a Coordinator is allowed to hold state and submit its own background work.
  - **A Coordinator MUST NOT own independent FSM state or its own action-ownership/cancellation bookkeeping** (the `action_id`/generation, stale-callback fencing, and cooperative-cancellation contract from "Async UI Action Ownership & Cancellation" in §2 item 8 above). That bookkeeping has exactly one owner — the Presenter (or a single shared tracker the Presenter owns and hands to every Coordinator) — never reimplemented per-Coordinator. Splitting a Presenter into Coordinators that each keep their own action-id counter is the same "Single-Scope Cohesion" violation as scattering one FSM's Enum/matrix across files: one lifecycle, fragmented into several sources of truth that can silently disagree. Before splitting any Presenter that already has bespoke action-ownership machinery (e.g. `BacktestPresenter`'s `_next_action_id`/`_active_action`/`BacktestActionKind`), extract that machinery into one shared, reusable tracker first — do not duplicate it across the new Coordinator files.
  - The Presenter that owns a screen's Coordinators keeps the FSM, keeps `_connect_ui_signals()`/`_connect_engine_events()`, and keeps final say over UI-visible state; Coordinators do the work and report back through it, they do not become parallel mini-Presenters with their own UI-mode opinions.
- **UI Preview Convention & Live Tooling (BOT-031):**
  - Every UI package (`src/presentation/ui/screens/<name>/` and `src/presentation/ui/components/sidebar/`) MUST maintain a `preview.py` declaring `build_preview() -> QWidget` for fast, standalone local rendering without full engine boot.
  - Run preview live via `.\scripts\preview-qml.ps1 <screen>` or inspect available targets with `.\scripts\preview-qml.ps1 --list`. Enforced via guard test `tests/unit/presentation/ui/test_preview_fixtures_exist.py`.


---

## 4. Testing & Quality Assurance

- **Four required test levels:** Every feature defines its proof across the
  four levels in `.agents/rules/ci-rule.md` — Unit, Integration, Sanity and
  Desktop E2E. A change may add no new test only when an existing test at the
  relevant level already proves the exact new behavior; name that evidence in
  the task/report.
- **Sanity:** Every new feature/screen ships construction-only sanity coverage
  in `tests/sanity/`: boot the real app (`create_app()`, real composition root),
  construct real View + Presenter, assert real DI resolves and
  `quick_widget.errors() == []`. No click, background dispatch or network.
- **Integration:** Put deterministic user/application journeys in
  `tests/integration/`: drive named QML/Qt input, wait on terminal
  signal/state, and assert the observable result using local seeded/fake
  boundaries. Never depend on a public exchange or live account.
- **Desktop E2E:** A reported GUI/runtime defect or native rendering change
  requires a retained opt-in Windows desktop E2E harness: start the actual app,
  seed deterministic local data, use real `QTest`/`qtbot` input, wait for the
  visible terminal state, and capture clean Qt messages/stderr. This level is
  local/nightly when necessary, but it is not optional evidence for native
  interaction work.
- **External service smoke:** An explicitly requested, credential-free smoke
  check is operational evidence, not a fifth test level and never a normal CI
  gate or replacement for deterministic coverage.
- **Static quality:** Ruff lint/format plus architecture/import rules run on
  every commit and pull request; they support but do not replace the four test
  levels.
- **Deterministic Async & UI Testing:** Never use timing sleeps to synchronize a test. Wait for a named completion signal, FSM state, terminal event, or bounded `qtbot.waitUntil(...)` condition. Give every QML control that is a critical user action a stable `objectName` so integration/E2E tests can target it.
- **Financial & Backtest Invariants:** Add deterministic property/invariant tests for financial code: reject `NaN`/infinite values, keep fees non-negative, keep equity/trade/metrics internally consistent, and require identical outputs for identical input data/configuration. Every new execution mode, fee model or simulation pass must extend these invariants.
- **Domain Logic Edge Cases — Boundary Value Analysis, not exhaustive enumeration:** "Test every edge case" is an unbounded, unverifiable target — pick cases using Equivalence Partitioning (one representative input per class the logic is meant to treat identically) plus Boundary Value Analysis (the values right at and around a class boundary, where real bugs concentrate), not a manual grab-bag. For any consequential domain calculation or decision, mutation-verify it: deliberately break the logic under test (flip a comparison operator, shift a boundary by one, invert a sign) and confirm the existing test actually fails — a test that still passes against broken logic proves nothing about correctness, no matter how many lines it executes (`BOT-106A`: a mathematically-constant return sequence still made `statistics.stdev()` compute ~1e-16 instead of exactly `0.0`, silently passing a test that assumed float equality). Do not add exception-handling tests for a domain state an existing invariant — FSM transition matrix, frozen dataclass, DI-enforced construction — already makes unreachable; that is padding coverage, not proving correctness.
- **Business Acceptance for Trading Features:** A backtest UI test MUST assert the business composition of the result, not merely that a run completed. For example, a long-only result may contain long entries and long exits but MUST contain no short trade; a future short-enabled strategy must prove a downtrend produces an actual SHORT fill, its SHORT table filter shows it, its PnL moves correctly as price falls, and its chart marker represents the fill rather than merely the strategy signal.
- **Read-only CI:** A CI verification command MUST not mutate the working tree. Use `ruff check` and `ruff format --check` in CI; reserve `--fix` and formatter writes for an explicit developer formatting action. A test runner that changes unrelated files is not an acceptable required quality gate.
- **Fixing a bug:** follow `.agents/rules/bug-fix-rule.md` in full — root
  cause first, regression test before the fix (confirmed failing for the
  right reason, at the correct test tier), kept permanently after.
- **Use repo's QML test helpers:** Use `qml_item` / `find_qml_item` fixtures from `tests/conftest.py`, `qtbot.waitUntil(...)`, and `item.mapToItem(root, 0, 0)`.
- **Do not move click handling off the Button itself** when tests emit `.clicked`.
- **Local CI/CD Enforcement:**
  - Always run `.\scripts\ci-local.ps1 -Full` to validate your code before finishing changes. This includes lint, format, coverage, Unit and Sanity checks; `-UnitOnly` is diagnostic-only and never sufficient for handoff or commit.
  - For lifecycle/concurrency work, add deterministic tests for stale-success, stale-failure, success-after-cancel, and cancellation during every relevant computation phase. Do not rely on timing sleeps to test races.
- **CI/CD MUST capture a log file, then scan it for problem levels:** A green
  exit code is not sufficient evidence that a run was clean. `scripts/ci-local.ps1`
  automates this — it captures every test run to a log file and runs
  `Invoke-RunLogScan` afterward, which greps for the problem levels
  `.agents/rules/logging-rule.md` §"Log levels" defines (`WARNING`, `ERROR`,
  `CRITICAL`) using that file's own documented matcher
  (`Select-String "- (WARNING|ERROR|CRITICAL) -"` / `grep -E '\- (WARNING|ERROR|CRITICAL) \-'`)
  and fails the run if any are found. This runs automatically on every
  `ci-local.ps1` invocation (both `-SanityOnly` and the Unit/Full path) — do
  this in the script, not by hand each time.
  Every hit the scan reports MUST be investigated and reported — never
  silently accepted because the tests still passed, and never bypassed with
  `-AllowLogWarnings` as a way to get a green build. Report each one as
  either (a) a real defect, which then follows `.agents/rules/bug-fix-rule.md`
  in full, or (b) an understood, explicitly justified expected condition,
  naming the reason. "It was already there before my change" is a reason to
  check whether it is a known open bug in `Tasks/bug_report/incomplete/`, not
  a reason to skip it. `-AllowLogWarnings` exists only to triage a run whose
  hits are already understood and recorded.
  This rule exists because a run can exit 0 while logging a real, silently
  degraded path — e.g. a realtime backtest that logged repeated
  `tick_gap_forced_commit` WARNINGs on every bar of every run (`BUG-022`: the
  bar-close condition never matched real exchange `close_time` values, so the
  closing tick of every bar was evaluated twice) and still reported success,
  or a chart query returning `rows=0` that produced a blank chart with no
  failure anywhere (`BUG-021`).

---

## 5. Proactive Inconsistency Challenge & Constructive Pushback

- The AI assistant MUST actively challenge/refute user requests if they introduce inconsistencies, anti-patterns, layer violations, or break established domain principles.
- Never blindly follow contradictory instructions; explain the root issue and propose a clean, consistent alternative.

---

## 6. Git Commits & Version Control

- **DO NOT commit code changes (e.g., using `git commit`) autonomously unless the user explicitly requests you to do so. Always wait for explicit permission before saving changes to version control.**
- When committing upon user request, strictly follow `.agents/rules/commit-rule.md` (Conventional Commits, pre-commit test verification, atomic changes, and the mandatory `Co-Authored-By` trailer — naming the AI assistant that actually authored the commit, never a fixed placeholder; misattributing to a different tool is not acceptable per `commit-rule.md`).
