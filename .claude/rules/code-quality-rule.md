---
description: Typing boundaries, top-level imports only, single-scope FSM cohesion, schemas, and suppression rules.
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
---

# SYSTEM PROMPT: CODE QUALITY & HYGIENE

Enforce repository-specific hygiene constraints across all Python modules:

1. **Typing & Boundaries:** Explicit type annotations on signatures and attributes; zero `Any` at seams (`CS-001`). Model data via frozen dataclasses, value objects or `Enum`, never loose dicts/tuples. Mypy covers `src+scripts`; `presentation` is excluded (governed by review D5). `[gate; review: D5]`
2. **Top-Level Imports Only:** Zero function-local imports. All imports live at the file head; the only exception is a top-level `if TYPE_CHECKING:` block. `[review: D4]`
3. **Single-Scope Lifecycle Cohesion:** Definitions describing a single lifecycle (FSM states, events, transition matrix, UI modes) must live together in one file (e.g. `*_fsm_matrix.py`). Lifecycle cohesion overrides feature-based slicing. `[review: D8]`
4. **Constants & Schemas:** Strategy and indicator parameters route through schemas; shared keys live in `config_keys.py` or `constants.py`. `[gate: ruff PLR2004]`
5. **No Bare Suppressions:** Never use bare `# noqa`. Per-file ignores live exclusively in `pyproject.toml` with documented rationale. `[gate; review: D3]`
6. **Implementation Framing Flow:** Before writing code, frame: (a) *Boundary:* Identify target module and layer; (b) *Seam Now, Variant Later (P7):* Establish explicit interfaces/ports for extensibility, but implement only today's variant—reject speculative over-engineering; (c) *Proven Patterns (P5):* Reuse existing repo patterns (CQRS, FSM, Coordinator) over novel inventions; (d) *Pythonic Separation:* Use classes for stateful lifecycles or polymorphism; use pure functions and frozen dataclasses for data transforms. Split abstraction levels across files (`architecture-rule.md` §5). `[review: A4, C6, C9]`
