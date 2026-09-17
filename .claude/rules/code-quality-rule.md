---
description: Typing, readability, immutability, and the hard rules — no magic numbers, no nested loops, no God objects, no lazy imports, Single-Scope Cohesion.
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
---

# Python code quality

Applies to every Python file in `src/` and `scripts/`. Where things *live* is `architecture-rule.md`.

## 1. Typing
Explicit annotations on every signature, return and class attribute. No `Any` where `Union`, `Optional`, `TypeVar` or a generic fits — an `Any` at a seam switches type checking off past it (`CS-001`). Model data as frozen dataclasses, value objects or `Enum`, never loose dicts and tuples. `[gate: mypy over src+scripts, presentation excluded — there review D5 is the only check]`

## 2. Readability
PEP 8; explicit over clever; no nested comprehensions or multi-line lambdas where a loop or a named helper reads better; small single-purpose functions; descriptive names. `[gate: ruff N; eye]`

## 3. Immutability and pure functions
Depend on arguments, return new values, never mutate an argument in place, never a mutable default; side effects (I/O, DB, network) live in adapter classes. `[gate: ruff B006; review: D10]`

## 4. Hard rules
- **No magic numbers or strings.** Named constants or config keys (`config_keys.py`, `constants.py`); strategy/indicator parameters through parameter schemas. `[gate: ruff PLR2004]`
- **No nested loops** — extract a helper. `[eye]`
- **No God objects** — a class or module with a second reason to change is split. `[review: D9]`
- **No low-level OS/file/byte work** inline in application or composition-root code — a utility class. `[review: D11]`
- **No function-local imports.** All imports at the top of the file; the only exception is a top-level `if TYPE_CHECKING:` block. `[review: D4]`
- **Single-Scope Cohesion.** Definitions describing one lifecycle (an FSM's state enum, event enum, transition matrix, UI-mode map) live in one file, e.g. `*_fsm_matrix.py`. Counterweight: `architecture-rule.md` §5 — different abstraction levels never share a file; the two collide only on "same lifecycle" vs "same feature", and lifecycle wins. `[review: D8]`
- Ruff's `S` (Bandit), `B`, `SIM`, `ERA`, `N`, `PLR2004` rules are part of the gate; a per-file ignore lives in `pyproject.toml` with an inline reason, never a bare suppression. `[gate; review: D3]`
