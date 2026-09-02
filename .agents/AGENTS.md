---
name: Agents Navigation
description: Navigation stub — which rule file covers which topic. Deliberately holds no rules of its own.
trigger: always_on
---

# Development Guidelines — this file only NAVIGATES

> **New agent starts here:** read [`ONBOARDING.md`](ONBOARDING.md) before this
> file. That one is the process map; this one is just an index by topic.

**Do not copy rules into this file.** This is where drifted copies are born:
an agent finds it convenient, copies a few sections "for readability", and
weeks later the copy and the original contradict each other with nobody
knowing which one is being read. Need a new rule → edit the rule file it
belongs to; here you add one line pointing at it.

## Topic → file

| Topic | Read |
| :--- | :--- |
| SOLID, layer boundaries, ports/interfaces, explicit contracts, use cases, splitting by abstraction level | [`rules/architecture-rule.md`](rules/architecture-rule.md) |
| Internal signal or event bus — who owns this truth | [`rules/event-rule.md`](rules/event-rule.md) |
| Deferring work / accepting a trade-off → needs a type or a test standing for it | [`rules/design-intent-rule.md`](rules/design-intent-rule.md) |
| Typing, readability, immutability, magic numbers, God objects, lazy imports, cohesion | [`rules/code-quality-rule.md`](rules/code-quality-rule.md) |
| Background-action ownership, stale callbacks, cancellation, Coordinators | [`rules/async-action-rule.md`](rules/async-action-rule.md) |
| Truthful data, business semantics, snapshots, benchmarks | [`rules/domain-truth-rule.md`](rules/domain-truth-rule.md) |
| Presentation layer: declarative views, responsive sizing, icons, injection defense, previews | [`rules/ui-rule.md`](rules/ui-rule.md) |
| How to **write** a test | [`rules/testing-rule.md`](rules/testing-rule.md) |
| How to **run** the CI gate, the four test levels, handling red | [`rules/ci-rule.md`](rules/ci-rule.md) |
| Before every commit | [`rules/commit-rule.md`](rules/commit-rule.md) |
| A bug was reported (**mandatory**) | [`rules/bug-fix-rule.md`](rules/bug-fix-rule.md) |
| Adding or changing logs | [`rules/logging-rule.md`](rules/logging-rule.md) |
| Missing tooling or a library needed to verify | [`rules/environment-rule.md`](rules/environment-rule.md) |
| Process, permissions, bookkeeping, the traps that produced real defects | [`ONBOARDING.md`](ONBOARDING.md) |
| Where the last session stopped | [`Handover.md`](Handover.md) |
