# EPIC-033K — Bots mode: create, judge, run and watch bots, laid out as HLD §11.2.1 designs it

**Status:** 🟡 In progress (stages 1 and 2 of 4)
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🔴 — arms live strategies
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**SPEC:** SPEC-014 (the Bots tab of `EPIC-029F`, rebuilt as the mode); SPEC-010 when specified
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Arming a strategy lives in a card inside each desk and the last signal in another card on Dev Board, while `EPIC-029F` (PR #333) builds the Bots tab as its own `WorkbenchSurface` holding a push button, a splitter and hand-configured tables. There is no one workbench where a person sees everything that trades for them; `EPIC-029` already decided that place is Bots, with signal strategies becoming a bot kind (`EPIC-029L`).

## 2. Acceptance criteria
- [ ] The central widget and default docks are exactly those HLD §11.2.1 lists for this mode (the one list; this task does not copy it). The chart and the Plan, Orders, Fills and Log docks follow the selection in the Bots dock.
- [ ] The Bots menu and toolbar hold exactly HLD §11.2.3's commands; each bot kind contributes its panel and its toolbar, shown while a bot of that kind is selected; SPEC-014's behaviour (lifecycle-gated actions, one action at a time, the Stop dialog's *keep* default, the close guard) is unchanged.
- [ ] A strategy armed on a venue is listed as its own row with Arm and Disarm actions until `EPIC-029L`.
- [ ] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [ ] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the Bots tab's view (its presenter, coordinators, fenced reads and view model are kept; its 7 `item_view_config` lines leave `baseline_stock_controls.json` with it), the strategy and last-signal cards.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Stages
Reviewable pull requests, as `EPIC-033L` (Backtest) was delivered:

| Stage | Pull request | What |
| :--- | :--- | :--- |
| 1 | this task's first PR | The layout: the selected bot's chart is the central widget; Bots (the list, with the status line) is a `NAVIGATOR` dock; Plan (name, state, figures, the kind's editor, its verdicts) a `RAIL` dock; Orders, Fills, Log and the kind's Backtest tabbed `CONSOLE` docks. The surface accepts those four places in `shell/surfaces.py`. Fit levels, a push button over the chart, becomes a Bots menu command. `BotDetailPanel` and its `QTabWidget` are deleted. |
| 2 | ✅ delivered (2026-10-06) | Each kind contributes its toolbar (SPEC-014: "each bot type has its own toolbar"): Grid's Suggest from ATR and Suggest from Bollinger become actions shown while a Grid is selected, in the Bots menu and disabled otherwise. |
| 3 | next | A strategy armed on a venue is a row of its own with Arm and Disarm until `EPIC-029L`; the desks' strategy and last-signal cards are deleted. It touches `trading/ui/desk/`, so it is coordinated with the session rebuilding the desks. |
| 4 | last | The SPEC journeys and the conformance suite for the finished mode; the desktop E2E (open, use, rearrange, restart); the task closes. |

### Decisions in stage 1
- **The kind's backtest is a fourth bottom panel.** HLD §11.2.1's row did not list it; it was a tab of the old detail and `EPIC-029D` built it. Its row now says "Orders, Fills, Log, Backtest (the kind's)". With no bot selected, or a kind without a backtest, the panel holds an instruction rather than hiding: a dock that hides itself fights the person's own View toggle and the saved perspective.
- **The status line stays at the top of the Bots panel**, not in the status bar: a refused action or an unreadable bot file is an alarm, and `ui-presentation-rule.md` §10 keeps alarms out of the status bar alone.
- **The Plan panel scrolls once, at the dock, and the Grid backtest's figures scroll in their own pane** (PR #361 review). Without that, the mode's minimum height was 703 px, and 997 px with the Backtest tab in front: it could not fit a 1024×700 window. The verdicts are word-wrapped lines inside the Plan's one scroll area, not a list scrolling inside it. `test_bots_view.py::test_the_mode_fits_a_small_window_with_a_grid_and_its_backtest_in_front` and `test_grid_backtest.py::test_a_runs_figures_scroll_in_their_pane_and_never_raise_the_floor` hold it.
- **The Backtest panel asks the dock area for no more than its minimum** (PR #361 re-review). The Grid backtest page's charts hint at 850×1104 px, and the bottom docks took that hint, leaving the chart 104 of 768 px. `test_bots_view.py::test_with_a_grid_selected_the_chart_keeps_the_larger_share_of_the_window` holds the chart above half the height.
- **`WorkbenchSurface.dock_of` is the shared lookup; `BackTestView.dock_of` keeps its own copy for now.** `backtesting/ui/` is being rebuilt by `EPIC-033L`'s parallel session, so this PR does not edit it. That session may make its copy call `self._surface.dock_of(widget)`.
- **Fit levels is a command**, "Fit &levels" in the Bots menu, enabled while a bot is selected; HLD §11.2.2 lists it with Refresh fills among the commands its table does not name yet.

## Implementation notes (written when done)
Stages 1 and 2 delivered; stages 3 and 4 to come.

### Stage 2 — each kind's commands and toolbar
- **Declared Qt-free, by kind.** `kinds/kind_commands.py` maps a `kind_id` to its `KindCommand`s (id, menu text); `bots_commands.py` contributes every one to the Bots menu after Delete bot, not on the mode's toolbar. Grid's are "Suggest from &ATR" and "Suggest from Bollin&ger" (HLD §11.2.3's keys; A and G were free in the Bots menu). A second kind is one entry there and its editor's `kind_actions`.
- **The toolbar is the kind's editor's.** `BotKindPanel.kind_actions()` (default: none) gives the actions by command id; `GridPanel` holds a `QToolBar` ("Grid", `toolbarGridKind`) at the top of the editor with the two actions, where the two push buttons sat under the fields. The editor exists only while a bot of its kind is selected, so the toolbar shows exactly then. It is panel content (`ui-presentation-rule.md` §8, as Backtest's chart controls): no View toggle, nothing for Reset layout to move, and a dock that hides itself is avoided (stage 1's decision).
- **The menu follows the toolbar through one shared mechanism.** `ChartCommandMirror`'s drive-and-follow body moved to `support/ui_kit/action_mirror.py` (`ActionMirror`); `ChartCommandMirror` names the chart's commands over it, and `KindCommands` (`bots_screen/kind_command_binding.py`) the kinds'. `bind_bots_commands` builds `KindCommands` on the view model; the presenter hands each selection's editor to it (`follow_panel_of`, `None` with no selection). A menu command is enabled exactly while its toolbar action is: a Grid selected, editable, and the planner holding that range. Writing a second follower was the duplication `test_presenter_duplication_only_shrinks.py` caught (`_on_command`, `_on_enabled`: 32 → 34); sharing it kept 32.
- **A defect found on the way.** `GridPanel.set_planner_market` re-enabled the suggestions whatever the editor's state, so a running Grid, read-only from the moment it was shown, offered them once the planner answered. `_offer_suggestions` now holds them off while read-only; `test_grid_panel.py::test_a_read_only_panel_offers_no_suggestion_when_the_planner_answers_late` was red before the fix.
- **Proof:** `test_kind_commands.py` (contributed to the Bots menu, not the mode's toolbar; a menu command follows the Grid toolbar's action and fills the range; on the screen, live for a selected draft Grid and off for a running one or none; red when the presenter stops handing the editor over or the binding is dropped), the conformance suite (access keys unique per menu, every toolbar action in a menu and worded as it, no push button duplicating a command).
