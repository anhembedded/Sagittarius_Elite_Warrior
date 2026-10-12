---
description: The shared mechanisms this application already has (need, symbol, where, one current user), delivered when UI or application code is opened so a change reuses one instead of building a second. The table is generated from `Capability:` docstring blocks.
paths:
  - "src/modules/**/ui/**"
  - "src/modules/**/application/**"
  - "src/shell/**/*.py"
  - "src/presentation/ui/**/*.py"
---

# CAPABILITY CATALOG — find what exists before you write

*Capability* here means a shared mechanism a developer reuses (`Docs/VOCABULARY/README.md`); it is not the Engine-API sense in `engine_capabilities.py`. Class A of the bug reports ("did not reuse") is what this table answers: `BUG-155` (a free-text symbol field beside `SymbolPickerOverlay`), `BUG-165` (hand-built empty labels beside `empty_page`). `[eye]`

1. Before building a widget, a helper or a flow, find your need below by its words and its synonyms. A row fits: use its symbol. No row fits: search `src/support/` once more, then build. `[review: A7]`
2. Name what you checked in the task's **Reuse** section (`.claude/templates/task.md` §3a); a pull request without it fails review check A7. `[review: A7]`
3. Add a mechanism others will reuse by writing a `Capability:` block in its module docstring (shape: `scripts/render_capability_index.py`), then `python3 scripts/render_capability_index.py --write`. Never edit the table by hand: the guard compares it with the generator. `[guard: test_every_support_package_is_in_the_catalog.py]`

## Declared in code (generated)

<!-- capabilities:begin -->
| Need | Use | Where | Used by |
| :--- | :--- | :--- | :--- |
| Name a widget or factory by import path so boot imports no widget module (also: lazy import, deferred import, late import, contribution factory, PLC0415) | `Deferred` | `src/core/contracts/deferred.py` | `src/modules/trading/module.py` |
| A panel's page while it has nothing to show, framed like a filled view (also: empty state, EmptyStateStack, no data label, placeholder, instruction text) | `empty_page`, `frame_instruction_page` | `src/support/ui_kit/empty_page.py` | `src/modules/bots/ui/bots_screen/bot_plan_panel.py` |
| Choose a trading pair, with favourites and recents (also: symbol picker, pair chooser, ticker selector, market combo, symbol field) | `SymbolPickerOverlay`, `ISymbolPickerSource` | `src/support/ui_kit/symbol_picker/` | `src/modules/bots/ui/bots_screen/new_bot_dialog.py` |
<!-- capabilities:end -->

## Not declared in code (hand-written)

| Need | Use | Where |
| :--- | :--- | :--- |
| A widget family the app wraps from the Engine (`EmptyStateStack`, `Selection`, `IValueFormatter`) | `sagittarius_engine.extensions.pyside_mvc.workbench` | the Engine repository, not this checkout |
