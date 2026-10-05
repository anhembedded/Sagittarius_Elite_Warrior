# EPIC-033L — Backtest mode: test a strategy on stored history, laid out as HLD §11.2.1 designs it

**Status:** 🟡 In progress (stage 2a of 4)
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🟡 — the most styled area (61 `setStyleSheet` calls)
**Complexity:** L
**Epic:** [EPIC-033](../README.md)
**SPEC:** SPEC-009 when specified
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Backtest is a page whose parameter bar of pill dropdowns clips at 1366 px, scrolls a chart inside a page scroll, and owns 16 hand-styled dialogs.

## 2. Acceptance criteria
- [ ] Run setup is a dock (or one Run Settings… dialog) with market, symbol, strategy, timeframe, range, timezone, capital and execution; Run backtest is an action (F7, HLD §11.2.3) and Stop backtest is enabled only while a run runs. *(Corrected 2026-10-05: the task said F5, which keeps its standard meaning, Refresh, and HLD §11.2.3 gives F7; "Stop replaces Run" would hide a command, which `ui-presentation-rule.md` §2 forbids — the two actions stay, and each is disabled while it does not apply.)*
- [ ] The central widget and default docks are exactly those HLD §11.2.1 lists for this mode (the one list; this task does not copy it). Every remaining dialog is a stock `QDialog` with `QDialogButtonBox`.
- [ ] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [ ] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the Backtest screen and its 16 dialogs.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

### Stages (one pull request each)
1. **Re-host into the workbench.** A left-dock place (`Place.NAVIGATOR` → `DOCK_LEFT`); the view on a `WorkbenchSurface`: result chart central, Run setup left (`RunSetupPanel`, a form of stock controls replacing the pill toolbar), Metrics right (the banners and figures), Trades bottom. `PageShell`, the page scroll area and the splitter's 1000 px of minimum heights go; `IBacktestView`'s 19 members are unchanged.
2. **Stock controls**, in two pull requests. **2a:** the trades list becomes a table built from its column specs, with a filter, a search and the selected trade's journal; Drawdown and Monthly returns become bottom docks; the panel's Export button becomes Tools → Export trades…. **2b:** Monte Carlo becomes a bottom dock beside Trades; progress moves to the status bar; the simple pickers (timeframe, range, time zone) become fields.
3. **Dialogs.** The remaining overlays become `QDialog`s with a `QDialogButtonBox`.
4. **Clean-up.** The mode's baseline rows and ratchet entries reach zero.

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Implementation notes (written when done)
**Stage 1 (2026-10-05).** `src/core/contracts/place.py` gains `NAVIGATOR` (the left dock: what the centre is picked or set up from), mapped to `RegionKind.DOCK_LEFT` in `workbench_surface.py` and filled after the workspace in `surface_building.py`; the vocabulary, HLD §4/§11.2.5 and SDD-02 list it. `BackTestView` hosts a `WorkbenchSurface` (`BACKTEST_SURFACE`, held equal to `shell/surfaces.py` by `test_backtest_mode_layout.py`) with the docks Run setup, Metrics and Trades. `run_setup_panel.py` is the old toolbar as a `QFormLayout`; values are escaped so an ampersand never becomes an access key. The trades panel keeps its `BUG-004` minimum height until stage 2 replaces its hand-built rows. Measured: `no_nested_scroll` leaves the conformance baseline; style-sheet calls 89 → 78; `backtest_top_panel.py` 734 → 497 lines. Review of PR #355: the Run setup's access keys took Alt+T, Alt+E and Alt+R from Tools, Edit and Trade; they now avoid every menu-bar key, which `test_backtest_mode_layout.py` derives from the shell's menus and every contributed command. The four figures abreast made Metrics 563 px wide and left the chart 558 px of 1366; two to a row and a two-line header leave it 771 px, held by a test. A perspective saved before this change has nothing to restore: the screen had no surface, so `ModeHost` saved none for it.

**Stage 2a (2026-10-05).** `trade_table_model.py` (`TradeTableModel`) holds each `TradeLogRow` as raw values under ten column specs — number, side, entry and exit time and price, quantity, size, net profit, return — with the profit and return coloured by sign as well as signed. The panel (`backtest_trade_logs_panel.py`, rewritten) is a "Show:" combo box, a "Find:" field with a clear button, the `SpecTable`, and a form of the selected trade's journal (`trade_details()`: entry and exit reason, duration, MAE, MFE, the strategy's metadata). Selecting a row is `PROP-001`'s chart link. Times are written in the mode's display time zone through `ZonedValueFormatter` (`support/ui_kit/value_formatter.py`), which asks the zone when it writes; the coordinator resets the model on a zone change. The view model holds raw rows and no page: the table scrolls, so pagination (`trade_log_pagination.py`, twenty rows a page) and the `BUG-004` floor went; the visibility test now asserts the table's first row is on screen. `trade_log_row_to_qml` and the hand-built row, filter-tab and column files are deleted. Drawdown and Monthly returns are bottom docks (`result_panels.py`) tabbed with Trades; `activeBottomTab` went with the tab bar. Export is Tools → Export trades…, enabled while trades are listed. Measured: style-sheet calls 78 → 52, `apply_role` 32 → 31, `backtest_trade_logs_panel.py` 443 → 192 lines and off the god-file list.
