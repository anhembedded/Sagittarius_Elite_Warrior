# EPIC-033I — Trade mode: one mode for both venues, laid out as HLD §11.2.1 designs it

**Status:** 🔵 Backlog (planned in 4 stages)
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🔴 — the money-moving mode
**Complexity:** L
**Epic:** [EPIC-033](../README.md)
**SPEC:** [SPEC-004](../../../../Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md), [SPEC-005](../../../../Docs/SPEC/SPEC-005_place_a_manual_order.md), [SPEC-012](../../../../Docs/SPEC/SPEC-012_place_a_spot_order.md), [SPEC-013](../../../../Docs/SPEC/SPEC-013_see_my_account_on_a_desk.md); SPEC-006 and SPEC-007 when specified
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Futures and Spot are two separate page-shaped modes today, each a fixed splitter with an order form in its own scroll area, and the Dev Board has a third order path behind F9.

## 2. Acceptance criteria
- [ ] The central widget and default docks are exactly those HLD §11.2.1 lists for this mode (the one list; this task does not copy it). One Trade mode; the venue is chosen on its toolbar (only enabled venues listed); each venue keeps its own saved perspective.
- [ ] The Trade menu, its shortcuts, toolbar placement and confirmations are exactly HLD §11.2.3's; Emergency stop is also on every mode's toolbar.
- [ ] Confirmations follow the rule: risky actions only, the safe choice as default, specific verbs ("Place order", "Cancel all"), never OK/Cancel.
- [ ] The user confirms one order round-trip per venue on Testnet.
- [ ] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [ ] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the Futures and Spot desks and the Dev Board order dialog.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Stages
Reviewable pull requests, as `EPIC-033L` (Backtest) and `EPIC-033K` (Bots) were delivered. Each leaves the app working.

| Stage | Pull request | What |
| :--- | :--- | :--- |
| 1 | this task's first PR | **One Trade mode** (`trade`, the default mode) replaces the routes `trading.futures` and `trading.spot`. One page per enabled venue, each a `WorkbenchSurface` of its own (`trade.<venue>`) so each keeps its own saved layout; the shell's mode host follows the page shown (`ISurfaceStack`). The page: the chart central; the symbol and the status line on its header toolbar; Order entry above Account summary on the right; Account (today's tab panel), Equity and Strategy tabbed at the bottom. Trade → Venue › Futures, Spot (only enabled venues, exclusive, remembered) on the mode's toolbar; Enable live trading and New order… (F9) act on the venue chosen; Emergency stop (F8) is on every mode's toolbar and stops every enabled venue. The desks' screens, factories, command file and disabled-desk presenter are deleted; their `no_style_sheet` baseline rows go. |
| 2 | next | **The bottom panels HLD §11.2.1 lists.** The account tab panel becomes Positions (Futures) or Assets (Spot), Open orders, Order history and Trade history docks, tabbed with Equity, each table from its column specs; "Hide other pairs" becomes a checkable command; the tables' outcome line moves to the venue's status line. |
| 3 | next | **The Trade menu complete, and its confirmations.** Cancel order (Del) and Cancel all orders (toolbar) become Trade menu commands acting on the chosen venue's Open orders, and Close position… on its Positions; the tables' own toolbars go, which takes the mode's `failing_with_venues` baseline rows to zero. Every confirmation of the mode asks with its verb and the safe default, never OK/Cancel or Yes/No: Place order (today a Yes/No box), Cancel order, Cancel all, Close position, and Enable live trading on enable only (HLD §11.2.3), which the Engine's action confirms on every trigger today. |
| 4 | last | **Close.** The Strategy panel leaves with arming (`EPIC-033K` stage 3, coordinated: the Bots mode lists an armed strategy per venue); the SPEC journeys and the conformance suite for the finished mode; the desktop E2E (open, use, rearrange, restart); the user's Testnet round trip per venue; the task closes. |

## Implementation notes (written when done)
Not started.
