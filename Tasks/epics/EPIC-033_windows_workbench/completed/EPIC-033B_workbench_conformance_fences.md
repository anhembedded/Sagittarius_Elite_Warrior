# EPIC-033B — A booted-app conformance suite and static bans hold the contract, shrink-only until each mode migrates

**Status:** ✅ Done (2026-10-06)
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟡 — a shared surface changes shape
**Complexity:** M — a runtime suite over every mode plus AST guards
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033A, EPIC-033O

---

## 1. Context and problem
HLD §11.5 lists five rules as "enforced"; only the `.qml` ban has a test (UX review, guard survey). The screenshot review measured the violations by hand: 0 menu-bar actions, 1 of 8 modes with docks, up to 90 styled widgets and 20 controls over 32 px per screen, scroll areas nested two deep. A measurement nobody repeats drifts back.

## 2. Acceptance criteria
- [x] `tests/integration/presentation/ui/test_workbench_conformance.py` boots the real app (`main_window` fixture), visits every mode at 1024×700 and 1920×1080 and fails, per mode, on: no `File`/`Edit`/`View`/`Window`/`Help` menu; a `QDockWidget` whose `toggleViewAction()` is not in `View`; a visible widget with a non-empty `styleSheet()`; a visible button, line edit, combo or spin box taller than its own `sizeHint()`; a `QScrollArea` inside a `QScrollArea`; a toolbar holding a widget that is not the widget for one of its actions; a mode that is not a workbench host; a perspective that does not survive save, restart and restore; a visible item view whose selection behaviour, edit triggers, sorting, header policy or column alignment differs from what its column spec declares. — built at 1366×768 first; 033C added 1024×700 and 1920×1080 (2026-10-05), with a per-mode `fits_the_window` check and `mode@WxH` baseline keys. The restart half is `test_every_modes_rearranged_layout_survives_a_restart` in `test_main_window_state.py` (2026-10-06): it needs a second window over the same state store, which the suite's shared `main_window` fixture cannot give, so it runs the suite's `rearrange`/`restart_problems` check there, with the probe `test_a_host_that_does_not_restore_after_a_restart_is_seen` here. Per-column alignment moved to [`EPIC-033N`](../completed/EPIC-033N_uniform_display_widgets.md), which owns the column specs it compares against; this box no longer claims it.
- [x] Each failing mode is listed in `baseline_workbench_conformance.json` (mode → failed checks) and the suite fails both on a new failure and on a listed one that now passes; the list only shrinks and is empty when 033M closes.
- [x] Static bans in `tests/unit/architecture/test_stock_controls_only.py`: `setStyleSheet`, `apply_role`, `StyledButton`, `setFixedSize/Height/Width`, `setMinimumHeight/Width` on a control, an item view or header configured outside `configure_item_view()` (`setSelectionBehavior`, `setEditTriggers`, `setSortingEnabled`, `setSectionResizeMode`, `setAlternatingRowColors`), a number or time formatted for display outside the value formatter, `QFont(` with a family literal, a widget `move()` over a canvas; per-file counts shrink-only (`baseline_stock_controls.json`), ban at zero. — built (six rules: `style_sheet`, `fixed_size`, `item_view_config`, `font_family`, `color_literal`, `checkable_button`) without the value-formatter and `move()` bans. The formatter ban moved to [`EPIC-033N`](../completed/EPIC-033N_uniform_display_widgets.md)'s formatter criterion (2026-10-06): the formatter exists now, but the per-screen helpers it would ban are that task's to delete. `move()` has legitimate non-overlay uses that an AST scan cannot tell apart, so the rule's §3 keeps it as review row H4.
- [x] `test_labels_escape_mnemonics.py` fails on a user-visible string literal passed as a button, dock, tab or action text that contains a single `&` before a space (UX-09: "Data & stream", "Shards & Timeframes"). — built as the runtime check `mnemonics_escaped` in the conformance suite instead, over the visible buttons, group boxes, dock titles, actions and tab texts of every mode: a static scan of string literals flagged docstrings and labels that are never mnemonics. The one label it still finds, the Dev Board's "Data & stream" dock, is the `dashboard` baseline line, which leaves with the Dev Board (`EPIC-033P`).
- [x] The three guards that favour the `kit` look are superseded, not loosened: their file docstrings name the 033B check that forbids strictly more, and they are deleted in the commit that adds it (P8).
- [x] Each new check is mutation-verified: break one mode on purpose, see the suite name it.

## 3. Design
One runtime suite, because the defects are properties of the composed window (a dock missing from View, a nested scroll) that no file-level scan sees (CS-002: a test constructs its subject). Static bans catch the cause at the line that writes it. Both are ratchets keyed per mode and per file, the repository's allowlist pattern.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/integration/presentation/ui/test_workbench_conformance.py` | New suite |
| `tests/integration/presentation/ui/baseline_workbench_conformance.json` | Measured as found |
| `tests/unit/architecture/test_stock_controls_only.py`, `baseline_stock_controls.json` | Static bans |
| `tests/unit/architecture/test_labels_escape_mnemonics.py` | Mnemonic guard; fixes the two labels it finds |
| `tests/unit/presentation/ui/test_widget_guards_hold.py`, `test_app_owns_its_size_tokens.py`, `test_palette_is_the_only_color_source.py` | Deleted, superseded |
| `tests/unit/architecture/scanned_roots_registry.py` | Rows for the new guards |

## 5. Testing
Integration and unit tiers. Mutation: add `setStyleSheet` to one desk widget, nest a scroll area, add a dock not in View; each must fail naming the mode.

## Implementation notes (written when done)
- Commit 4292f0b: `test_stock_controls_only.py` (six rules, per-file shrink-only baseline) and `test_workbench_conformance.py` (two shell checks, nine per-mode checks, baseline per mode).
- Superseded and deleted in the same commit: `test_widget_guards_hold.py`, `test_app_owns_its_size_tokens.py`, `test_palette_is_the_only_color_source.py`; their registry rows went with them.
- **2026-10-06, closing.** Three more checks, each with a probe that plants the defect: `restart_problems` (a second window that restores nothing is named bar by bar; on the real app, a perspective store that restores nothing names every mode, and registering only the mode host names every surface panel), `access_keys_unique` (two Market commands edited at run time to share `l` and lose `c` were named) and `toolbar_actions_in_a_menu` (with the check disabled, its probe and its three baseline lines went red). The new baseline lines, as found: `market`, `dashboard` and `backtest` → `toolbar_actions_in_a_menu` (the shared chart toolbar's timeframes, zoom and Go live, and the Dev Board's Cancel order).
- Mutation evidence: each suite's probe tests plant the defect (a styled, oversized button widget in a toolbar; a lone `&`; a new styled file) and see it named. On the real app, a `setFixedHeight(80)` and a style sheet added to Welcome's Start button made the suite fail with `welcome/control_height: QPushButton 'btnStart' is 80px, its size hint 22px` and `welcome/no_style_sheet`; reverted.
