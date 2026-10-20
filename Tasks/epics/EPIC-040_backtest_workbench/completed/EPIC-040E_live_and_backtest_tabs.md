# EPIC-040E — The Bots screen has Live and Backtest centre tabs; the bottom Backtest tab is gone

**Status:** ✅ Done (2026-10-20)
**Source:** The owner, 2026-10-14: *"could we move it to another tab with live chart? I know we could use tab widget"*
**Risk:** 🟡 — the screen's layout and its saved state (docks and geometry persist per mode)
**Complexity:** M — layout, saved-state migration, command wiring
**Epic:** [EPIC-040](../README.md)
**Depends on:** [EPIC-040D](EPIC-040D_backtest_workbench_shell.md)

---

## 1. Context and problem
- The backtest is a bottom dock tab beside Orders, Fills and Log (`ui/bots_screen/bots_view.py`, `_BacktestSlot` at line 305).
- Its charts' size hints fought the bottom docks, so `_BacktestSlot` exists only to shrink it (PR #361 review). It squeezes both the live chart and the backtest.
- The owner's screenshot of 2026-10-14 shows the backtest occupying half the height while the bot runs.

## 2. Acceptance criteria
- [x] The Bots mode's centre shows two tabs, **Live** and **Backtest**:
  - Live holds the live chart.
  - Backtest holds the 040D workbench for the selected bot.
- [x] The bottom docks are Orders, Fills and Log only. `_BacktestSlot` is deleted.
- [x] The Plan dock shows the real bot on both tabs; it is never the sandbox's editor. On the Backtest tab it may be hidden by the user like any dock.
- [x] A selected bot whose kind has no backtester, or whose venue the kind's backtest does not replay (`backtest_supports`), shows the Backtest tab disabled with a tooltip saying why. It is never hidden, because menus and tabs stay stable (MS `cmd-menus`).
- [x] View → Backtest (a `QAction` with a shortcut) switches to the tab. It is reachable by keyboard.
- [x] Saved window state from before the change loads without error. A stale "Backtest" bottom dock in the saved state is ignored.
- [x] The conformance suite passes at 1024×700, 1366×768 and 1920×1080. Preview frames exist for both tabs.

