---
name: Architecture Rule
description: SOLID, layer boundaries, ports/interfaces and implementer completeness, explicit contracts (no implicit duck-typing), use cases, and abstraction-level separation.
trigger: always_on
---

# ARCHITECTURE RULES

Read this file when: designing or restructuring, adding or changing an
interface, adding a use case, deciding which file or directory something
belongs in, or splitting a file/class that has crossed a threshold.

Pure code-quality rules (magic numbers, nested loops, typing, immutability) are
**not** here — see [`code-quality-rule.md`](code-quality-rule.md).

> [!IMPORTANT]
> **Decision doctrine when the architecture is hard or ambiguous.**
> Several directions are defensible and none is absolutely right → decide by
> **proven design patterns**. **Don't be afraid to redesign** an existing part
> if the current shape is a *hard design* (rigid, patched, hard to extend) —
> "it currently works" is not a reason to keep it. When torn: **look at what
> large, community-proven projects do** — prefer a pattern with a name and wide
> precedent over inventing a new shape nobody has validated.
>
> The agent **decides these itself** — do not ask the user about every small
> design choice. Ask only when the trade-off is genuinely large, irreversible,
> or outside pure design (`push`, delete, overwrite — see `../ONBOARDING.md`
> §6; this doctrine does **not** loosen that group).
>
> It decides **which direction is right**, not **how the process runs**: task
> and design/ADR still come before code, and the CI and commit gates still
> apply unchanged.

---

## 1. SOLID

Apply it where it makes the code clearer or more testable; don't force an
abstraction onto a small piece that is nearly certain never to change just to
tick a box.

- **S — Single Responsibility:** one class/module, **one** reason to change.
  Split by responsibility into separate files instead of piling unrelated logic
  into one place.
- **O — Open/Closed:** prefer extending via a new class/strategy over editing
  already-tested logic; put the extension point behind an interface.
- **L — Liskov:** a subclass must work anywhere its base type is expected — no
  "not implemented" throws on inherited methods, no narrowing of accepted
  input, no weakening of a guarantee the base type promised.
- **I — Interface Segregation:** keep interfaces narrow and role-specific;
  don't make an implementer satisfy methods it has no use for.
- **D — Dependency Inversion:** high-level modules depend on abstractions, not
  on concrete implementations.

---

## 2. Abstraction & decoupling

- Define explicit abstractions for repositories, services, and every client
  that reaches outside the system.
- Prefer **dependency injection** over hard-coded construction inside business
  logic.
- **No multiple inheritance.** Use composition; flatten interfaces where
  needed, to avoid complex method resolution order.
- **Every implementer of an interface must stay complete, everywhere.** When an
  interface gains a method, **every** class implementing it must be updated in
  **the same change** — not just the main production implementation. `grep` for
  implementers across `<SRC_DIR>`, `scripts/`, **and** `<TEST_DIR>`.

  > **Real evidence:** a test double / probe script left behind after an
  > interface change still constructed fine until the exact moment someone ran
  > it, then failed with `TypeError: Can't instantiate abstract class`. The
  > second occurrence slipped through because the `grep` scope omitted
  > `scripts/`. **A linter cannot catch this class of defect** — verifying
  > implementer completeness across files is a type checker's job. But don't
  > rely on the tool alone: the `grep` is part of making the change.

### 2.1 Contracts must be explicit — no implicit duck-typing

> **Every contract that crosses a boundary (module ↔ module, consumer ↔ port,
> view ↔ controller) MUST be a named type. A contract may never exist only as
> "call it and see whether the method is there".**

| | Forbidden | Required |
| :--- | :--- | :--- |
| **Implicit contract** | An unannotated parameter whose consumer then calls 15 of its members; capability probing via `hasattr`/`getattr`/`in` | — |
| **Explicit contract** | — | A named type: an interface class **or** a structural type (Protocol / `interface` / trait) |

**A named structural type is NOT implicit duck-typing.** It has a name, it is
greppable, a type checker can verify it. The only thing it drops is **required
inheritance** — not the contract.

#### Selection order — not to be inverted

1. **An inherited interface class (ABC / `implements`) is the default**, and
   the "implementer completeness" rule in §2 applies in full.
2. **A structural type only when inheritance is impossible or forbidden by this
   repository** — and its docstring **MUST state which reason applies**:
   - **(a)** Inheritance causes a metaclass conflict or the framework forbids it
     (many UI frameworks disallow a class inheriting from two framework bases).
   - **(b)** §2's "no multiple inheritance" blocks it: the implementer already
     has its own base class.
   - **(c)** The implementer is a third-party class this repository cannot edit.
3. **Not (a)/(b)/(c) → it must be an interface class.** "More convenient" is
   not a reason.

#### A structural type is not an escape from completeness

It must describe **exactly and completely** what the consumer actually uses.
Adding a new call to the contract without declaring it on the type is **a
return to the implicit duck-typing this section forbids**, only now with a file
that looks like an interface standing next to it for reassurance.

