---
name: Architecture Rule
description: SOLID, Clean Architecture layer boundaries, Ports/Adapters and ABC completeness, contracts must be explicit (no implicit duck-typing — ABC by default, Protocol only when inheritance is impossible), CQRS use-case structure, and Abstraction-Level Separation (different abstraction levels never share a file or a directory).
trigger: always_on
---

# ARCHITECTURE RULES

Read this when: designing/refactoring architecture, adding or changing a Port (`abc.ABC` / `Protocol`), adding a Use Case, deciding which file/directory something belongs in, or splitting a file/class that has crossed a threshold. Pure code quality (magic numbers, nested loops, lazy imports, typing, immutability) lives in [`code-quality-rule.md`](code-quality-rule.md) — the counterweight to §5 is **Single-Scope Cohesion** in that file.

> [!IMPORTANT]
> **The decision doctrine for hard/ambiguous architecture has moved to
> [`../ONBOARDING.md`](../ONBOARDING.md) §7** ("Deciding for yourself is the default") —
> 2026-09-02. Reason: it is a rule about **autonomy**, it applies to every
> technical decision and not just architectural ones, and sitting here meant
> **no navigation file pointed at it**, so in practice nobody read it. Summary:
> decide by proven patterns, reference large projects, don't shy away from
> redesigning a *hard design*, decide without asking about every small choice —
> except for the 3 categories listed there.

---

## 1. SOLID Principles

Follow SOLID wherever it's practical — apply it to improve clarity/testability, don't force an abstraction onto a small, unlikely-to-change piece of code just to tick a box.

- **S — Single Responsibility:** One class/module has one reason to change (see "No God Objects"). Split by responsibility into separate files/modules instead of piling unrelated logic into one file or one function.
- **O — Open/Closed:** Prefer extending behavior via a new class/strategy over editing existing, already-tested logic; put extension points behind an interface/ABC.
- **L — Liskov Substitution:** A subclass must work anywhere its base/interface is expected — no raising `NotImplementedError` on inherited methods, no narrowing accepted inputs or weakening guarantees the base type promised.
- **I — Interface Segregation:** Keep ports/interfaces narrow and role-specific; don't make an implementer satisfy methods it has no use for.
- **D — Dependency Inversion:** High-level modules depend on abstractions, not concrete implementations.

---

## 2. Full Abstraction & Decoupling

- Define explicit abstractions using `abc.ABC` or `typing.Protocol` for repositories, services, and external clients.
- Adhere strictly to the Dependency Inversion Principle (DIP). High-level business logic must depend on abstractions, not concrete implementations.
- Prefer Dependency Injection (DI) over hardcoded class instantiations inside domain logic.
- **NO Multiple Inheritance:** Strictly avoid multiple inheritance. Use composition over inheritance, and flatten interfaces where necessary to avoid complex method resolution orders (MRO).
- **Every `abc.ABC` implementer must stay complete, everywhere.** When a Port (`IExchangeClient`, `IMarketDataRepository`, ...) gains an `@abstractmethod`, **every** implementer must be fixed in the same change — grep `src/`, `scripts/` **and** `tests/`. A test double or probe script left behind still imports fine and only blows up when someone actually runs it: `TypeError: Can't instantiate abstract class` (`BUG-026`: the fake exchange client of a shutdown-probe script fell behind a Port change; the second instance, `scripts/backtest_timeframe_toolbar_e2e.py`, was only caught by the static audit in `EPIC-002A`). `ruff` cannot catch this — it is the type checker's job; `mypy` (`EPIC-002`) is the mechanical backstop, but you **still have to grep the implementers yourself**, don't leave it to the tool.

### 2.1 Contracts must be explicit — no implicit duck-typing

> **Every contract that crosses a boundary (Presenter ↔ View, consumer ↔ port, module ↔ module) MUST be a
> named type. A contract must never exist only as "call it and see whether the method is there".**

**Forbidden:** implicit contracts — `def __init__(self, view)` with no annotation, then the consumer calls 15 of its members; `hasattr()`/`getattr()` to probe for capabilities. **Required:** a named type (`abc.ABC` **or** `typing.Protocol`).

What is forbidden is *implicit duck-typing*, **NOT `typing.Protocol`** (misreading this means tearing down 18 perfectly correct Protocols: 9 in `src/`, 9 in the Engine). `Protocol` **is** an explicit interface: it has a name, you can `grep` it, `mypy` can check it, and with `@runtime_checkable` you can `isinstance()` it — it only drops the **inheritance requirement**, not the contract.

**Order of choice — must not be reversed:**

