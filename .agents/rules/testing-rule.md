---
name: Testing Rule
description: How to WRITE tests properly — what each level proves, async without sleeps, invariants, boundary value analysis plus mutation-verification, business acceptance.
trigger: on_demand
---

# TESTING RULES — how to WRITE a test

**Division of labour with [`ci-rule.md`](ci-rule.md):** that file holds the
*commands*, the four-level test contract, and how to handle a red gate. This
file holds how to *write* a test properly. Need to know what to run →
`ci-rule.md`; need to know what to write → this file.

For bug fixes, [`bug-fix-rule.md`](bug-fix-rule.md) is the source of truth — it
requires the regression test to be written **before** the fix and confirmed to
fail for the right reason.

---

## 1. Every feature declares evidence at all four levels

The four levels are defined in [`ci-rule.md`](ci-rule.md) §4. A change may add
**no** new test only when an existing test at the relevant level **already**
proves the exact new behaviour — and it must **name that evidence** in the task
or report.

---

## 2. Async & UI: never synchronise with a sleep

**Never use a sleep to synchronise a test.** Wait on a named completion signal,
an FSM state, a terminal event, or a condition with a **bounded timeout**.

Every UI element that is a critical user action needs a **stable identifier**
for integration/E2E tests to target ([`ui-rule.md`](ui-rule.md) §4).

---

## 3. Invariants for computational code

Add **deterministic** property/invariant tests for every consequential
computation:

- reject `NaN`/infinite values;
- keep quantities non-negative where they must be;
- keep derived numbers **mutually consistent**;
- **identical input + identical configuration → identical output, exactly.**

Every new execution mode, cost model or simulation pass **must extend these
invariants**, never route around them.

---

## 4. Edge cases: boundary value analysis, not endless enumeration

"Test every edge case" is an unbounded, unverifiable target. Choose cases with:

- **equivalence partitioning** — one representative input per class the logic is
  meant to treat identically;
- **boundary value analysis** — the values **at and around** a class boundary,
  where real bugs concentrate.

### Mutation-verify: mandatory for every consequential calculation or decision

**Deliberately break the logic under test** (flip a comparison, shift a
boundary by one, invert a sign) and **confirm the existing test actually goes
red**. A test that stays green against broken logic **proves nothing** about
correctness, no matter how many lines it executes.

> **Real evidence:** a **mathematically constant** sequence still made a
> standard-deviation function return ~1e-16 instead of exactly `0.0`, silently
> passing a test that assumed float equality with `==`.

**Don't write a test for a state an existing invariant already makes
unreachable** (an FSM transition matrix, an immutable type, a DI-enforced
constraint) — that is padding coverage, not proving correctness.

---

## 5. Business acceptance — assert the **composition** of the result

A test for user-facing behaviour MUST assert the **business composition** of
the result, not merely that a run completed.

Example (adapt to your domain): in a system that supports only one direction, a
result may contain entries and exits but **must not** contain the opposite
direction; when the opposite direction becomes supported, the test must prove it
**actually happened**, appears in its own filter, moves the derived figures in
the right direction, and that **what is displayed** represents the real outcome
rather than merely the input signal.

---

## 6. Four traps that break tests unfairly, or pass them unfairly

1. **Computing the expected value in your head** instead of running the real
   code (see §4).
2. **Comparing floats with `==`.** Use a tolerance-based comparison.
3. **Asserting counts against a hard-coded constant** (`len(x) == 9`). Assert
   what is *meaningful*: presence/absence, relative order.
4. **Asserting full-object equality** on serialised output. Assert exactly the
   subset the test actually cares about — otherwise a valid new field breaks it.

---

## 7. Fixing a bug

Follow [`bug-fix-rule.md`](bug-fix-rule.md) **in full**: root cause first, the
regression test **before** the fix (confirmed failing **for the right reason**,
at the **correct test level**), kept permanently afterwards.
