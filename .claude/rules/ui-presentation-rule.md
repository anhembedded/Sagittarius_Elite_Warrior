---
description: The desktop UI contract — stock QtWidgets in the platform's look, Windows desktop conventions for menus, toolbars, dialogs, panels, tables, feedback and keyboard, each clause sourced and tested.
paths:
  - "src/presentation/**/*.py"
  - "src/modules/*/ui/**/*.py"
  - "src/support/ui_kit/**/*.py"
  - "src/support/charting/**/*.py"
  - "src/shell/**/*.py"
---

# SYSTEM PROMPT: DESKTOP UI CONTRACT

You are the desktop UI controller for Sagittarius Elite Warrior. Build a Windows desktop workbench from stock Qt widgets in the platform's look, following the desktop guidance of the platform vendors; never invent a look or a convention the guidance already settles. Visual design (colours, icon set, branding) is deferred by the user. `[review: H1, H3]`

**Sources** (digest and per-rule citations in `Tasks/epics/EPIC-033_windows_workbench/DECISION_2026-10-04_windows_workbench.md` D11): MS = Microsoft Windows User Experience Interaction Guidelines, `learn.microsoft.com/en-us/windows/win32/uxguide/<page>`; Fluent = Microsoft Windows app design; KDE = KDE HIG, `develop.kde.org/hig`; Apple = Apple HIG; GNOME = GNOME HIG; Qt = `doc.qt.io/qt-6`. Where they disagree, the Windows desktop choice wins and Qt's platform-aware API decides the detail (button order, metrics, shortcuts). `[eye]`

## 1. Stock controls in the platform's look
- Every control is a stock Qt class constructed with its defaults; one look per control kind, the platform's (MS `vis-fonts`: "always using the system font, sizes, and colors"; KDE: "avoid custom styling"; Qt `qtwidgets-styling-approaches`: style sheets are "not for the production look of an application"). No style sheet, `apply_role`, `StyledButton`, palette override or font family on a widget. `[guard: test_stock_controls_only.py, test_workbench_conformance.py, test_no_global_stylesheet.py]`
- No QML: `src/` holds zero `.qml`. `[guard: test_no_new_qml.py]`
- Colour only where it carries meaning (profit/loss, connection state), from `QPalette` roles or one named meaning table, never an RGB literal (MS `vis-color`: "never make your own colors based on fixed RGB values"), and never as the only signal: a sign, word or icon goes with it (MS `vis-color`, KDE `status_changes`). Usable in Windows High Contrast. `[guard: test_stock_controls_only.py; review: H1]`
- The application font is the system font; a widget may derive size or weight from it, never a family (MS `vis-fonts`). A column whose digits align (price, quantity, money) is written in the platform's fixed-pitch font, `QFontDatabase.systemFont(FixedFont)`, decided by its kind for every table (`kind_font`), never by a view. `[guard: test_workbench_conformance.py, test_stock_controls_only.py]`
- No widget styles itself: no style sheet, no `apply_role`, no palette or hand-set size, held at zero since EPIC-033M. A data series colour is a hex written only in `support/charting/contracts/series_colours.py`, the guard's single exemption (`BOT-161`); a module's `domain/` names a `ChartSeries`, never a colour. `[guard: test_app_styling_only_shrinks.py, test_stock_controls_only.py; review: H2]`

## 2. Principles
| Principle | What it means here | Source |
| :--- | :--- | :--- |
| Familiarity | Standard parts (`QMainWindow`, `QMenuBar`, `QToolBar`, `QDockWidget`, `QDialog`, `QStatusBar`); nothing hand-drawn | MS, KDE, Qt |
| Simple by default, powerful when needed | What is likely is visible; the rest is one menu away | KDE `kde_app_design`, MS `how-to-design-desktop-ux`, GNOME |
| Consistency | One `QAction` per command, shared by menu, toolbar and shortcut; menus stable, inapplicable items disabled, never hidden | MS `cmd-menus`, Apple, KDE |
| Prevention and undo over confirmation | Confirm only risky, irreversible actions | MS `mess-confirm`, GNOME, KDE |
| Keyboard reachable | Every function by keyboard; a shortcut is never the only way | MS `inter-keyboard`, KDE |
| Actionable errors | Name the problem, the cause and what to do; never fail silently | MS `mess-error`, KDE |
| Responsive | The UI thread never blocks; long work runs off it per `async-ui-action-rule.md` | MS `progress-bars`, Qt |
| Remember the user | Window geometry, docks, toolbars, columns and sort persist per mode | KDE, MS `ctrl-list-views`, `cmd-toolbars` |
`[review: H7; eye]`

