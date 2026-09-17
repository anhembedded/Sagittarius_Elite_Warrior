---
description: Traps that produced broken tests here — one line each, with the bug or case-study id. Loads with every tests/ file.
paths:
  - "tests/**/*.py"
---

# Pitfalls — tests
1. Computing a test's expected value in your head — run the real code (`BOT-106A`, `stdev()` of a constant series is 1e-16).
2. Floats compared with `== 0` or `if value:` — `math.isclose`.
3. Asserting counts (`len(cards) == 9`) — assert presence and order.
4. Full-dict equality on `to_dict()` — assert the fields you care about.
5. A test double shaped from the calls your code makes (`BUG-124`, `CS-001`) — derive it from the interface or use the real thing.
6. Proving a class works and calling that the program working (`BUG-126`, `CS-002`; `BUG-127`, `CS-003`) — ask what constructs it, assert against the real graph.

A new trap is one line here with its id; the long form is a case study (`Docs/CASE_STUDIES/README.md`).
