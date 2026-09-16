---
paths:
  - "src/**/*presenter*.py"
  - "src/**/*coordinator*.py"
---

**Open [`.agents/rules/async-ui-action-rule.md`](../../.agents/rules/async-ui-action-rule.md) now,
all of it** — it is short, and it is the rule behind more real bugs than any other in this
repository. A presenter or a coordinator that starts background work, receives a worker's result,
or cancels anything is what it governs. This pointer copies no rule text.
