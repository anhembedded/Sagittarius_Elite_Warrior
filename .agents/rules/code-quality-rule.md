---
name: Code Quality Rule
description: Typing, readability, immutability/pure functions, and the hard quality rules — no magic numbers, no nested loops, no God objects, no lazy imports, Single-Scope Cohesion.
trigger: on_file_change
patterns:
  - <SRC_DIR>/**
  - scripts/**
---

# CODE QUALITY RULES

Applies to every source file under `<SRC_DIR>` and `scripts/`.

**Architectural** decisions (where an interface lives, which layer a file
belongs to, splitting by abstraction level) are not here — see
[`architecture-rule.md`](architecture-rule.md).

---

## 1. Strong typing

- Explicit annotations on **every** signature: parameters, return values, class
  attributes.
- **Avoid "any" types absolutely** (`Any`, `object`, `any`, `interface{}`).
  Where flexibility is needed use unions, optionals, generics, type variables.
- Use **structured types** (dataclass/struct/record, immutable where possible;
  or a validating model) instead of raw dicts/maps and anonymous tuples. Model
  data with value objects and enums rather than loose primitives.

## 2. Readability over brevity

- Follow the language's style guide. Prefer explicit, self-documenting code
  over a short one-liner.
- Do **not** use complex nested comprehensions or multi-line lambdas where a
  clear loop or a named helper reads better. No lambdas for non-trivial
  callbacks.
- Keep functions small, focused, single-purpose. Use descriptive names.

## 3. Immutability & pure functions

- Aim for pure functions: depending only on their arguments, returning
  deterministic values.
- **Never mutate a passed argument in place.** Return a new instance or a
  modified copy.
- **Strictly avoid mutable default arguments** (the classic
  `def f(items=[]):`).
- Isolate side effects (I/O, DB, network) inside dedicated adapter/boundary
  classes.

## 4. Four hard rules

- **No magic numbers, use named constants.** No raw numbers or strings in code.
  Declare them centrally as named constants or configuration keys. Algorithm and
  strategy parameters must be declared through a parameter schema, not scattered.
- **No nested loops.** Avoid deeply nested loops. Extract the inner logic into a
  helper to reduce cyclomatic complexity and improve testability.
- **No God objects.** No huge class/module that knows or does too much. Delegate
  (CLI parsing, bootstrapping, event handling) into dedicated modules.
- **Abstract low-level logic.** Don't write detailed OS/filesystem operations
  directly in the application or composition-root layers. Extract them into
  utilities.

## 5. No function-local / lazy imports

**Every** import is declared at the top of the file. No imports inside
functions, methods, callbacks, test cases, or nested scopes. (The only
exception: a type-checker-only guard, still at top level.)

Lazy imports hide a circular dependency instead of fixing it, and make import
cost appear at random points during runtime.

## 6. Single-Scope Cohesion & colocation

Tightly coupled components describing **one** lifecycle, one state machine, or
one feature configuration MUST live in the same file/scope — the canonical
example: the State enum + Event enum + transition matrix + UI-mode mapping of
**the same** FSM.

Do **not** fragment tightly coupled definitions across files, so that
understanding or changing a single lifecycle requires jumping through 4-5
distant modules. Enums, schemas, transition tables and constants belonging to
**one** concept must live together as a single source of truth.

> **Its direct counterweight: abstraction-level separation**
> ([`architecture-rule.md`](architecture-rule.md) §5) — "different abstraction
> levels don't share a file or a directory", plus the mandatory split
> thresholds of **>400 lines per file** and **>15 public methods per class**.
> Read **both** when torn. Quick arbitration: *does changing A force me to edit
> B?* Yes → same file; no → split.

---

## 7. Changing something SHARED: branch to preserve old behaviour

These two failure classes only appear when editing something with many existing
callers — and both break code **unrelated** to your change.

- **Adding a field to a shared type (especially an immutable one) means the new
  field ALWAYS needs a default value.** A shared type typically has hundreds of
  direct construction sites in tests; a missing default breaks all of them at
  once, with nothing actually wrong at the business level.
- **Changing a shared formula or rule means keeping the old branch VERBATIM for
  the old case**, and using the new formula only when genuinely in the new case.

  > **Real evidence:** a change added a multiplier to a calculation; the old
  > formula was **completely wrong** whenever the multiplier differed from 1,
  > yet remained correct for all existing data. The correct handling was to
  > branch on the multiplier — **the proof being that 47 existing tests passed
  > without a single line changed.** If your fix requires editing old tests,
  > stop and ask: am I fixing a bug, or changing behaviour that was promised?

---

## Appendix — examples per stack *(swap for your language)*

| Rule | Python | TypeScript |
| :--- | :--- | :--- |
| Structured types | `@dataclass(frozen=True)`, Pydantic models | `interface` / `type`, `readonly`, zod schemas |
| Avoiding "any" | ban `Any`; use `Union`/`Optional`/`TypeVar` | `noImplicitAny`, ban `any`; use generics, unions |
| Immutability | `frozen=True`, `tuple`, `MappingProxyType` | `readonly`, `as const`, `Object.freeze` |
| Type-checker-only guard | `if TYPE_CHECKING:` | `import type { ... }` |
| Read-only lint/format | `ruff check` / `ruff format --check` | `eslint` / `prettier --check` |
