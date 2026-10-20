# EPIC-040E — The Bots screen has Live and Backtest centre tabs; the bottom Backtest tab is gone

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"could we move it to another tab with live chart? I know we could use tab widget"*
**Risk:** 🟡 — the screen's layout and its saved state (docks and geometry persist per mode)
**Complexity:** M — layout, saved-state migration, command wiring
**Epic:** [EPIC-040](../README.md)
**Depends on:** [EPIC-040D](../completed/EPIC-040D_backtest_workbench_shell.md)

---

## 1. Context and problem
- The backtest is a bottom dock tab beside Orders, Fills and Log (`ui/bots_screen/bots_view.py`, `_BacktestSlot` at line 305).
- Its charts' size hints fought the bottom docks, so `_BacktestSlot` exists only to shrink it (PR #361 review). It squeezes both the live chart and the backtest.
- The owner's screenshot of 2026-10-14 shows the backtest occupying half the height while the bot runs.

## 2. Acceptance criteria
- [ ] The Bots mode's centre shows two tabs, **Live** and **Backtest**:
  - Live holds the live chart.
  - Backtest holds the 040D workbench for the selected bot.
- [ ] The bottom docks are Orders, Fills and Log only. `_BacktestSlot` is deleted.
- [ ] The Plan dock shows the real bot on both tabs; it is never the sandbox's editor. On the Backtest tab it may be hidden by the user like any dock.
- [ ] A selected bot whose kind has no backtester, or whose venue the kind's backtest does not replay (`backtest_supports`), shows the Backtest tab disabled with a tooltip saying why. It is never hidden, because menus and tabs stay stable (MS `cmd-menus`).
- [ ] View → Backtest (a `QAction` with a shortcut) switches to the tab. It is reachable by keyboard.
- [ ] Saved window state from before the change loads without error. A stale "Backtest" bottom dock in the saved state is ignored.
- [ ] The conformance suite passes at 1024×700, 1366×768 and 1920×1080. Preview frames exist for both tabs.

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
