# SDD — Software Design Description for `EPIC-025`

- **Status:** 🔵 Draft 2026-09-13 — **round 3**, revised after the independent design review
  ([`Tasks/reports/EPIC-025_design_review.md`](../../Tasks/reports/EPIC-025_design_review.md)); the
  disposition of every finding is in the ADR §7. The HLD says *what* and *why*; this document says
  *how*, at the level of classes, sequences and states, for the code Phase 0 (`EPIC-025A`) writes.
  It answers open question O1 (contribution-point schema) concretely.
- **Reading order:** HLD §3 and §4.6 first; then the diagrams below in number order.
- **Toolkit (ADR D20–D22, HLD §11):** QtWidgets only, OS theme; a factory returns a `QWidget` that a
  surface host (`QMainWindow`) places as a dock panel, toolbar, status-bar tile, central widget or
  dialog. `PageShell` and `QuickSurface` are retired; wherever this document says *panel*, read *panel*.
- **Rendering:** any PlantUML renderer; the sources were syntax-checked with PlantUML 1.2026.8.
- **The behaviour these contracts serve** is specified in [`Docs/SPEC/`](../SPEC/README.md), one use
  case per file. A contract that ships differently from this document is recorded in
  [`05_module_contracts.md`](05_module_contracts.md); a *flow* that changes is recorded in its `SPEC`.


## This document is a directory, and why

It was one 288-line `README.md`. The HLD next door has been twelve numbered
files since it was written, and the difference showed: every pull request of
`EPIC-025` Phase 1 edited the single SDD file, so its history is one stream of
diffs in which "the threading contract changed" and "market_data's ports
shipped differently" are indistinguishable. Split on the user's decision of
2026-09-15, so a change can be traced to the concern it belongs to.

Every `###` heading kept its exact wording, so the references already written
elsewhere — *"SDD, 'Threading contract'"*, *"SDD 'Ownership'"*,
*"the SDD's `register()` versus `boot()`"* — still resolve.

| § | File | What it is the authority on |
| :-: | :--- | :--- |
| 1 | [`01_diagrams.md`](01_diagrams.md) | the diagram index: which `.puml` answers which question |
| 2 | [`02_contribution_mechanism.md`](02_contribution_mechanism.md) | the descriptor's shape, registry validation at `contribute()` time, and what each surface accepts |
| 3 | [`03_ownership_lifetime_threading.md`](03_ownership_lifetime_threading.md) | who owns a contributed panel, how long it lives, which thread may call a port |
| 4 | [`04_boot_and_configuration.md`](04_boot_and_configuration.md) | `register()` versus `boot()`, the shell's boot order, `IConfigWriter`, and `dev.mode` with its restart |
| 5 | [`05_module_contracts.md`](05_module_contracts.md) | **each module's published surface: specified, then corrected against what shipped.** The symbol lease and `contracts/errors/` live here too |
| 6 | [`06_measured_baselines.md`](06_measured_baselines.md) | the numbers Phase 0 committed, so a later phase can be compared against them |

Diagrams are in [`diagrams/`](diagrams/); the north star is
[`Docs/HLD/README.md`](../HLD/README.md).
