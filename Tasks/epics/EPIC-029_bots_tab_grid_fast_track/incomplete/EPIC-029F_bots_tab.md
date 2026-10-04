# EPIC-029F — The Bots tab: a list of bots, a common shell, the Grid panel with live verdicts, and the lifecycle controls

**Status:** 🔵 Backlog
**Source:** [`PRO-006`](../../../proposal/PRO-006.md). The user's words, 2026-10-03: *"thêm 1 tab
là bot trading … Tab đó có thể chọn loại bot, và tùy vào các bot sẽ có thanh công cụ riêng"* ("add
a Bot trading tab; it picks the bot type, and each bot type has its own toolbar"). The design is in
ADR D19 and O4.
**Risk:** 🟡 — a new screen must pass the route wiring, laziness and MVP guards, and its async
actions must be fenced.
**Complexity:** L — screen, list, detail shell, New Bot dialog, Grid panel, stop dialog, preview,
UI FSM and a SPEC.
**Epic:** [EPIC-029](../README.md)
**SPEC:** `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, written by this task.
**Depends on:** `EPIC-029B` (queries and commands), `EPIC-029C` (verdicts) and `EPIC-029G` (the
chart). The buttons drive bots through `EPIC-029B`'s use-case commands. `EPIC-029E` implements the
behaviour behind those same commands, so this task is built and tested with a fake executor. The
end-to-end run with the real executor is checked when both are merged, in `EPIC-029H`'s
preconditions.

---

## 1. Context and problem

There is no place to create or watch a bot. Strategy controls live on the desks and the Dev Board
(`trading/ui/dashboard/dev_board_widgets/strategy_card.py`). The navigation has Welcome 5,
Dev Board 10, Futures 16, Spot 17, Database 20 and Watchlist 30, and Backtest sits in the QUANT
ENGINE section.

## 2. Acceptance criteria

- [ ] **Route.** The `bots` route appears as NAVIGATION item 18, "Bots", with a Lucide icon.
  `contribute()` stays lazy.
  `tests/unit/shell/test_screen_wiring.py` changes in all three places that pin the routes:
  - `_EXPECTED_ROUTES`, in contribution order, not NAVIGATION order;
  - `_real_modules`, which builds `BotsModule`;
  - the `by_route` map.
- [ ] **The list.** Each row shows the name, the kind, the venue, the symbol, a state pill
  (Draft, Running, Paused, Recovering, Halted, Stopped or Error) and the PnL. The pill's text
  names the state; colour is never the only signal.
- [ ] **The detail shell** is the same for every kind. It shows:
  - the header with name, state and the Start/Pause/Resume/Stop actions that are legal in that
    state (from the FSM; illegal ones disabled, with a tooltip saying why);
  - venue, symbol, capital, grid profit, unrealised PnL and running time;
  - the bot's chart (`EPIC-029G`);
  - its orders and fills, filtered by its tag;
  - its log.
- [ ] **New Bot dialog.** The dialog asks for kind (Grid only for now), then venue (Spot venues
  that are enabled), then symbol, then parameters.
  - The symbol is an explicit field. It never comes from a chart.
  - The OK button names what it does ("Create bot").
  - Cancel restores everything.
- [ ] **The Grid panel.** Every parameter is editable.
  - Derived values and verdicts recompute on each edit, without blocking the UI thread.
  - A REFUSED verdict disables Start and says why.
  - Warnings show their threshold and their measured value.
  - "Suggest from ATR" and "Suggest from Bollinger" fill the fields only when the user clicks.
  - The planner preview draws the proposed levels on the bot's chart.
- [ ] **The charts are `BotChart`** (`EPIC-029G`, ADR D16). The planner preview and the running bot's
  chart each host a `BotChart` (`show_symbol`; `follow` with `BotTickFeed` for the running bot) and draw
  only through `show_overlay`, never through a drawer of their own (the PR #321 review). A level outside
  the candles' range is off screen today (`029G` notes): offer a "fit levels" view.
- [ ] **Stop dialog.** Its default is O3's answer. It states that resting orders will be cancelled
  and what happens to the base.
- [ ] **Closing the app** while a bot is RUNNING warns, with Cancel (O4).
- [ ] **One action at a time.** Every action runs through a presenter-owned coordinator with an
  action id. A stale completion is dropped, and a cancelled action publishes nothing and restores
  the prior state.
- [ ] **Preview.** `preview.py` builds the screen with sample bots in every state.
- [ ] **SPEC.** `SPEC-014` follows the template (trigger, preconditions, flow, failures, what it
  does not promise, ports, proven by) and is listed in `Docs/SPEC/README.md`.

## 3. Design

- **MVP:**
  - `bots_screen.py` (the contribution);
  - `bots_presenter.py`, `bots_view.py` and `bots_view_model.py`;
  - `bots_ui_fsm_matrix.py` for the screen's own modes: no selection, viewing, editing a draft,
    action in flight.
- **One component per kind's panel, chosen through `IBotKind`.** Only `GridPanel` exists, in
  `ui/kinds/grid/`, and the shell never names Grid.
- **Data.** The view model receives read models through the bots queries. It never reads the store
  directly. Fill and state updates arrive as Qt signals marshalled from the bot worker
  (architecture rule §6).
- **QtWidgets only.** No stylesheet; the OS theme; no fixed pixel sizes (`ui-presentation-rule.md`).

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/**` (new) | screen, MVP, coordinators, kinds/grid panel, dialogs, preview |
| `src/modules/bots/module.py` | `contribute()` the screen |
| `tests/unit/shell/test_screen_wiring.py` | `_EXPECTED_ROUTES`, `_real_modules`, `by_route` |
| `tests/unit/modules/bots/ui/**` (new) | below |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/SPEC/README.md` | the use case |
| `Docs/HLD/11_desktop_workbench.md`, `04_surfaces_and_contribution_points.md` | the new place and route |

## 5. Testing

- **`qtbot` view-model and presenter tests:** legal actions per state, verdict rendering, the
  disabled Start with its reason, dialog cancel, and coordinator fencing.
- **Preview:** a smoke test of `preview.py`.
- **Sanity:** the route scan includes `bots`.
- **Visual check:** the user opens the preview. This is listed, not claimed.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
