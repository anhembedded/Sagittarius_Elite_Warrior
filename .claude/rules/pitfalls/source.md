---
description: Traps that produced broken source here — one line each, with the bug id. Loads with every src/ file.
paths:
  - "src/**/*.py"
---

# SYSTEM PROMPT: SOURCE PITFALLS & IMPLEMENTATION TRAPS

1. A new field on a frozen dataclass without a default — hundreds of call sites break.
2. Changing a shared formula without a branch that keeps the old behaviour byte-for-byte (`BOT-114`).
3. A port gains an abstract method and only the main implementer changes — grep `src/`, `scripts/` **and** `tests/` (`BUG-026`).
4. Optimising from a micro-benchmark alone (`BOLT-001`) — profile the whole path with `cProfile` first, pick the target from the profile, micro-benchmark to confirm.

A new trap is one line here with its id; the long form is a case study (`Docs/CASE_STUDIES/README.md`).
