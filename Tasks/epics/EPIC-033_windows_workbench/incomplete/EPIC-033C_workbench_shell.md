# EPIC-033C — One top-level workbench window: menu bar, mode bar, View menu, Reset layout, status bar

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🔴 — touches order placement
**Complexity:** L — replaces the shell every mode lives in
**Epic:** [EPIC-033](../README.md)
**Depends on:** Engine W1, EPIC-W3; 033B

---

## 1. Context and problem
`MainWindow` (`src/presentation/ui/main_window.py:72`) is a `QMainWindow` whose central widget is a custom `Sidebar` beside a styled `QStackedWidget` (`:134-151`, `_CONTENT_BG_STYLE`). It has no menu bar. The sidebar is 202 px wide with `setFixedHeight(40)` buttons (`sidebar.py:326,331`) and breaks below 1100 px. `app_bootstrapper._apply_font` (`:530-539`) forces Consolas 10 pt on the whole application.

## 2. Acceptance criteria
- [ ] The app's top window is the Engine's `WorkbenchShell`; every mode is a nested workbench host it switches between.
- [ ] The menu bar holds File, Edit, View, the modules' menus (Trade, Data, …), Tools, Window, Help in that order, every item with a unique access key; View lists the modes (Ctrl+1…), every dock of the current mode, Toolbars and Status Bar; Window → Reset Layout restores the mode's default perspective; Help → About shows name, version and venue.
- [ ] Welcome is deleted: the app opens on the last used mode, as Windows applications do; developer mode moves to Tools → Options.
- [ ] The window title and the status bar name the venue (Testnet or Mainnet) in text, never by colour alone.
- [ ] Modes are a vertical mode bar of checkable actions with icons and tooltips (Ctrl+1…Ctrl+8), as in Qt Creator; `Sidebar`, its 10 style sheets and its fixed heights are deleted.
- [ ] The application font is the platform's (`_apply_font` deleted); tabular numbers use `QFontDatabase.systemFont(FixedFont)` only where digits align.
- [ ] Each mode's perspective is saved on exit and restored on start, keyed by mode and app version; a mismatched version resets, never crashes.
- [ ] The environment banner stays a non-movable toolbar row above every mode (`test_environment_banner_all_screens.py` stays green).
- [ ] 033B's conformance rows for the shell checks are removed from the baseline.

## 3. Design
Qt Creator's shape (P5): mode selector, a `QMainWindow` per mode, perspectives through `saveState`. The shell is Engine mechanism (D3); the app supplies policy: which modes, their order, icons and default perspectives.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/presentation/ui/main_window.py`, `app_bootstrapper.py` | Build the Engine shell; delete the sidebar wiring and the font override |
| `src/support/ui_kit/sidebar/` | Deleted |
| `src/shell/screen_wiring.py`, `src/support/ui_kit/registry/screen_registry.py` | Modes registered with the shell instead of the sidebar |
| `src/shell/welcome/` | Welcome becomes a mode with a central widget only |

## 5. Testing
Unit: shell wiring. Integration: conformance suite (menus, View, perspectives round-trip). Desktop E2E: open, rearrange, restart, see the layout back.

## Implementation notes (written when done)
Not started.
