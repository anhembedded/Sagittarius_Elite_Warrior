# EPIC-028M — The single Trading screen is gone, the Dev Board uses the shared order panel, and the docs describe two desks

**Status:** ✅ Done (2026-10-02)
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟢 — deletion plus docs; a saved layout pointing at the old route must still open
**Complexity:** M — move the desks' dependencies out, delete two god files, rewire Dev Board F9 and its session controls, HLD/SPEC
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028K](EPIC-028K_futures_desk_screen.md), [EPIC-028L](EPIC-028L_spot_desk_screen.md), ADR O4

---

## 1. Context and problem
- `trading_view.py`, `trading_presenter.py` are on the god-file baseline; HLD 04 §4.5 and HLD 11 §11.3 say manual order is Dev Board only.

## 2. Acceptance criteria
- [x] **First, move what the desks use out of `ui/trading/`** (the PR #308 review): `TradingViewModel` (`desk_presenter.py`, `desk_view.py`, `desk_strategy.py`), `ChartCoordinator` and `StrategyOverlayCoordinator` (`ui/trading/coordinators/`). They move to the desk package or a shared trading UI address, with their tests, before anything is deleted. Deleting `ui/trading/` as it stands would break both desks.
- [x] The Dev Board's Enable/Disable and Emergency Stop move onto `DeskSessionControls` (`ui/desk/desk_screen/`). Today the Dev Board (`dashboard_presenter.py`) and the single screen each carry their own copy of that flow, beside the desks' (the PR #308 review). Only the texts are already shared (`session_outcome_text.py`).
- [x] Route `trading` and its view/presenter/view model are deleted and removed from `baseline_god_files.json`. The route's real consumer, Welcome's Start (`app_bootstrapper.py`), opens the Futures desk instead. There is no layout loader keyed by route to change: `BUG-104` deliberately does not remember the route (`main_window.py`).
- [x] The Dev Board's F9 dialog hosts the shared order-entry panel with the configured venue's profile.
- [x] HLD 04 §4.5, HLD 11 §11.2–11.3, `SPEC-004` (still single-venue: its precondition names Futures Testnet and it has no per-venue toggles; the PR #295 review's question 4), `SPEC-005`, `SPEC-012` updated; a new SPEC "See my account on a desk" lists its proving tests.
- [x] `test_spec_index_is_consistent.py`, reference checker and the full gate green.

## 3. Design
Delete, don't deprecate (no compatibility shims). The PR #300 epic review corrected the first draft, which assumed a layout loader keyed by route.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/trading/trading_view_model.py`, `coordinators/chart_coordinator.py`, `coordinators/strategy_overlay_coordinator.py` | moved first, out of `ui/trading/` (the desks use them) |
| `src/modules/trading/ui/trading/` | the rest deleted |
| `src/modules/trading/ui/dashboard/dashboard_presenter.py` | toggle and Emergency Stop through `DeskSessionControls` |
| `src/modules/trading/ui/dashboard/…` | F9 dialog on the shared panel |
| `Docs/HLD/04_*.md`, `Docs/HLD/11_*.md`, `Docs/SPEC/*` | updated / new SPEC |

## 5. Testing
- Moved with their subjects: `test_desk_view_model.py`, `test_chart_coordinator.py`, `test_strategy_overlay_coordinator.py`.
- What the deleted screen's tests proved now runs against the desk classes, mutation-checked line by line:
  - `test_desk_session_controls.py`: toggle, refusal, superseded answers, every Emergency Stop outcome, `BUG-089`, `BUG-093`, `accountReconciled`;
  - `test_desk_equity.py`: backlog, live samples, `BUG-100`;
  - `test_desk_live_feeds.py`: fills per symbol and venue, equity per venue, `BUG-084`, `BUG-085`, the market filter, the stream following a symbol picked after going live.
- Dev Board:
  - `test_dashboard_presenter.py` drives the real `DeskSessionControls` and the F9 wiring;
  - `test_dev_board_order_entry.py` places through the panel (accepted order, leased symbol in words, price by market, Futures TP/SL followed);
  - `test_dev_board_order_dialog.py` (integration, real app, trading off) checks that F9 says no venue is enabled.
- Route: `test_main_window_state.py` boots with `"trading"` or `"trading.futures"` stored and builds no trading screen; `test_screen_wiring.py` checks the six module routes.
- Guards: spec index, god-file, app-styling and presenter-duplication ratchets lowered; reference checker clean.
- Tiers on the final tree: fast gate PASS (`logs/ci-local-20261002-045419.log`, grep clean); unit + sanity 6984 passed; integration 232 passed, 4 skipped. The full gate is GitHub Actions' run on the PR head.

## Implementation notes (written when done)
- **Six commits:**
  1. move the desks' dependencies;
  2. give the desks the old screen's equity chart and fill markers, plus the replacement tests;
  3. delete the screen;
  4. move the Dev Board onto `DeskSessionControls`;
  5. put the shared order panel in the F9 dialog;
  6. docs.
- **The desks were missing two of the old screen's parts.** The ADR lists the equity chart among the shared desk parts, and the old screen marked fills on its chart. Deleting the screen without them would have removed both from the app. They moved first (`DeskEquity`, `DeskChart.record_fill`), with their regressions.
- **`TradingViewModel` became `DeskViewModel` and is now type-checked.** It had been frozen under a mypy exclude entry for its old path, and its one error (`Property("QStringList")`) is fixed. Its session counters left with the only screen that showed them. `ChartCoordinator`'s stream owner is now required.
- **The Dev Board's tables are kept from events, not re-read.** So `DeskSessionControls` gained `accountReconciled(ReconciledAccount)`, emitted with an enable's reconciled state and with a confirmed Emergency Stop's final state, never with an unconfirmed one (`BUG-093`). The desks keep re-reading on `accountChanged`. Enabling on the Dev Board still never puts its chart live.
- **F9 is `DevBoardOrderEntry`.** It holds the desks' panel for the venue the board trades (`TradingVenue`, the primary enabled venue), with that venue's profile.
  - The panel follows the board's symbol. It takes the board's price only while the board charts that venue's market (a Spot chart's price is not a Futures order's).
  - Accepted orders join the board's Open orders: the gap `EPIC-028K` found on the desks, closed for the board too. On Futures, TP/SL entries go to the follower.
  - With no venue enabled the dialog says so. The board's own manual-order card is deleted. `manual_order_intent` stays, because the desks' panel uses it.
  - `dashboard_view.py` stays under 400 lines by hosting the panel in `OrderEntryHost`, which is based on the kit `Panel` because of the bare-Qt-base guard.
- **Kept:** the `"trading"` surface in `src/shell/surfaces.py`. It declares a workbench place family, not a route, and the desks move onto it when `EPIC-025` converts the remaining `PageShell`s.
- **Not changed, needs the user (settings rule):** `pyproject.toml`'s mypy exclude list still names five `ui/trading/` paths that no longer exist (`trading_view.py`, `trading_presenter.py`, `trading_view_model.py`, `module.py`, `preview.py`). They match nothing now, and removing them is pure shrink, but editing `pyproject.toml` needs the user's approval. **Resolved 2026-10-02:** the user approved, and the five entries were removed (`mypy` still reports no issues in 930 source files).
- **Follow-up from the PR 309 review.**
  - An enable refused before the venue was read (`TRADING_VENUE_DISABLED`, `CONNECTION_NOT_READY`) hands over nothing, so the Dev Board keeps its tables. `EnableTradingResult.account_was_read` states this in the contract, and the handler's tests pin it on every path.
  - F9 reads its balances again after each of the venue's fills and when the session changed the account (an enable, an Emergency Stop), as a desk does.
  - When the board switches to the other market, F9 clears its price rather than keep an old one unmarked.
  - Comments and Settings text that named the deleted screen as if it still existed now use the past tense or name the desk class that replaced it.
