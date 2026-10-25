---
description: Traps that produced broken tests here — one line each, with the bug or case-study id. Loads with every tests/ file.
paths:
  - "tests/**/*.py"
---

# SYSTEM PROMPT: TEST PITFALLS & FAILURE TRAPS

1. Computing a test's expected value in your head — run the real code (`BOT-106A`, `stdev()` of a constant series is 1e-16).
2. Floats compared with `== 0` or `if value:` — `math.isclose`.
3. Asserting counts (`len(cards) == 9`) — assert presence and order.
4. Full-dict equality on `to_dict()` — assert the fields you care about.
5. A test double shaped from the calls your code makes (`BUG-124`, `CS-001`) — derive it from the interface or use the real thing.
6. Proving a class works and calling that the program working (`BUG-126`, `CS-002`; `BUG-127`, `CS-003`) — ask what constructs it, assert against the real graph.
7. A parametrized test whose id is a whole log line (`... - ERROR - ...`): the id is printed in the run log, and the log scan fails the gate on `- (WARNING|ERROR|CRITICAL) -` — give the cases short `ids=` (`BOT-199`).

8. A journey over a booted app that counts or unpacks everything on a fake Discord transport: the app's own heartbeat (the housekeeping thread's first pass, one second in) lands beside the alert on a slow runner and the count is wrong. Read posts through `tests/discord_posts.py` (`BUG-252`).

9. A test that expects a value which changes with the calendar (a zone abbreviation such as `BST`/`EDT`, a daylight-saving offset) written down as a literal: it is true until the clock changes. Compute it at the same moment as the code under test (`_machine_in(key)(datetime.now(UTC)).tzname()`), or freeze the clock (`BUG-269`).

A new trap is one line here with its id; the long form is a case study (`Docs/CASE_STUDIES/README.md`).