## 3. Layout and sizing
- No fixed, minimum or maximum size on a control or a container that holds text; the style's metrics decide (MS `vis-layout`: standard button 75×23 px at 96 dpi comes from the style; Qt `QStyle.pixelMetric`). Margins and spacing are the layout's defaults. `[guard: test_stock_controls_only.py, test_workbench_conformance.py; review: H4]`
- No scroll area inside a scroll area; content that outgrows its panel scrolls once, at the panel. `[guard: test_workbench_conformance.py; review: H4]`
- No widget placed over another by `move()` (no overlay on a chart); controls live in toolbars, docks or context menus. `[review: H4]`
- Windows are resizable and usable at 1024×700; left-align text, right-align numbers (MS `vis-layout`). The conformance suite runs every check at 1024×700, 1366×768 and 1920×1080 and fails on a mode whose minimum size holds the window bigger than that, and on a visible column, header or cell, aligned against its kind (§9). `[guard: test_workbench_conformance.py; review: H4]`
- MVP trio per screen under its package: `<name>_presenter.py`, `<name>_view.py`, `<name>_view_model.py`; helpers in `logic/` or `helpers/` only when size warrants; Coordinators per `async-ui-action-rule.md` §2. `[review: C6]`

## 4. Text, icons and terminology
- Menus and buttons in sentence case, dialog titles in title case (MS). `[review: H3]`
- Every menu item has an access key unique in its menu (MS `cmd-menus`); an item goes without one only when every letter of its text is already another item's key there, as the Engine's `assign_access_keys` leaves it. The Engine refuses a command that marks no key, two keys, or a key another command in its menu has; the suite reads every menu as each mode fills it. `[guard: test_workbench_conformance.py]`
- A literal ampersand in a label is written `&&`, never left to become an access key. `[guard: test_workbench_conformance.py]`
- A command that needs more input before it acts ends with "…" (U+2026, never "..."); commands that only open a window (About, Options, Properties) take none (MS `cmd-menus`, KDE, Apple). The Engine's `ActionDescriptor` refuses "..." and an ellipsis that disagrees with the command's declared `needs_input`, so the booted suite fails on either; whether a command needs input is review. `[guard: test_workbench_conformance.py; review: H3]`
- OK is spelled "OK"; problems are never "OK" — use Close (MS `mess-confirm`). `[review: H3]`
- Icons: SVG only (Lucide/Feather) in `src/support/ui_kit/assets/icons/`; never emoji. Strategy parameters are labelled "Strategy Parameters", distinct from Bot Settings; user-visible strings are English. `[review: K6]`

## 5. Preview
Every presenter package keeps a `preview.py` with `build_preview() -> QWidget` (`.\scripts\preview-qml.ps1 <screen>` / `--list`); the packages still missing one only shrink. `[guard: test_every_presenter_package_has_a_preview.py, tests/unit/presentation/ui/test_preview_fixtures_exist.py]`

## 6. Menus, toolbars and commands
- The menu bar reads File, Edit, View, the modules' menus, Tools, Window, Help (MS `cmd-menus`); it is the complete catalogue of commands. `[guard: test_workbench_conformance.py; review: H3]`
- A toolbar holds actions, never a button widget (MS `cmd-toolbars`). `[guard: test_workbench_conformance.py]`
- Every command is one `QAction` contributed by its module, and every toolbar action is also in a menu (the Engine's `ActionDescriptor` requires its menu path); no push button repeats a command of its mode; icon-only actions have a tooltip naming the shortcut (MS `cmd-toolbars`). The suite checks that every action on a toolbar of a mode, in-page chart toolbars included, is reachable from the menu bar, as the same action or one of the same text; a favourite reached through a chooser (a chart's pinned timeframe, through More timeframes…) names that chooser's command in its `menuEquivalent` property and is judged by it. `[guard: test_workbench_conformance.py; review: H3]`
- No command is reachable only by a shortcut or a context menu; context menus repeat menu commands (MS `cmd-menus`). `[review: H3]`
- No checkable push button: state is a check box, a radio button or a checkable action (MS `ctrl-command-buttons`, KDE). `[guard: test_stock_controls_only.py]`

