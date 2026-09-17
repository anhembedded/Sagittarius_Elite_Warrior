---
description: How to write a test that can fail — what each level proves, no sleeps, invariants, boundary analysis with mutation checks, doubles from the interface, wiring asserted against the real graph.
paths:
  - "tests/**/*.py"
---

# Writing tests

`ci-rule.md` holds the run commands, the four levels and red-gate handling; `bug-fix-rule.md` owns a regression test (written first, confirmed red). For the module architecture the layer-by-layer proof map is `Docs/HLD/10_test_strategy.md`.

## 1. What each level proves
- Every feature names its proof at each of the four levels, or names the existing test that already proves the exact behaviour. `[review: E1]`
- **Sanity** (`Tasks/epics/EPIC-009_sanity_tier_redesign/DECISION_2026-08-25_sanity_model_and_execution.md`): one real boot per session (`booted_app`); every assertion scans a real source of truth (registered use cases, navigable routes, packages on disk) so **a new feature adds zero sanity tests**; `diagnostic_guard` fails on any Qt message, WARNING+ record or `warnings.warn` during boot/construct/shutdown; the only substitution is the network boundary at configuration (`binance_fake_server.py`), never a hand-written port substitute (`BUG-026`/`027`); no business facts; `--self-check` launches the real entry point as a subprocess. `[review: E5, E6; contract: .claude/skills/test-health/contract.json]`
- **Integration**: deterministic journeys in `tests/integration/`, real input, wait on a terminal signal/state, seeded/fake boundaries, never a live exchange.
- **Desktop E2E**: a reported GUI defect or native rendering change keeps an opt-in harness on a real display with real `QTest`/`qtbot` input and clean Qt messages.
- **`tests/testnet/`**: real Futures Testnet, opt-in twice (`ci-rule.md` §3a); assert invariants (`FILLED`, a position back to zero), never figures; clean up in `finally`; wait on a named condition.

## 2. Writing a test that can fail
- **No timing sleeps.** Wait on a named signal, FSM state, terminal event or bounded `qtbot.waitUntil`. Give every critical control a stable `objectName`. `[review: E3]`
- **Financial invariants**: reject `NaN`/inf, non-negative fees, equity/trade/metrics consistent, identical output for identical input; every new execution mode or fee model extends them.
- **Boundary Value Analysis, not enumeration**: one representative per equivalence class plus the values at and around each boundary. **Mutation-verify** any consequential calculation: flip the operator, shift the boundary, invert the sign — the test must go red (`BOT-106A`: `stdev()` of a constant series is 1e-16, not 0.0; compare floats with `math.isclose`). Do not test states an invariant already makes unreachable. `[review: E7]`
- **Business acceptance for trading features**: assert the composition of the result (a long-only run has no short trade; a short-enabled strategy shows the SHORT fill, its filter, PnL direction and the fill marker), not that a run completed.
- **A double's shape comes from the interface, never from the calls your code makes** (`CS-001`). Subclass the real collaborator or derive from the ABC; where the real thing is cheap and in-memory (`MemoryEventBus`, a fake repository), use it. A double answering whatever the code asks always passes. `[guard: test_no_foreign_port_is_mocked.py, test_engine_port_calls_are_real.py; review: E13]`
- **A test constructs its subject, so it proves nothing about wiring** (`CS-002`, `CS-003`). Where the behaviour *is* a wiring — subscribes, registers, binds, starts at boot — assert it against the graph `create_app()` builds. The tell: a setup line that production is missing. `[guard: test_a_bus_subscriber_is_constructed.py, test_every_resolved_type_is_bound.py; review: E15]`
- **A wiring test must fail when the line is removed.** Break the line, run the file, restore (`pr-review` E12): 22 green tests once covered two deletable `textEdited` connections. `[review: E12]`
- No hard-coded counts (`len(cards) == 9`), no full-dict equality on `to_dict()`, no float `== 0`; assert what is meaningful. A new field on a frozen dataclass has a default. `[review: E7, E8]`
- Every path-scanning guard has a row in `tests/unit/architecture/scanned_roots_registry.py` and fails on an empty scan; a new guard's docstring states **`Retire when:`** — the condition under which it is deleted. `[guard: test_scanned_roots_are_not_empty.py]`
