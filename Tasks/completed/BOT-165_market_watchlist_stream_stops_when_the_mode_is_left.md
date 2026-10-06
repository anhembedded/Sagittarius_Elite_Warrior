# BOT-165 — The Market mode's Watchlist stream stops when the user leaves the mode and starts again on return

**Status:** ✅ Done (2026-10-06)
**Board:** Decision (owner, via `BUG-163`): the Watchlist stream is released when Market is hidden, via a new `IHiddenAsMode` port the shell calls; only the Watchlist's own owner stops, return restarts it, a restore still starts nothing.
**Source:** The owner, 2026-10-06, approving `BUG-163`'s recommendation: "như bạn đề xuất" (as you recommend).
**Risk:** 🟡 — a new shell-to-presenter port call; a wrong owner would stop another consumer's stream.
**Complexity:** S — one port, one shell call, one presenter hook.
**SPEC:** [SPEC-002](../../Docs/SPEC/SPEC-002_watch_the_live_market.md)
**Depends on:** None

---

## 1. Context and problem
`BUG-163` found the Watchlist stream starts on the user's open of Market and keeps streaming after they leave, because nothing told the presenter it was hidden (`IShownAsMode` had only `on_mode_shown`).

## 2. Acceptance criteria
- [x] Leaving Market stops `WATCHLIST_STREAM_OWNER`.
- [x] Returning to Market starts it again on the chosen market.
- [x] Another owner's stream of the same symbol survives the leave.
- [x] A restore at start still starts nothing (`BUG-104`).

## 3. Design
`IHiddenAsMode.on_mode_hidden()` beside `IShownAsMode` (the seam `i_shown_as_mode.py` already named). `MainWindow._announce` tells the mode it replaces. `MarketPresenter` keeps `WatchlistStream.running`: hidden stops the owner, a later show restarts it, a market switch while hidden starts nothing. Only the Watchlist is released; chart streams stay as before (a tab owns its own, released on close). `IMarketStream.stop` is per owner, so no other owner is touched.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/i_shown_as_mode.py` | `IHiddenAsMode` port |
| `src/presentation/ui/main_window.py` | tell the previous mode it was hidden |
| `src/modules/trading/ui/market/market_presenter.py`, `watchlist_stream.py` | `on_mode_hidden`; the Watchlist stream (start, pause, release, filters) extracted into `WatchlistStream` to stay under the 400-line ceiling |
| `Docs/SPEC/SPEC-002_watch_the_live_market.md` | flow and proof rows |
| tests | unit `test_market_presenter_hidden.py`; integration `test_main_window_state.py`; port contract test |

## 5. Testing
Unit and integration (real `MainWindow` on the composed app, `FakeMarketStream`); mutation-checked (no stop, no restart, wrong owner, restore starts, shell never calls hidden): each killed.

## Implementation notes (written when done)
All four criteria are proven by `test_market_presenter_hidden.py` (6 tests) and two tests in `test_main_window_state.py` on the real `MainWindow` over the booted app; the existing 14 BUG-104 tests are unchanged and green. Five mutations (drop the stop, drop the restart, stop the wrong owner, start on restore, shell never calls hidden) each fail at least one test. Chart streams are deliberately untouched (out of the approved scope). GitHub Actions' `ci-local.ps1 -Full` is the full-gate evidence on the PR.
