---
name: UI Presentation Layer Rule
description: QtWidgets only, the OS theme, the seven desktop UX principles, MVP layout, preview.py, sizing, tables, icons, terminology.
trigger: on_file_change
patterns:
  - src/presentation/**/*.py
  - src/modules/*/ui/**/*.py
  - src/support/ui_kit/**/*.py
  - src/support/charting/**/*.py
---

# UI and presentation

This layer is excluded from the `mypy` gate, so `architecture-rule.md` §2.1 (explicit Presenter ↔ View contract, with a contract test) and `async-ui-action-rule.md` decide more here than tooling. Design: `Docs/HLD/11_desktop_workbench.md`.

## 1. QtWidgets only, OS theme (ADR D20–D22, 2026-09-13)
- No QML: `src/` holds zero `.qml`, and a new one fails the gate. No stylesheet, palette library, theme tokens or theme distribution; colour only where it carries meaning, through `QPalette` roles or a per-widget property. Per-widget styling in not-yet-rebuilt screens is a shrink-only ratchet. `[guard: test_no_new_qml.py, test_no_global_stylesheet.py, test_app_styling_only_shrinks.py]`
- Every user-facing surface is a standard `QMainWindow` part — `QMenuBar`, `QToolBar`, `QStatusBar`, `QDockWidget`, `QDialog` — never a hand-drawn substitute; a module contributes panels and dialogs through the registry (`Docs/HLD/04_surfaces_and_contribution_points.md`). `[review: H3]`

## 2. The seven desktop UX principles (user decision 2026-09-13; full text in HLD §11)
| Principle | In Qt |
| :--- | :--- |
| Familiarity | standard parts, no reinvented chrome |
| Consistency | one `QAction` per user action carries shortcut, menu entry and toolbar button; standard shortcuts never rebound |
| Efficiency | every action reachable by keyboard; nothing more than two clicks from its mode; layouts remembered |
| Clarity | no animation for its own sake; a dialog names the action and its consequence; progress for anything longer than a heartbeat |
| User control | every dialog has Cancel; long operations cancellable; reversible edits via `QUndoStack`; one Settings dialog with Apply/Cancel |
| Robustness | the UI thread never blocks; an error names what failed and what to do; saved layouts keyed by version, migrate or reset |
| Scalability | adding a panel never changes another panel or the shell |
`[review: H7]`

## 3. Layout and sizing
- MVP trio per screen under its package: `<name>_presenter.py`, `<name>_view.py`, `<name>_view_model.py` flat; helpers in `logic/` or `helpers/` only when size warrants; Coordinators per `async-ui-action-rule.md` §2.
- Never a fixed pixel size on a container holding text or widgets (a leaf glyph may). Content that can outgrow its viewport goes through `PageShell.set_workspace()`, which scroll-wraps it. `[review: H4]`
- Table column widths declared once and bound to header and rows; a table narrower than its columns scrolls horizontally, never drops them (`BOT-128`). `[review: H6]`
- Two independent positioning systems (a `move()`-placed overlay and a library's own layout) never share a region; anchor to measured free space (`chart_card/zoom_controls.py`).

## 4. Icons and terminology
SVG only (Lucide/Feather) in `src/support/ui_kit/assets/icons/`, rendered via `image://icons/<name>/<token>`; never emoji. Strategy parameters are labelled "Strategy Parameters", distinct from Bot Settings; user-visible strings are English.

## 5. Preview
Every UI package keeps a `preview.py` with `build_preview() -> QWidget` (`.\scripts\preview-qml.ps1 <screen>` / `--list`). `[guard: tests/unit/presentation/ui/test_preview_fixtures_exist.py]`
