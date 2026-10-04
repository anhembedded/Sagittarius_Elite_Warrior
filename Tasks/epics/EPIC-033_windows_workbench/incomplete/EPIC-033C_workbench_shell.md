# EPIC-033C — One top-level workbench window: menu bar, mode bar, View menu, Reset layout, status bar

**Status:** 🟡 In review (pull request open; open criteria listed below)
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🔴 — touches order placement
**Complexity:** L — replaces the shell every mode lives in
**Epic:** [EPIC-033](../README.md)
**Depends on:** Engine W1, EPIC-W3; 033B

---

## 1. Context and problem
`MainWindow` (`src/presentation/ui/main_window.py:72`) is a `QMainWindow` whose central widget is a custom `Sidebar` beside a styled `QStackedWidget` (`:134-151`, `_CONTENT_BG_STYLE`). It has no menu bar. The sidebar is 202 px wide with `setFixedHeight(40)` buttons (`sidebar.py:326,331`) and breaks below 1100 px. `app_bootstrapper._apply_font` (`:530-539`) forces Consolas 10 pt on the whole application.

## 2. Acceptance criteria
- [x] The app's top window is the Engine's `WorkbenchShell`; every mode is a nested workbench host it switches between. — `MainWindow(WorkbenchShell)`; each screen's view is the central widget of a `ModeHost` (`support/ui_kit/mode_host.py`) until its mode is re-laid out (033H-033L, 033P).
- [x] The menu bar holds File, Edit, View, the modules' menus (Trade, Data, …), Tools, Window, Help in that order, every item with a unique access key; View lists the modes (Ctrl+1…), every dock of the current mode, Toolbars and Status Bar; Window → Reset Layout restores the mode's default perspective; Help → About shows name, version and venue. — the modules' own menus arrive with their commands in 033D; a mode whose panels live on its view's own surface (Bots, Dev Board) lists and resets that surface's docks.
- [x] Welcome is deleted: the app opens on the last used mode, as Windows applications do; developer mode moves to Tools → Options. — the last mode arrives as `RESTORE`; the first run opens on the Futures desk (the registry default); Tools → Options → Developer (`shell/developer_options/`).
- [x] The window title and the status bar name the venue (Testnet or Mainnet) in text, never by colour alone.
- [x] Modes are a vertical mode bar of checkable actions with icons and tooltips (Ctrl+1…Ctrl+8), as in Qt Creator; `Sidebar`, its 10 style sheets and its fixed heights are deleted.
- [ ] The application font is the platform's (`_apply_font` deleted); tabular numbers use `QFontDatabase.systemFont(FixedFont)` only where digits align. — the first half is done (the conformance `system_font` check passes); the fixed font for aligned digits is a column kind's job and lands with 033N.
- [x] Each mode's perspective is saved on exit and restored on start, keyed by mode and app version; a mismatched version resets, never crashes. — the Engine's `PerspectiveStore` through `presentation/ui/mode_perspectives.py`; keyed by mode and layout version.
- [x] The environment banner stays a non-movable toolbar row above every mode (`test_environment_banner_all_screens.py` stays green).
- [x] 033B's conformance rows for the shell checks are removed from the baseline. — `menu_bar_order`, every mode's `workbench_host`, the Dev Board's `docks_in_view_menu`, and the Welcome row.

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
- **Every mode is built at start** (the user's decision, 2026-10-04, over an Engine change for lazily built modes). So building a screen no longer means the user opened it: the work that used to start in a constructor for that reason moved to `IShownAsMode.on_mode_shown(source)` (`core/contracts/i_shown_as_mode.py`), which the window calls each time a mode shows. The Watchlist starts its stream on the first show; the Data screen runs its shard discovery on the first show; the Dev Board's opt-in auto-start (`BOT-034`) begins only on `USER_INTENT`, never on a restore (`BUG-104`).
- **`BUG-104`'s guarantee, restated.** It was "a remembered route is never built"; with every mode built at start it is "a remembered mode is shown as `RESTORE`, and nothing that needs a click goes live on a restore". `test_main_window_state.py` proves it on the real app with the auto-start enabled.
- **`ModeHost`** finds a view's own surface as a `RegionHost` that is the view's direct child (Bots, Dev Board), rather than a `surface` property: no Protocol, and Settings' non-workbench surface is not mistaken for one.
- **Navigation** goes through `MainWindow.navigate()` for clicks, shortcuts, View and restore alike, so the mode always hears why it was shown; `INavigationService` is now `presentation/ui/shell_navigation.py` over the window.
- **Welcome's other jobs**: the version and venue are in Help → About, the title and the status bar; the developer-mode switch is Tools → Options → Developer, written only on OK or Apply (a failed save now also restores the in-memory value, which the Welcome switch did not).
- **Not done here**: the fixed font for aligned digits (033N); the modules' own menus (033D). `src/config/user_config.json` still carries the three `ui.font.*` keys `_apply_font` read; removing them is a configuration change left for the user's approval.
- **Still owed to `ui-presentation-rule.md`** by this task: the conformance suite's 1024×700 run (§3), and moving dock object names and Reset layout from review to a check (§8). The restart half of the perspective check is proved by `test_main_window_state.py`, not yet by the conformance suite.
- **Desktop E2E** (open, rearrange, restart on a real display) is the user's to run; the integration suite covers the restart round trip offscreen.