1. **`abc.ABC` is the default.** Implementers are `class X(IPort)`; the ABC completeness rule in §2 applies in full.
2. **`typing.Protocol` (with `@runtime_checkable`) only when inheritance is impossible or forbidden by this very repo** — and **the docstring MUST state which reason applies**. Exactly 3 reasons are valid, and all 3 have real precedent:
   - **(a) The implementer is a `QObject` subclass.** PySide6/Shiboken forbids inheriting from 2 bases derived from `QObject`, and `ABCMeta` has a metaclass conflict with Shiboken — an ABC **will not run**, it is not merely "worse". Precedent: `kit/style.py`, `LogModel`, `ITab`, `IStateContributor`, `IBacktestChartHost`.
   - **(b) §2 "NO Multiple Inheritance" blocks it** — the implementer already has its own base (`BasePresenter`, `QMainWindow`, ...).
   - **(c) The implementer is a third-party class** this repo cannot modify.
3. **Not (a)/(b)/(c) → it must be an ABC.** "Protocol is more convenient" is not a reason.

**Protocol is not an escape hatch from completeness.** A Protocol must describe exactly and fully what the consumer actually uses; adding a new call without declaring it on the Protocol is going straight back to implicit duck-typing. An omission on an ABC blows up immediately with `TypeError`; an omission on a Protocol makes **nothing** blow up until `mypy` runs — so for Protocols, `mypy` (`EPIC-002`) is not a backstop but the **only** mechanism.

