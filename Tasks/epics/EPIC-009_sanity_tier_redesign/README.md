# EPIC-009 — Sanity Tier Redesign

**Status:** 🔵 **In discussion — no scope agreed, no task files, no code.**
**Type:** Testing architecture / quality gates
**Priority:** to be decided once [the ADR](DECISION_2026-08-25_sanity_model_and_execution.md) is ratified
**Branch:** none yet

> Deliberately **not** registered in [`Tasks/ROADMAP.md`](../../ROADMAP.md).
> A ROADMAP line says work has started; this epic exists so the decision can be
> argued before anyone writes code. Add the line when the ADR reaches *Approved*.

---

## 1. Why this epic exists

The Sanity tier reports green while proving substantially less than it claims:

- Its mandatory contract clause (`quick_widget.errors() == []`, `code-rule.md`
  §4) is enforced by **0 of 38** cases and is now unenforceable — EPIC-006
  removed QML from the app.
- It constructs **2 of 4** screens; two screens have never been built by any
  sanity test.
- It observes **1 of 5** diagnostic channels the real app writes to during boot.
- It never proves shutdown, despite three filed shutdown bugs (two P1).
- It boots the real application ~24 times to produce 38 assertions.

Evidence: [`sanity_tier_audit_and_remediation.md`](../../reports/sanity_tier_audit_and_remediation.md).

## 2. What is decided so far

**Nothing.** The ADR is at *Proposed*. It records five proposed decisions
(D1–D5), four implementation constraints (C1–C4), a draft 12-entry failure-mode
catalogue, and eight blocking open questions.

## 3. Next step

Close the open questions in the ADR §7, in order. Q1 (ratify the failure-mode
catalogue) gates everything else; Q2/Q3/Q4/Q6 need one session on a machine
that can actually run the app.

## 4. Sub-tasks

None. Sub-task files are created after the ADR is approved, per
[`Tasks/epics/README.md`](../README.md).
