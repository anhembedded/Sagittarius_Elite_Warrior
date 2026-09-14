---
paths:
  - "**/*.qml"
  - "src/presentation/**/*.py"
---

**Open [`.agents/rules/ui-presentation-rule.md`](../../.agents/rules/ui-presentation-rule.md) now**,
including its "Desktop UX principles".

This layer is excluded from the `mypy` gate, so two neighbours decide more here than tooling does:
[`async-ui-action-rule.md`](../../.agents/rules/async-ui-action-rule.md) for anything starting
background work, and [`architecture-rule.md`](../../.agents/rules/architecture-rule.md) §2.1 for the
Presenter ↔ View contract. This pointer copies no rule text.
