---
name: Python Code Quality Rule
description: Typing, readability, immutability/pure functions, và các quy tắc chất lượng cứng — no magic numbers, no nested loops, no God objects, no function-local imports, Single-Scope Cohesion.
trigger: on_file_change
patterns:
  - src/**/*.py
  - scripts/**/*.py
---

# PYTHON CODE QUALITY RULES

Áp cho mọi file Python trong `src/` và `scripts/`.

Quyết định **kiến trúc** (Port nằm đâu, file nào thuộc tầng nào, tách file
theo abstraction level) không nằm ở đây — xem
[`architecture-rule.md`](architecture-rule.md).

---

## 1. Strong Typing & Type Safety

1. **Strong Typing & Type Safety:**
   - Always use explicit type annotations for all function signatures, parameters, return values, and class attributes.
   - Strictly avoid using `Any`. Use `Union`, `Optional`, `Generics`, or `TypeVar` where flexibility is needed.
   - Use `dataclasses` (with `frozen=True` where possible) or `Pydantic` models instead of raw dictionaries for complex data structures. Model data with proper structures (dataclasses, value objects, `Enum`) instead of loose primitives or tuples.

---

## 2. Readability & Clean Code (Over Brevity)

3. **Readability & Clean Code (Over Brevity):**
   - Follow PEP 8 guidelines. Prioritize explicit and self-documenting code over short one-liners.
   - Do NOT use complex, nested list comprehensions or multi-line `lambda` expressions when a clear `for` loop or named helper function is more readable. Do not use `lambda` for non-trivial callbacks.
   - Keep functions small, focused, and single-purpose (Single Responsibility Principle). Use explicit, descriptive variable names.

---

## 3. Immutability & Pure Functions (No Side Effects)

4. **Immutability & Pure Functions (No Side Effects):**
   - Strive for pure functions: functions should depend only on passed arguments and produce deterministic return values.
   - Never mutate passed arguments in-place. Return new instances or modified copies instead.
   - Strictly avoid mutable default arguments (e.g., NEVER use `def func(items=[]):`).
   - Isolate side effects (I/O, DB calls, network requests) inside dedicated adapter/boundary classes.

---

## 4. Strict Code Quality Rules

7. **Strict Code Quality Rules:**
   - **No Magic Numbers & Named Constants:** Strictly avoid using raw numbers or magic strings in code. Define them centrally as named constants or configuration keys (`config_keys.py`, `user_config.json`, `constants.py`). Strategy/indicator parameters must be declared dynamically via parameter schemas (`input_int`, `input_float`, etc.).
   - **No Nested Loops:** Avoid deep nesting of loops (e.g. `for` inside `for` inside `while`). Extract nested logic into separate helper functions to reduce cyclomatic complexity and improve testability.
   - **No God Objects:** Strictly avoid creating massive classes or modules that know too much or do too much. Delegate responsibilities (e.g. CLI parsing, bootstrapping, event handling) into dedicated modules.
   - **Abstract Low-Level Logic:** Do not write verbose, low-level OS/File system operations (like deep `os.path` joins or byte-level manipulation) directly in application or composition root layers. Extract them into common utility classes.
   - **No Function-Local / Lazy Imports (Tuyệt đối không dùng Local Import):** All module, class, function, and type imports MUST be declared at the top of the file (top-level imports) adhering strictly to PEP 8. Never place `import ...` inside functions, methods, slots, test cases, or nested scopes (the only exception is `if TYPE_CHECKING:` guards at top level).
   - **Single-Scope Cohesion & Colocation (Gom chung các thành phần liên quan vào cùng 1 Scope / Single Source of Truth):** Tightly coupled components that define the same domain lifecycle, state machine, or feature configuration MUST be co-located within the same single file or module scope (e.g., FSM State Enum + FSM Event Enum + Transition Matrix + UI Mode mappings in a single `*_fsm_matrix.py`). Do NOT fragment tightly coupled definitions across multiple scattered files where understanding or modifying a single feature lifecycle requires jumping across 4-5 distant modules. Related enums, schemas, transition tables, and constants belonging to a single concept must reside together as a single source of truth.

> **Đối trọng của Single-Scope Cohesion là Abstraction-Level Separation**
> ("khác abstraction level thì không chung file, không chung thư mục", cùng
> ngưỡng buộc tách >400 dòng/file và >15 method công khai/lớp) —
> [`architecture-rule.md`](architecture-rule.md) §5. Lưỡng lự thì đọc cả hai.