## 3. Design
**A stock `QTabWidget` in the centre region**, if the Engine's workbench region host has no tabbed centre of its own. Read `WorkbenchSurface` / `RegionHost` first; prefer the Engine's mechanism if it exists (P5). Tabs, not a mode, because the backtest belongs to the selected bot and shares its selection: a separate mode would need its own bot picker.

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Centre tabs Live / Backtest (chosen, the owner's proposal) | Each gets the full width. One selection drives both. Stock control. |
| Keep a bottom dock, just taller | Rejected: it still competes with the live chart while the bot runs. |
| A separate "Backtest" mode in the mode bar | Rejected for now: it duplicates bot selection, though it may suit a future multi-kind research mode. |
| Backtest in a floating window | It can come later: the tab can become a dock that floats, if asked. |

**Disabled, not hidden** for an unsupported kind or venue: KDE and MS guidance, and the rule's "inapplicable items disabled, never hidden".

**Risks:**
- **Saved-state compatibility.** Qt restores docks by object name; a missing name is skipped. Test with a saved state from master.
- **The live chart's feed when the Live tab is hidden.** Keep it subscribed, so switching back shows no gap. Measure the cost; the chart already throttles.
- **Two charts alive at once:** memory. Acceptable for one backtest chart. Note it for PRO-008's resource budget.

## 3a. Reuse
- **Layout:** used the Engine's region host if it offers tabs; otherwise a stock `QTabWidget`.
- **Commands:** used `QAction` registration through `kind_command_binding` / `bots_commands.py`, and `backtest_supports` for enabling.
- **Previews:** used the `preview_frames.py` pattern.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/bots_screen/bots_view.py` | Centre tabs; `_BacktestSlot` deleted |
| `src/modules/bots/ui/bots_screen/bots_presenter.py`, `detail_effects.py`, `kind_backtests.py` | Backtest hosted by the centre tab instead of the bottom dock |
| `src/modules/bots/ui/bots_screen/bots_commands.py` | View → Backtest action |
| `src/modules/bots/ui/bots_screen/preview.py`, `preview_frames.py` | Frames for both tabs |
| `tests/...conformance` | Sizes and the restored saved state |

## 5. Testing
- Conformance suite at three sizes.
- A presenter test: a selection change reaches both tabs.
- A disabled-tab test for an unsupported venue.
- Saved-state load from a pre-change file.
- The owner's visual check on Windows.

## Re-check against master (2026-10-20, `5e7d00f`)
The design held. The re-scopes, each with its reason:
- **A stock `QTabWidget`, as planned.** The Engine's region host has no tabbed centre of its own; `WorkbenchSurface` takes any widget as its centre, and `bots_view.py` already used stock tabs.
- **The workbench is hosted, not `BotBacktest`.** `KindBacktests` (one page per kind and venue) is replaced by `BacktestWorkbenches` (one workbench per venue, any kind). The Grid's own page stays in the tree until `040F` deletes it; nothing hosts it now.
- **One workbench per venue, all kept.** A workbench's chart and sync read its venue's market (`BUG-172`), so a bot of another venue needs another one; closing the first would drop a sandbox with edits without the question 040C promised. Each is kept and followed only by bots of its own venue.
- **Availability from the kind, not a table.** The tab is off when `IBotKind.backtester()` is `None` or the kind's `supported_profiles()` leaves the venue's market out, so a second kind (`040G`) needs no entry in `kind_panels`. `backtest_supports` and the Grid page's registration are now unused and go with `040F`.
- **View commands are named "tab".** View already lists the Backtest *mode* (`Back&test`), so the commands are "Live chart tab" and "Backtest tab" (Ctrl+J; Ctrl+digit is the mode bar's).
- **The workbench's results became tabs, and its top bar two rows.** With the workbench in the centre, the mode's minimum height was 551 px against the 500 px a 1024×700 window leaves, because the chart and the tabs beneath it stacked (246 px). Replay, Equity, Figures and Fills are one tab widget (153 px). A `QTabWidget` asks for its widest and tallest page, shown or not, so the period and the commands also share one row no longer (one row was 850 px, which made the mode 1020 px wide against the 984 px a 1024-wide window leaves, found in review): the period is a row, the commands and the status line the next. A page-level scroll area is not an option: the mode allows no scroll area inside another (a chart and a table are scroll areas).
- **A run on a hidden workbench continues.** Moving to a bot of another venue leaves the first workbench running (it is that bot's run); its failure still reaches the notifier, and its result is there when the person comes back.
- **Saved state.** Nothing migrates: Qt restores docks by object name and skips one the window no longer has, so a state saved with the Backtest dock loads (a test saves one and restores it into the new view).
- **Frames.** `bots_screen/centre_tab_frames.py`: the Live tab, the Backtest tab ready, with a result, and off.

## Implementation notes
**What shipped.** `BotsView.centre` (Live, Backtest) replaces the bottom Backtest dock and `_BacktestSlot`; `BacktestWorkbenches` follows the selected bot (its planner market and risk facts) on the workbench of its venue; `TabAvailability` turns the tab off, with a tooltip, for a kind with no backtest or a venue it does not trade on, never hiding it; View → Live chart tab and Backtest tab are commands of the Bots mode (`bots_commands.py`), the second following the tab (`bots_command_binding.py`); `WorkbenchPorts` gained the venue's `run_query` from the presenter's dependencies; the Bots screen's tests moved to the workbench (`test_bots_view.py`, `test_bots_backtest_tab.py`, `test_backtest_workbenches.py`, `test_bots_centre_tabs.py`).

**Mutation checks (each went red, then restored).** View → Backtest switching a tab that is off; the venue-support check dropped; the page re-shown on every follow; the page not put back after a note on the same venue; the command's enabled signal removed; Live and Backtest swapped; the market numbers not passed to the workbench; the shortcut dropped. One survived: the code that moved the current tab to Live when the Backtest tab was turned off was redundant, because Qt's tab bar does it, so it was deleted and the behaviour is pinned by a test.

**Review, round 1 (PR #635).** The mode's minimum width was 1020 px with a bot selected, either tab in front (Blocking; fixed as above, and the fit test now measures the width as well as the height with both tabs); the risk facts reaching the workbench and `close()` shutting every workbench down had no test that fails without them (both pinned; a spy on the real `BacktestWorkbench.shutdown`); the saved-state test now saves through `save_perspective`, with the old Backtest dock tabbed with Orders and Log hidden, and checks both survive `restore_perspective`; a tab that is off before the commands are bound starts off (pinned); and the leftovers for `040F` are named in its table.

**Verified / not.** Commit tier, the architecture suite, the bots, presentation and ui_kit unit tests and the Bots mode's conformance at its three sizes green; the Backtest mode's `1024x700/fits_the_window` fails locally on master too (719×706, container fonts) and passes in CI. Not verified: the owner's look on Windows, and the conformance checks with the Backtest tab in front (the suite reads each mode in its default state; the unit test pins the tab's minimum height instead).