**Real evidence (measured 2026-08-27):** `backtest_presenter.py` + 6 coordinators + `signal_wiring.py` call **14 members** of `view` that **no type declares** (the Engine's `BasePresenter.__init__(self, view, container)` leaves `view` unannotated). Scanning the whole directory yields 15 — the 15th comes from the dev harness `preview.py`, which is not part of the Presenter↔View boundary, so the "check where each hit comes from" step cannot be skipped. The Engine *does* have `IView`, but it declares exactly 1 method, `bind()`, that no View implements, and `src/` references `IView` **0 times**: the real contract ≠ the declared contract.

```bash
# What is the consumer actually using off `x`? (drop -h to see which file each hit is in)
grep -rnoE "(self\.)?_?<attribute_name>\.[a-zA-Z_]+" src/<directory>/
```

The number of members remaining **after excluding hits outside the boundary under review** must match the declared type; a mismatch means the contract has drifted. **Better than a one-off `grep`: a test that locks both directions** — `tests/unit/presentation/ui/screens/backtest/test_backtest_view_contract.py` (`EPIC-013B`) walks the source with `ast` and goes red both when something is used but not declared **and** when something is declared but nobody uses it (the `IView` situation), while also locking the **count** (comparing sets alone lets one deletion and one addition cancel out and still stay green). Mandatory in `presentation/`: that layer is **excluded from the `mypy` gate** (`pyproject.toml`, `EPIC-002A`), so a Protocol here has no static mechanism checking it — without the test it is just documentation.

**The View is chosen at bootstrap, not swapped at runtime.** A Presenter does **not** have to survive having its View swapped mid-flight: which View is used is a bootstrap-time decision, read from config and injected into `__init__`. The contract must still be explicit (declare `IBacktestView` so consumers can program against it and `mypy` can check it), but a coordinator/presenter **must not** cache `self._view` and then assume immutability as an optimization — `BUG-013`: a cached child widget may be a C++ object already `deleteLater()`d after the host rebuilt it. What is immutable here is the *View's identity*, not the *widgets inside it*.

---

## 3. Clean Architecture Layer Enforcement

- Always strictly respect the 4 Layers: **Domain** (Pure) $\rightarrow$ **Application** (Use Cases/Ports) $\rightarrow$ **Interface Adapters** (CLI/UI Presenters) $\rightarrow$ **Infrastructure** (DB/API/Frameworks).
- Never leak Infrastructure concerns (like `sagittarius_engine` base classes, SQLAlchemy, or API clients) into the Domain or Application layers.
- Prioritize building reusable abstraction base layers (base cards, base dialogs, base presenters/view models) over concrete duplication.
- **Shared Kernel — exactly 2 symbols, no more** (`EPIC-008`'s ADR §4.1): `src/domain/` and `src/application/` may import **only** `sagittarius_engine.domain.i_domain_event.IDomainEvent` and `sagittarius_engine.domain.base_event.BaseEvent`.

  **Reason:** every domain event must inherit `BaseEvent` so the engine can build its registry/catalog and audit tooling (which events exist, who listens, how long they run); copying `BaseEvent` into Elite would create two inheritance trees that cannot recognize each other — precisely what the registry exists to prevent. This is a **Shared Kernel** in the DDD sense: small, named, written down as a rule, jointly owned by both sides.

  **Everything else from the engine MUST go through a port** in `src/application/ports/`, with an adapter wrapping it in `src/infrastructure/engine_adapters/`. `EPIC-008F` built 3 ports: `IEventPublisher` (replacing `IEventBus`), `IConfigReader` (replacing `IConfig`), `ICommandDispatcher` (replacing `IDispatcher`). **The Presentation layer is not bound by this** — it may know the engine directly (`BasePresenter`, `QtEventBridge`, `IEventBus.on/off`); the **listening** direction only happens there, and `IEventPublisher` deliberately only has the **publishing** direction.

  **There is a locking test:** `tests/unit/domain/test_indicator_script_conventions.py` keeps an allow-list of exactly the 2 module paths above, plus 1 test that blocks widening the allow-list into a prefix (widening it to a prefix lets the whole engine back into the domain with no test noticing). Manual check:
  ```bash
  grep -rn "sagittarius_engine" src/domain src/application --include=*.py
  ```
  Adding any other engine import into those 2 layers is **wrong**, even "we only use 1 method" — that is exactly why `IConfigReader`/`ICommandDispatcher` exist.

---

## 4. Use Case Structure (CQRS)

- Every Application Use Case must reside in its own dedicated directory (e.g., `src/application/use_cases/<my_use_case>/`).
- The Command/Response definition must be separated from the Handler logic into multiple files (e.g., `command.py` and `handler.py`), and then exported cleanly via `__init__.py`.
- Never import engine-specific interfaces (like `sagittarius_engine.extensions.cqrs.ICommand`) into the Application layer. Use the layer's own pure Python `ICommandHandler` / `IQueryHandler` interfaces.

---

## 5. Abstraction-Level Separation

Splitting is the default: **the more files the better**; merging needs a reason, splitting needs no permission.

1. **Never in the same file:** two things at **different abstraction levels** MUST NOT live in one file. An interface/Port and its implementation; a base class and its subclasses; an abstract policy and how it reads the disk — one file each.
2. **Never in the same directory:** files at **different abstraction levels** MUST NOT share a `dir`. A directory is a layer, not a bin: `interfaces/` holds no implementations, `widgets/` (shared primitives) holds no concrete screens, `domain/` holds no infrastructure adapters. A directory that is mixing two layers must be split into subdirectories by layer — don't just rename files to tidy up.
3. **The only counterweight is Single-Scope Cohesion** ([`code-quality-rule.md`](code-quality-rule.md)), and it only wins when the definitions describe **the same lifecycle** (the enum + matrix of the same FSM; `StyleRole` + `_build_qss()`). "Same feature", "same screen", "often used together" are **not** enough to merge.
4. **Thresholds that force a split** (`EPIC-007` §3.4, applies to all new code): a file **>400 lines** or a class **>15 public methods**. Hitting the threshold means splitting, non-negotiable.
5. **Quick arbitration:** *"Does changing A force you to read/change B?"* Yes → same lifecycle, one file is fine. No → different layers, split. Evidence: `data_management_widgets.py` (**1.156 lines**) accidentally became the whole app's shared widget library because it mixed shared primitives with widgets specific to a single screen — 3 files across 2 other screens had to import across into it (`EPIC-007` §1).

---

## 6. Event Placement — Qt signal or Event Bus?

The question is not "signal or bus", nor "bridging signals are technical debt", but: **who owns this truth?**

> **A truth private to ONE screen** → internal Qt signal.
> **A truth of the SYSTEM, or needed by ≥2 screens** → Event Bus + exactly **one** normalizing Feed.

### 6.1 Separate the two problems that keep getting conflated

| | Problem | Correct mechanism |
| :-: | :--- | :--- |
| **A** | Getting data from a background thread to the main thread **safely** | Qt queued signal **or** `QtEventBridge` — both are correct |
| **B** | **Who is allowed to know about whom**; one truth handled redundantly in several places | Bus + exactly 1 normalizing subscriber (Feed), many places *displaying* it |

**A Qt queued signal is exactly the mechanism Qt designed for (A)** — not technical debt, not a workaround. A signal bridging worker → main thread is **correct** code, don't "clean it up". `QtEventBridge` can only replace signals emitted **from an event bus handler**; a background worker that never goes through the bus gains nothing from the bridge — deleting its signal pushes UI updates onto the worker thread, exactly the class of bug in [`BUG-031`](../../Tasks/bug_report/completed/BUG-031_cross_thread_timer_start_hangs_ui_during_backtest.md).

### 6.2 Classification — ask exactly one question

*"If another screen also wanted to know this, would that be absurd?"*

- **Absurd** → a private truth (`history finished loading`, `my stream started`, `my indicator finished computing`): internal Qt signal inside the presenter/controller. Pushing it onto the bus is a **leak** — every screen can hear it and the coupling surface balloons.
- **Reasonable** → a system truth (`health changed`, `background task died`, `sync progress`, `log`): onto the bus, with **exactly one** Feed listening and normalizing, and many screens *displaying*.

### 6.3 Promote when a second consumer actually appears — never before

This is a rule about **routing**, not about whether to create an abstraction (see §7). Promoting late is cheap (the worker already emits *something*; changing where it emits to is a local edit); pushing everything onto the bus up front is expensive and nearly irreversible — afterwards nobody dares delete a subscriber because nobody knows who is still listening.

### 6.4 Real evidence (measured 2026-08-25, `EPIC-008G`)

Counted across 3 presenters: **48 signals, 46 of them with exactly one listener.** The only fan-out is `ui_log_signal` (2 listeners) — which genuinely is a system truth, i.e. exactly the thing that *should* become a Feed; the code had already classified itself correctly. `EPIC-008G` §2 set the target "delete 48 bridging signals" because it conflated (A) with (B); measured for real, **47 of the 48 exist because of (A)**, and about 1 could be deleted. **Don't set targets by signal count** — with the wrong boundary, the number only leads you to break correct code.

---

## 7. Code must speak for itself — anything deferred or traded away needs an Interface

> **If something will be built later, or is a price you have knowingly accepted, then the code
> must contain an Interface / type / test that represents it. It must not live only in
> documentation.**

Documentation is something an agent has to go looking for; a type hits you in the face while reading the code. Evidence: `EPIC-008G` §2 set the wrong target "delete 48 bridging signals" even though its author **had** the rules at hand — because the place where the signals are declared said nothing about them being thread bridges. A correct rule with mute code is a useless rule.

### 7.1 Two forms, two ways of expressing them

| Form | What the code must contain |
| :--- | :--- |
| **Will be built later** (a known extension point, a later phase already agreed) | A **type/ABC/base class** acting as the landing spot, with a docstring giving the extension recipe. A later agent can `grep` it and imitate it. |
| **A price knowingly paid** (a deliberate trade-off) | A **test locking the current behavior** + a docstring stating what was given up and why it is acceptable. Not just a one-line note. |

- **Trade-off:** `EPIC-008F` dropped `frozen=True` on 4 domain events so they could inherit `BaseEvent` — instead of deleting the immutability test it **turned it into a test locking the new behavior** (`test_signal_generated_event_is_no_longer_frozen`) with the reason and the conditions for restoring it.
- **Extension point:** `SystemErrorFeed` is the first Feed, `HealthFeed`/`SyncProgressFeed` are already agreed to be coming → there must be a `BaseFeed` as the contract, so that promoting a private truth onto the bus (§6.3) has a **named landing spot**.

### 7.2 Always favor abstraction — a class is a **contract**, not a lump of code

> When writing a class, **evaluate its extensibility and its API first**, then write the body.
> The default is **to have an abstraction**: a class must be a **contract** with other classes, not
> an implementation block whose guts other places have to know to use it.

When adding a new class, ask in order: (1) **who will call it, and what do they need to see?** — that is the API, designed up front rather than extracted afterwards; (2) **where is extension likely?** (swapping the backend, swapping the data source, adding a variant) — that spot must be an `abc.ABC` / Port so a later person can replace it without touching consumers; (3) **is the consumer forced to know internal details?** — if so the contract is not yet good enough, tighten it.

Abstraction here is **not** "spawn another middle layer for its own sake": it is that **a class's public surface must be programmable against**, and that any point known to be changeable has an abstract type representing it.

> ⚠️ The old threshold *"only create an abstraction once there are ≥2 real needs"* (`EPIC-006`'s ADR §4) **was dropped on 2026-08-25**; `EPIC-006`'s ADR and `EPIC-007`'s design still cite it, so read them knowing it is no longer in force. The lesson that still holds: the 4 stub cards (`ActionCard`/`FormCard`/`StreamCard`/`TableCard`) were wrong not for lacking abstraction but for **guessing the wrong shape** of something that did not exist yet — favoring abstraction means designing the API of what you are writing now, not guessing at what nobody needs yet.

### 7.3 No wriggling out via docstrings

Docstrings/comments are a **supplement**, not a substitute. A comment explains *why*; types and tests are what **force** the next person down the right path, and what **breaks** when reality changes. A decision that lives only in prose has nothing to detect when it stops being true — the very mechanism that let `.agents/context/` rot for 3 weeks (`EPIC-002`).
