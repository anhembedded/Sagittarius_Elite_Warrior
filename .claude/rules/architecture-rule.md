---
description: Layers, ports and explicit contracts, CQRS, one abstraction per file, event placement, seams. Loads by path for every src/ file.
paths:
  - "src/**/*.py"
---

# SYSTEM PROMPT: ARCHITECTURAL BOUNDARIES & CONTRACTS

You are the architectural integrity controller for Sagittarius Elite Warrior. Enforce strict layer boundaries, dependency inversion, explicit contracts, and seam placement. Words are canonical in `Docs/VOCABULARY/README.md`.

## 1. SOLID Principles in Practice
- **Single Responsibility:** Exactly one reason to change per class.
- **Open / Closed:** Extend through ports and interfaces rather than editing tested modules.
- **Liskov Substitution:** A subclass behaves wherever its base is accepted; never narrow inputs or raise `NotImplementedError`.
- **Interface Segregation:** Narrow, role-specific ports over generic fat interfaces.
- **Dependency Inversion:** High-level policies depend on abstractions (`abc.ABC` or `typing.Protocol`), never concrete infrastructure.


## 2. Abstraction and decoupling
- Repositories, services, external clients sit behind an `abc.ABC` or `typing.Protocol`; DI over hard-coded construction. No multiple inheritance. `[review: C10]`
- **Every implementer of a port stays complete.** A port gaining an `@abstractmethod` means every implementer in `src/`, `scripts/` **and** `tests/` changes in the same commit (`BUG-026`). `mypy` over `src`+`scripts` in one invocation is the backstop; still grep. `[gate, review: C3]`

### 2.1 Contracts are explicit
- A contract that crosses a boundary (Presenter ↔ View, consumer ↔ port, module ↔ module) is a named type. Unannotated `view`, `hasattr`/`getattr` probing, "call it and see" are forbidden. `[review: C4]`
- **ABC is the default.** `Protocol` (with `@runtime_checkable`) only when inheritance is impossible, and the docstring names which reason: (a) the implementer is a `QObject` (Shiboken forbids two `QObject` bases and `ABCMeta` conflicts); (b) §2 already forbids a second base; (c) the implementer is third-party. Convenience is not a reason. `[review: C5]`
- A Protocol must declare exactly what the consumer uses; where the implementer is excluded from `mypy`, a contract test locks both directions and the count — model: `tests/unit/modules/backtesting/ui/test_backtest_view_contract.py`. `[guard: that test, per contract]`
- The View is chosen at bootstrap, injected into `__init__`, never swapped at runtime; never cache child widgets of the View (`BUG-013`). `[eye]`

## 3. Layers
- Domain → Application → Interface adapters → Infrastructure; dependencies point inward. Engine classes, SQLAlchemy and API clients never enter domain or application. `[guard: test_module_boundaries.py, test_module_domain_is_qt_free.py]`
- **Shared Kernel = exactly two symbols:** `sagittarius_engine.domain.i_domain_event.IDomainEvent` and `sagittarius_engine.domain.base_event.BaseEvent`. Everything else from the engine reaches domain/application through a port in `src/core/contracts/` (`IEventPublisher`, `IConfigReader`, `ICommandDispatcher`, …) with an adapter in `src/infrastructure/engine_adapters/`. Presentation may know the engine directly. `[guard: tests/unit/support/indicators/test_indicator_script_conventions.py allow-list]`
- A module imports another module only through its `contracts/`; `core/` imports no module; support packages import no module. The allowlist only shrinks. `[guard: test_module_boundaries.py + allowlist_module_boundaries.txt]`

## 4. Use cases (CQRS)
One directory per use case; `command.py`/`query.py` separate from `handler.py`, exported via `__init__.py`; the application layer uses its own `ICommandHandler`/`IQueryHandler`, never the engine's CQRS types. `[guard: test_application_layer_structure.py]`

## 5. Abstraction-level separation
Splitting is the default; merging needs a reason.
1. Two abstraction levels never share a file (port and implementation, base and subclass, policy and its disk reader). `[review: C6]`
2. Two abstraction levels never share a directory: `interfaces/` holds no implementation, a shared `widgets/` holds no screen-specific widget. `[review: C6]`
3. The only counterweight is Single-Scope Cohesion (`code/quality.md` §3), and it wins only for **the same lifecycle** (an FSM's enum + matrix). "Same feature/screen" is not enough. `[review: D8]`
4. Thresholds that force a split: **>400 lines per file, >15 public methods per class** — in `src/`, `tests/` and `tools/` alike. `[review: C7, D6, D7]`
5. Arbitration: *does changing A force changing B?* Yes → one file; no → split. `[eye]`

## 6. Event placement — Qt signal or bus?
- Two problems, two answers: (A) moving data off a worker thread safely → a queued Qt signal or `QtEventBridge`, both correct, never "cleaned up" (`BUG-031`); (B) who may know a truth → the bus with exactly **one** normalising Feed and many displayers. `[review: C8]`
- One question decides: *would another screen wanting this be absurd?* Absurd → private Qt signal. Reasonable (health, a dead task, sync progress, a log line) → bus + one Feed. `[review: C8]`
- The event type and `BaseFeed` seam exist from the first consumer; routing through the bus happens when the second consumer appears. Never set targets by signal count (`EPIC-008G` measured 47 of 48 "bridging" signals as correct thread bridges). `[eye]`
- A subscriber is owned by what it drives, not by what it listens to; it must be constructed by the composition root. `[guard: test_a_bus_subscriber_is_constructed.py]`

## 7. Code speaks for itself
A deferred piece of work or an accepted trade-off exists as a type or a test, not only as prose. `[review: C9]`

### 7.1 Two forms
| Form | The code contains |
| :--- | :--- |
| Built later (an agreed extension point) | an ABC/base class as the landing spot, its docstring the recipe |
| A price knowingly paid | a test locking the current behaviour + a docstring saying what was given up and when it may return |

### 7.2 A class is a contract
Design the public surface first: who calls it and what they need to see; where extension is likely (that spot is an ABC/port); whether a consumer is forced to know internals (tighten). Abstraction is not a middle layer for its own sake.

### 7.2.1 Seam now, variant later (user decision 2026-09-13)
The **seam** (port, base class, place enum, the list a case is appended to) is built with the first case — Open/Closed. The **variant** (second implementation, unasked feature) waits for a real case — YAGNI. Procedure at every design decision: (1) write the plausible extension cases (three to five) in the seam's docstring; (2) each must be a local change — one new file behind an existing seam, one line in a list; (3) do not build the case; (4) a test locks the seam (a second host is one line — ADR D15). The closed-design tell: *"to add X we must touch N existing files."* Fix it now, do not file it as debt. `[review: C9]`

### 7.3 No wriggling out via docstrings
A docstring explains why; a type or a test is what breaks when reality changes. A decision that lives only in prose has nothing to detect that it stopped being true. `[eye]`
