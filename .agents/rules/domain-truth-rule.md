---
name: Domain Truthfulness Rule
description: The system may not lie about what it actually did — real validation, immutable snapshots, no collapsed business semantics, no UI promising what the backend can't do, benchmarks with a method.
trigger: on_file_change
patterns:
  - <SRC_DIR>/domain/**
  - <SRC_DIR>/application/**
---

# TRUTHFUL DATA, VALIDATION & SNAPSHOT SEMANTICS

The principle running through all of this: **the system may not lie about what
it actually did.** A number that is valid as a data type can still be a lie
about the business — and depending on the domain that may be real money, a real
medical record, or a real decision a user made.

---

## 1. Validation must prove what it claims

- A check of the form "we have enough data across range X" MUST verify
  **internal gaps**, using the data's own cadence and normalised boundaries.
  Min/max values or a total row count **do not** prove coverage.
- Constraints imposed by an external system (limits, minimum sizes, step sizes,
  quotas) MUST come from that entity's own cached metadata. **Never hard-code a
  "universal" constraint**, and never substitute one quantity for another just
  because they share a unit.

## 2. Snapshots must be immutable and self-describing

A historical/cached snapshot shown to a user MUST be:

- **immutable** — holding no reference to a still-mutable model;
- **memory-bounded**;
- **carrying enough provenance to describe the result honestly**: the
  configuration used, the data window / watermark, the algorithm's version and
  parameters, the cost model, the execution mode.

Without provenance, two results that look identical can come from two different
configurations, and nobody can tell.

## 3. Don't collapse business semantics

**Distinct** domain facts must be modelled and tested **separately**. Never let
one ambiguous label silently stand for more than one truth.

Example (adapt to your domain): an algorithm's signal, an intended operation, an
execution result, opening a position and closing one are **five** different
facts. In a system that supports only one direction, the "out" operation is a
**close** of what exists — **not** an opening in the opposite direction.

## 4. Business contract before implementation contract

Tests must **first** express the observable business promise, then verify the
implementation. A green suite that only proves private calls, existing data
structures, or an **intentionally limited** engine contract is **not** evidence
that the user-facing behaviour is correct.

For every critical journey, write deterministic acceptance coverage for: the
expected inputs, the state transitions, the outcome, and **what is displayed**
(table, chart, message).

## 5. The UI must be truthful

Every label, icon, marker, filter, metric and empty state MUST describe **what
actually happened** and **what the system supports right now**.

- Two different truths must have different representations (§3).
- **Do not** present a planned or unsupported capability as available: hide it,
  disable it, or explicitly label it unavailable.
- Test the **displayed semantics**, not only the underlying payload.

## 6. Don't promise performance you haven't measured

- Never claim instantaneous or fixed latency without a reproducible benchmark
  fixture. State the workload, the cache condition, the measurement method. A
  displayed ETA must be labelled an **estimate**.
- **Benchmark methodology when comparing two implementations:** the same
  immutable source payload, the same interaction/viewport sequence, the same way
  of waiting for completion, and the same way of capturing the final result.
  Record median/p95, the environment, the real backend, the display semantics,
  and captured warnings.
- **Performance and correctness are separate proofs.** Never improve a benchmark
  number by dropping data, labels, or the final correctness check.

## 7. Counterintuitive story check

When a user story, label, default, or acceptance criterion can **reasonably
conflict** with a user's mental model, **stop and report** the observable
behaviour, the evidence, and the trade-off — before finalising the design.
Don't invent a hidden user intent; encode the chosen semantics truthfully in the
UI copy and in acceptance tests.
