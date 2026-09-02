---
name: Testing Rule
description: How to write tests correctly — what each level proves, async without sleeps, financial invariants, Boundary Value Analysis + mutation-verify, business acceptance for trading features.
trigger: on_demand
---

# TESTING RULES — how to WRITE tests

**Division of roles:** [`ci-rule.md`](ci-rule.md) holds the CI *run commands*,
the four-level test contract, and what to do when the gate is red; this file
holds *how to write* a test. For bug fixes, [`bug-fix-rule.md`](bug-fix-rule.md)
is the authority — the regression test must be written **before** the fix and
must be confirmed failing for the right reason.

---

## 1. What each test level proves

- **Four required test levels:** Every feature defines its proof across the
  four levels in `.agents/rules/ci-rule.md` — Unit, Integration, Sanity and
  Desktop E2E. A change may add no new test only when an existing test at the
  relevant level already proves the exact new behavior; name that evidence in
  the task/report.
- **Sanity:** Proves the real composition root exists and assembles in
  silence — model, decisions and full failure-mode catalogue in
  [`Tasks/epics/EPIC-009_sanity_tier_redesign/DECISION_2026-08-25_sanity_model_and_execution.md`](../../Tasks/epics/EPIC-009_sanity_tier_redesign/DECISION_2026-08-25_sanity_model_and_execution.md).
  Rules that follow from it:
  - **Adding a feature/screen adds zero new tests to `tests/sanity/`.** Every
    assertion scans a real source of truth (every registered use case, every
    navigable route, every screen package on disk) — never a hand-written
    per-feature test. If a new screen needs a new sanity test, the existing
    ones were written wrong.
  - One real app boot for the whole session (`tests/sanity/conftest.py`'s
    `booted_app`), not one per test.
  - `diagnostic_guard` (autouse) fails on any Qt message, Python log record
    at WARNING+, or `warnings.warn(...)` during boot/construct/shutdown —
    silence is the assertion, not just a green exit code. `quick_widget.
    errors() == []` is retired: zero QML since `EPIC-006`.
  - The only permitted substitution is the network boundary, drawn at
    configuration, never at a code path: point the real client at a local
    fake server (`tests/sanity/binance_fake_server.py`), never hand-write a
    substitute for a port like `IExchangeClient` — that shape produced
    `BUG-026`/`BUG-027`.
  - No assertion may name a business fact (a strategy, a screen's content) —
    that belongs to Integration.
  - The OUT-of-process layer (`--self-check`,
    `tests/sanity/test_self_check_process.py`) launches the real entry point
    as a real subprocess — the only tier that proves the process actually
    exits, not just that `teardown()` returned inside pytest's own process.
- **Integration:** Put deterministic user/application journeys in
  `tests/integration/`: drive named QML/Qt input, wait on terminal
  signal/state, assert the observable result using local seeded/fake
  boundaries. Never depend on a public exchange or live account.
- **Desktop E2E:** A reported GUI/runtime defect or native rendering change
  requires a retained opt-in Windows desktop E2E harness: start the actual app,
  seed deterministic local data, use real `QTest`/`qtbot` input, wait for the
  visible terminal state, capture clean Qt messages/stderr. Local/nightly when
  necessary, but not optional evidence for native interaction work.
- **External service smoke:** An explicitly requested, credential-free smoke
  check is operational evidence, not a fifth test level and never a normal CI
  gate or replacement for deterministic coverage.
- **`tests/testnet/` (`EPIC-021J`) is operational evidence, not a fifth test level.** It touches
  the real Futures Testnet with real credentials, and its whole value is proving the app can
  **actually** place and cancel an order on Binance's own infrastructure — something none of the
  four levels above proves, since Sanity and Integration both talk to `binance_fake_server.py`,
  never the exchange. That is also exactly why it can replace none of them: testnet price drift,
  network latency and rate limits make it inherently non-deterministic, the opposite of what the
  four levels exist to guarantee. Rules:
  - **Opt-in twice, not once.** `ci-rule.md` §3a: `-Full` excludes it via `--ignore` regardless of
    any environment variable, and the tier gates itself again on `SEW_TESTNET_TESTS=1` **and**
    real credentials.
  - **Assert invariants, never figures.** Testnet prices and balances move in real time — assert
    `FILLED`, or a position closing back to zero; never a specific number.
  - **Clean up in `finally`, always.** An order or position left behind corrupts the next run;
    there is no "re-run and tidy by hand".
  - **Wait on a named condition** (order/position state read back from the exchange), never a
    fixed `sleep` — the same rule as §2 below, and it applies to this real-network tier too.

---

## 2. Writing tests correctly

- **Deterministic Async & UI Testing:** Never use timing sleeps to synchronize a test. Wait for a named completion signal, FSM state, terminal event, or bounded `qtbot.waitUntil(...)` condition. Give every QML control that is a critical user action a stable `objectName` so integration/E2E tests can target it.
- **Financial & Backtest Invariants:** Add deterministic property/invariant tests for financial code: reject `NaN`/infinite values, keep fees non-negative, keep equity/trade/metrics internally consistent, and require identical outputs for identical input data/configuration. Every new execution mode, fee model or simulation pass must extend these invariants.
- **Domain Logic Edge Cases — Boundary Value Analysis, not exhaustive enumeration:** "Test every edge case" is an unbounded, unverifiable target — pick cases using Equivalence Partitioning (one representative input per class the logic is meant to treat identically) plus Boundary Value Analysis (the values right at and around a class boundary, where real bugs concentrate), not a manual grab-bag. For any consequential domain calculation or decision, mutation-verify it: deliberately break the logic under test (flip a comparison operator, shift a boundary by one, invert a sign) and confirm the existing test actually fails — a test that still passes against broken logic proves nothing about correctness, no matter how many lines it executes (`BOT-106A`: a mathematically-constant return sequence still made `statistics.stdev()` compute ~1e-16 instead of exactly `0.0`, silently passing a test that assumed float equality). Do not add exception-handling tests for a domain state an existing invariant — FSM transition matrix, frozen dataclass, DI-enforced construction — already makes unreachable; that is padding coverage, not proving correctness.
- **Business Acceptance for Trading Features:** A backtest UI test MUST assert the business composition of the result, not merely that a run completed. For example, a long-only result may contain long entries and long exits but MUST contain no short trade; a future short-enabled strategy must prove a downtrend produces an actual SHORT fill, its SHORT table filter shows it, its PnL moves correctly as price falls, and its chart marker represents the fill rather than merely the strategy signal.
- **Use repo's QML test helpers:** Use `qml_item` / `find_qml_item` fixtures from `tests/conftest.py`, `qtbot.waitUntil(...)`, and `item.mapToItem(root, 0, 0)`.
- **Do not move click handling off the Button itself** when tests emit `.clicked`.
- **Fixing a bug:** follow `.agents/rules/bug-fix-rule.md` in full — root
  cause first, regression test before the fix (confirmed failing for the
  right reason, at the correct test tier), kept permanently after.