The difference is how they break: an omission on an inherited interface
**fails at construction**; an omission on a structural type **breaks nothing at
all** until the type checker runs — so for structural types the type checker is
not a "safety net", it is **the only mechanism**. In any layer **excluded from
type checking** (very common for the UI layer), a structural type living there
has **no static verification whatsoever** — it is documentation.

#### Command to check when a contract looks implicit

```bash
# What is the consumer actually using off `x`? (drop -h to see which file each hit is in)
grep -rnoE "(self\.)?_?<attribute_name>\.[a-zA-Z_]+" <SRC_DIR>/<directory>/
```

The remaining member count **after discarding hits that don't belong to the
boundary under review** must match the declared type. A mismatch means the
contract has drifted. (Don't skip the "see where each hit comes from" step: in
one real measurement, the 15th hit came from a developer harness constructing
the object itself, outside the boundary being examined.)

**Better than a one-off `grep`: a test that locks both directions.** A `grep`
is something you must remember to run; a test runs itself. That test walks the
source and goes red **both ways**: a member used but not declared (the contract
has gone implicit again), **and** a member declared but used by nobody (a dead
contract). It must also lock the **count** — the two directions compare *sets*,
so removing one and adding one cancels out and stays green.

> **Real evidence:** a contract between two layers had **14 members** genuinely
> in use and **no type declaring any of them**. Meanwhile the *official*
> interface in the codebase declared exactly one method that **no implementer**
> implemented and **nobody** referenced. The real contract and the declared
> contract were two different things — precisely the cost of implicit
> duck-typing: the contract drifts and nothing breaks.

---

## 3. Layer boundaries

- Respect the dependency direction strictly: **Domain** (pure) → **Application**
  (use cases / ports) → **Interface Adapters** (CLI/UI, presenters) →
  **Infrastructure** (DB/API/frameworks). Dependencies point **inward** only.
- Never let infrastructure concerns (an ORM, an HTTP client, a framework base
  class) leak into Domain or Application.
- Prefer building reusable base layers over duplicating implementations.

### 3.1 A Shared Kernel, if any, is a few symbols, written into law, with a test locking it

When two repositories/modules must share a few types (a marker type, a base
event), that is a **Shared Kernel** in the DDD sense: a small region, **named,
written down as a rule, jointly owned** — not "an exception for convenience".

- List the permitted symbols **exactly and exhaustively**, as a list, never as
  a prefix.
- **Everything else goes through a port**, with the adapter wrapping it living
  in the infrastructure layer.
- **A test must lock that allow-list**, plus a separate test forbidding its
  widening into a prefix (a prefix lets the whole library back into the domain
  with no test noticing). Manual check:
  ```bash
  grep -rn "<library_name>" <SRC_DIR>/domain <SRC_DIR>/application
  ```
- Any other import into those two layers is **wrong**, even "we only use one
  method from it" — that is exactly why those ports exist.

---

## 4. Use case structure

- Every use case lives in its own directory.
- The command/response definition is separated from the handler logic
  (`command.py` + `handler.py`, or the equivalent), exported cleanly from the
  package entry point.
- Never import framework-specific interfaces into the Application layer — use
  that layer's own pure interfaces.

---

## 5. Abstraction-level separation

**Splitting is the default. More files is better; merging needs a reason,
splitting needs no permission.**

1. **Not in the same file:** two things at **different abstraction levels** MUST
   NOT live in one file. An interface and one of its implementations; a base
   class and its subclasses; an abstract policy and how it reads from disk —
   each gets its own file.
2. **Not in the same directory:** files at **different abstraction levels** MUST
   NOT share a `dir`. A directory is a **layer**, not a bucket: `interfaces/`
   holds no implementations, a shared-primitives directory holds no
   screen-specific widget, `domain/` holds no infrastructure adapter. A
   directory mixing two layers gets **split into sub-directories by layer** —
   don't just rename files to look tidier.
3. **The only counterweight is Single-Scope Cohesion**
   ([`code-quality-rule.md`](code-quality-rule.md)), and it wins **only** when
   the definitions describe **the same lifecycle**. "Same feature", "same
   screen", "usually used together" are **not** the same abstraction level and
   are **not** enough to merge.
4. **Mandatory split thresholds:** a file **>400 lines** or a class with **>15
   public methods**. Hitting the threshold means splitting — not negotiable.
5. **Quick arbitration:** *"Does changing A force me to read or edit B?"* Yes →
   same lifecycle, may share a file. No → different layer, split.

> **Real evidence:** a 1,156-line file accidentally became the whole app's
> shared widget library because it mixed shared primitives with one screen's own
> widgets — 3 files across 2 other screens had to import into it.

---

## 6. Two topics that moved into their own files

They sit at a different abstraction level from everything above (this file is
about **static structure**; those two are about **information flow** and about
**encoding intent**) — so per §5 of this very file, they don't share a file
with it:

| Question | Read |
| :--- | :--- |
| Does this truth travel by internal signal or over the event bus? | [`event-rule.md`](event-rule.md) |
| How must deferred work / an accepted trade-off show up in the code? | [`design-intent-rule.md`](design-intent-rule.md) |
