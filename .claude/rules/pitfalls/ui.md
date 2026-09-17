---
description: Traps that produced broken UI code here — one line each, with the bug id. Loads with every presentation, module UI, ui_kit and charting file.
paths:
  - "src/presentation/**/*.py"
  - "src/modules/*/ui/**/*.py"
  - "src/support/ui_kit/**/*.py"
  - "src/support/charting/**/*.py"
---

# Pitfalls — UI
1. `fsm.transition_to(X)` while in `X` raises, `@safe_ui_action` swallows it, the slot dies mid-way (`BUG-018`).
2. Important work after a call that can throw inside a `@safe_ui_action` slot.
3. `logger.info()` in a hot loop freezes the UI (`BUG-042`, 5 028 lines in 2 s) — `debug()`, or batch.
4. Putting logic in the view layer — state machines, validation and computation belong to the Presenter/ViewModel.

A new trap is one line here with its id; the long form is a case study (`Docs/CASE_STUDIES/README.md`).