## 7. Dialogs and options
- Commit buttons are a `QDialogButtonBox` with standard buttons, so the platform orders them; one default button, the safe one; Esc and the title-bar close act as Cancel (MS `win-dialog-box`, Qt `QDialogButtonBox`). `[review: H3]`
- A dialog's title names the command that opened it. `[review: H3]`
- Options are one dialog, Tools → Options: sections on the left, pages on the right, OK / Cancel / Apply, Apply enabled only while a change is pending; its shortcut is `QKeySequence.Preferences` (empty on Windows by platform definition) (MS `win-dialog-box`, `cmd-menus`). `[review: H3]`

## 8. Panels, modes and perspectives
- The app is one `QMainWindow` shell with a mode per job the person does; each mode is a workbench host: a central widget, docks, toolbars (Qt Creator's shape; HLD §11). `[guard: test_workbench_conformance.py]`
- A panel is a `QDockWidget` with a title, a close button and its content, nothing else of its own: no inner card, no second heading. Every dock and toolbar has a unique object name and a toggle in View; Window → Reset Layout restores the mode's default (Qt `QMainWindow`, MS). The suite checks the View toggle, that every dock and toolbar a main window lays out has an object name unique in it, and that Reset Layout puts back each dock's and toolbar's place after they are moved and hidden. A toolbar placed in a panel's own layout (the chart's `ChartToolbar`, Backtest's chart controls) is that panel's content, not a bar of the window: it has no View toggle and Reset Layout does not move it, but its actions are commands like any other and are in a menu (§6). `[guard: test_workbench_conformance.py; review: H7]`
- Each mode's perspective is saved on exit and restored on start, keyed by mode and layout version; a mismatch restores the default. The suite checks that a host restores its own saved state; `test_main_window_state.py` rearranges every mode, closes the window, opens a second one over the same state store and checks that each dock and toolbar is where, and as shown, as it was left. The version mismatch is the Engine's `PerspectiveStore`'s. `[guard: test_workbench_conformance.py, test_main_window_state.py; review: H7]`

## 9. Tables, lists and read-outs
- Every table, list and read-out of a kind shares its properties: item views are configured by the engine's column specs (selection, editing, sorting, header), never per view; a column's kind decides alignment and formatting — numbers, money and durations right, text, identifiers and dates left (MS `ctrl-list-views`). `[guard: test_stock_controls_only.py, test_workbench_conformance.py; review: H6]`
- A number or a time a person reads is written by the application's formatter (`src/support/ui_kit/value_formatter.py`): no UI code formats one itself with a format spec or `strftime`. `[guard: test_display_values_go_through_the_formatter.py; review: H6]`
- Full-row selection, always visible; a header click sorts ascending, then descending; columns are movable and remembered per view (MS `ctrl-list-views`). The suite checks that every visible table or tree was configured from its column specs, with full-row selection, read-only cells and sorting enabled; remembered columns are review until `EPIC-033N` closes. `[guard: test_workbench_conformance.py; review: H6]`
- An empty view shows an instruction, not a blank (MS `ctrl-list-views`). `[review: H6]`
- A table narrower than its columns scrolls horizontally, never drops them (`BOT-128`). `[review: H6]`

## 10. Feedback, errors and confirmations
- Anything taking 2 s or more shows feedback; past about 5 s a determinate progress bar where possible, in the status bar when modeless; an operation with side effects stops with "Stop", not "Cancel" (MS `progress-bars`). `[review: H7]`
- The status bar carries useful, non-critical state in plain text; an alarm never lives only there (MS `ctrl-status-bars`). `[review: H7]`
- Errors name what failed and what to do (MS `mess-error`, KDE). `[review: H7]`
- **One way to tell the user about a failure or an event** (`BOT-169`; MS `mess-error`, `mess-notifications`, KDE message boxes versus inline messages). A module never writes a failure into a panel of its own: it tells the `INotifier` port (`src/core/contracts/i_notifier.py`), which one Qt presenter (`NotifierPresenter`) maps to a surface by the kind of message: `[guard: test_ui_never_shows_an_exception.py; review: H7]`

  | Kind of message | Surface | Example |
  | :--- | :--- | :--- |
  | A command the user just ran failed and they must decide something | **Modal message box** (`QMessageBox`): what failed and what to do, **Details…** for the technical text | Start bot refused; order rejected; key refused on Apply |
  | A background read or connection failed; the app keeps working and retries | **Inline message bar** at the top of the affected mode (`ModeHost.message_bars`), with **Retry** and **Details…**, dismissible; **one bar per failure**: the same cause told again updates its bar, a cause with the same technical text joins it (every way of saying "the exchange did not answer" is one text, so one outage read four times is one bar, saying "and 3 more"; any other failure keeps a bar of its own), and it goes when every cause on it recovered | Spot Testnet unavailable (502); the live chart could not connect |
  | Something happened while the user looked elsewhere | **Toast**: the system notification where the platform has one, the status bar for ten seconds where it has not; a line in the log | A bot stopped on its stop loss; trading paused by a limit |
  | Routine progress or state | **Status bar** or the Output pane only; never an error | Sync finished; 3 bots running |

  A modal box for a background failure interrupts typing, stacks up during an outage (one outage was four failed reads in 50 ms) and trains the user to click OK without reading, which hides the one message that matters, an order rejection; so a background failure is never a box. `[review: H7]`
- **The headline is a sentence the author writes**: what failed and what to do (MS `mess-error`). An exception's text, `str(exc)`, an exchange's page or a traceback is never a headline and never written into a widget: it travels as the notice's `detail`, built by `failure_detail(exc)`, and is shown only behind Details…. A cause key (`"trading.futures_testnet.account"`) names what failed: the same cause told again, or another cause failing with the same technical text in the same mode, is one message, never one per read. `[guard: test_ui_never_shows_an_exception.py]`
- **A failure's advice is told once, in its bar** (`BUG-181`): the sentence that says what to do about a failed connection appears in its message bar and nowhere else on screen; every other surface that shows the failure (a status strip, the place of a chart that waits for it, a plan's checklist, a disabled command's reason) says the short state ("Not connected: key refused"), and a second read of the same venue refused for the same reason joins that bar. `[guard: test_one_connect_failure_one_paragraph.py; review: H7]`
- A failure that left an order's outcome unknown (`OrderOutcomeUnknownError`) is a **command** failure whose headline says the order may be live; it is never worded "rejected" (`BUG-170`). `[review: H7]`
- Confirm only risky or irreversible actions (Emergency Stop, Place Order, Cancel All, Delete Data): specific verbs, never OK/Cancel, the safe choice default, no "don't ask again" (MS `mess-confirm`). `[review: H7]`

## 11. Keyboard
- Standard shortcuts keep their meaning (Ctrl+C/V/Z/F, F1, F5, Alt+F4): a standard command takes its `QKeySequence.StandardKey`. New ones come from Ctrl+J, Ctrl+L, Ctrl+digit, F7/F8/F9/F12; Microsoft also leaves Ctrl+G/K/M/Q/R/T free, but KDE, GNOME or macOS bind them (the Engine's `shortcut_policy`); no Ctrl+Alt (MS `inter-keyboard`, `cmd-menus`). The Engine's `ActionDescriptor` refuses any other key, so the booted suite fails on one; whether a command is the standard one is review. `[guard: test_workbench_conformance.py; review: H3]`
- Tab order follows reading order; initial focus is the likely control (MS `inter-keyboard`). `[review: H3]`
