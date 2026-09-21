---
description: Error handling, failing correctly, representing invalid states, and explicit dependencies.
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
---

# SYSTEM PROMPT: ERROR HANDLING & FAIL CORRECTLY

1. **No Silent Swallowing:** Never silently swallow errors. `[review: B2]`
2. **Actionable Catching:** Catch errors only when you can handle, translate, recover, or add meaningful context. `[eye]`
3. **Precise Exception Scopes:** Do not catch broader exceptions than necessary (e.g. avoid bare `except Exception:` unless converting at seam). `[review: D1]`
4. **Preserve Error Context:** Always preserve error context (`raise ... from exc`). `[eye]`
5. **Control Flow:** Do not use exceptions for ordinary control flow when the language or domain model provides a clearer mechanism. `[eye]`
6. **No Fabricated Fallbacks:** Do not fabricate fallback behavior merely to avoid an error. `[review: B4]`
7. **Fail Correctly:** Do not hide invalid states with arbitrary defaults, empty values, silent recovery, or swallowed exceptions. Handle invalid states according to the domain contract. `[review: B4]`
8. **Representing Invalid States:** Make invalid states hard to represent using types, schemas, and immutability. `[review: C4]`
9. **Explicit Dependencies:** Dependencies must be explicit via constructor parameters or ports, never hidden global state or lazy fallbacks. `[review: C10]`
10. **Isolate Error Handling:** Keep `try/except` blocks tightly scoped to the specific statement that can fail; do not wrap broad blocks of business logic in a monolithic `try` block that obscures intent. `[review: B4, D1]`
11. **Domain Invariants Over Sentinel Codes:** Never use sentinel error return codes (e.g. `-1`, `None`) to signal failure where domain exceptions or explicit `Result` types express the outcome directly. `[review: C4]`

