# EPIC-033K — Bots mode: create, judge, run and watch bots, laid out as HLD §11.2.1 designs it

**Status:** 🟡 In progress (stage 1 of 4)
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
| 2 | next | Each kind contributes its toolbar (SPEC-014: "each bot type has its own toolbar"): Grid's Suggest from ATR and Suggest from Bollinger become actions shown while a Grid is selected, in the Bots menu and disabled otherwise. |
| 3 | next | A strategy armed on a venue is a row of its own with Arm and Disarm until `EPIC-029L`; the desks' strategy and last-signal cards are deleted. It touches `trading/ui/desk/`, so it is coordinated with the session rebuilding the desks. |
| 4 | last | The SPEC journeys and the conformance suite for the finished mode; the desktop E2E (open, use, rearrange, restart); the task closes. |

### Decisions in stage 1
- **The kind's backtest is a fourth bottom panel.** HLD §11.2.1's row did not list it; it was a tab of the old detail and `EPIC-029D` built it. Its row now says "Orders, Fills, Log, Backtest (the kind's)". With no bot selected, or a kind without a backtest, the panel holds an instruction rather than hiding: a dock that hides itself fights the person's own View toggle and the saved perspective.
- **The status line stays at the top of the Bots panel**, not in the status bar: a refused action or an unreadable bot file is an alarm, and `ui-presentation-rule.md` §10 keeps alarms out of the status bar alone.
- **Fit levels is a command**, "Fit &levels" in the Bots menu, enabled while a bot is selected; HLD §11.2.2 lists it with Refresh fills among the commands its table does not name yet.

## Implementation notes (written when done)
Stage 1 delivered; stages 2–4 to come.
