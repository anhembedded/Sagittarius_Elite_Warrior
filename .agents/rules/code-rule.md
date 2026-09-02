---
name: Python Code Rules (navigation stub)
description: Historical entry point — the real content has been split into 6 dedicated rule files. This file is navigation only.
trigger: always_on
---

# PYTHON CODING STANDARDS — this file is now NAVIGATION ONLY

The content has been split by abstraction level. The stub is kept because
`.agents/Skills/` still points here.

| Former content | Read in |
| :--- | :--- |
| SOLID; Full Abstraction & ABC completeness; Clean Architecture Layers; Use Case/CQRS; Abstraction-Level Separation | [`architecture-rule.md`](architecture-rule.md) |
| Typing; Readability; Immutability; No Magic Numbers / Nested Loops / God Objects / Lazy Imports; Single-Scope Cohesion | [`code-quality-rule.md`](code-quality-rule.md) |
| Async UI Action Ownership & Cancellation; Coordinator Pattern | [`async-ui-action-rule.md`](async-ui-action-rule.md) |
| Truthful Data, Trading Semantics, Renderer benchmark, Chart host boundary, Counterintuitive Story Check | [`domain-truth-rule.md`](domain-truth-rule.md) |
| UI & Presentation — MVP trio, responsive sizing, icons, `preview.py` | [`ui-presentation-rule.md`](ui-presentation-rule.md) |
| Testing — invariants, Boundary Value Analysis, business acceptance | [`testing-rule.md`](testing-rule.md) |
| CI — static quality, read-only gate, mandatory log scan | [`ci-rule.md`](ci-rule.md) §8 |
| Proactive Pushback | [`../ONBOARDING.md`](../ONBOARDING.md) §7 |
| Git Commits | [`commit-rule.md`](commit-rule.md) |

**Told to "read code-rule.md before doing anything":** read
[`../ONBOARDING.md`](../ONBOARDING.md) first, then open just the 1-2 files above
that match the work at hand. There is no need to load all 6.
