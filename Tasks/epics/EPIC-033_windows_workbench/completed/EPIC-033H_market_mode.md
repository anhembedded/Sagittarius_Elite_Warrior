# EPIC-033H — Market mode: watch the market, laid out as HLD §11.2.1 designs it

**Status:** ✅ Done (2026-10-05)
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🟢 — read-only data
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**SPEC:** [SPEC-002](../../../../Docs/SPEC/SPEC-002_watch_the_live_market.md), [SPEC-003](../../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md)
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Watching the market is spread over three screens today: Watchlist (a page with one table), the Dev Board chart, and the order-book widget, none of which can sit beside the others.

## 2. Acceptance criteria
- [x] The central widget and default docks are exactly those HLD §11.2.1 lists for this mode (the one list; this task does not copy it). Picking a symbol in the Watchlist drives the chart.
- [x] Connection state shows in the status bar in text; Tools → Check Connection runs SPEC-003.
- [x] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [x] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the Watchlist screen and the market half of Dev Board. The Dev Board's half is deleted with the Dev Board itself, by `EPIC-033P` (its acceptance criteria name it): the board turns into the Developer mode there, and removing its chart here would leave it a half-screen for one pull request.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Implementation notes (written when done)
- **Where it lives: `trading/ui/market/`, not `market_data/ui/`.** Tools → Check connection asks `trading`'s `IAccountSnapshot`, and `market_data` may not depend on `trading` (`trading` already depends on `market_data`; a module's declared dependencies are checked by `test_module_declarations.py`). Everything the mode reads of `market_data` goes through its contracts (`IMarketStream`, `MarketDataCandleFeed`) and `market_ticks.py`'s one Feed crossing. HLD §11.3's row for the indicator checklist says so.
- **The mode (`market_screen.py`, Ctrl+1).** Item sequence 5, ahead of the Dev Board's 10. The view (`market_view.py`) is a `WorkbenchSurface` on the new `market` surface (`shell/surfaces.py`): the charts in a `QTabWidget` as the central widget, an instruction while none is open; the Watchlist (a `SpecTable` over the moved `WatchlistTableModel`) and the Indicators (a checkable `QListWidget`) tabbed on the right, the Watchlist in front; the window's one Output pane shows the mode's `Market` channel.
- **A chart tab (`market_chart.py`).** `MarketChart` is a `LiveCandleChart` (ADR D15) with its own stream owner, `market.<symbol>`, and its own `IndicatorScriptRunner`: the checked scripts are replayed over the history it drew and fed each closed candle. The presenter forwards each tick of the mode's market (Spot, as the Watchlist always watched) to the chart of its symbol.
- **Going live (`BUG-104`, `BUG-107`).** The first showing opens the first tracked symbol's chart from local history; only the user's own open starts the Watchlist's stream (`market.watchlist`) and puts the charts live; a chart opened afterwards goes live as it opens; closing a tab releases its stream. A refused start says so in the status bar and the Output channel (SPEC-002 §4/§5).
- **The status bar (`IStatusSource`, new seam in `support/ui_kit/status_source.py`).** A view may offer widgets for the window's status bar; `MainWindow` adds each once, for every mode, after the venue — the shape `IOutputSource` gave the Output pane. The Market view offers two words: `Exchange: …` and `Market data: …`.
- **Tools → Check connection (SPEC-003).** Bound by the Market presenter, for every mode (`mode=None`). The check runs on the thread pool under an `ActionOwnershipTracker` id; only the newest check writes; the command is disabled while one runs. The answer is a word in the status bar (`connection_words.py`); a failure also names what to do in a message box, one line per `ConnectionFailureKind`, and the full report stays on Tools → Options → Trading. Its `&C` took the key of Backtest's interim "Compare reports…", now "Com&pare reports…".
- **File → Close chart (`QKeySequence.Close`).** The keyboard's way to a tab's close button (`ui-presentation-rule.md` §11), scoped to the mode, off while no chart is open; added to HLD §11.2.3's table.
- **`ChartCard` is a stock widget (`chart_frame.py`).** The conformance suite found the one style sheet in the mode: `ChartCard` was a `Card` of the old kit, styled by `apply_role`. It now sits on `ChartFrame(QWidget)`, which keeps `title`, `header_actions` and `body_layout`, so no caller changed; every chart (desks, bots, backtest, Dev Board) lost its styled frame with it.
- **Retired:** the Watchlist screen (`market_data/ui/watchlist/`: screen, view, presenter, preview, and their tests); its conformance baseline row; its `PLC0415` debt (3).
- **Verification:** commit tier PASS; unit 8,514 passed; integration 306 passed + the output-pane test updated for the new channel; conformance passes with no `market` row; mutation-checked (the stale-check fence, the restore-waits rule, the tick forwarding, the indicator fan-out, the tab's stream release, the status-bar wiring each turn a test red).
- **Still open, recorded rather than built:** the connection word has no icon beside it (HLD §11.2.2 says "a word plus an icon"); the mode watches Spot only; open tabs and checked indicators are not remembered across a restart; a script's parameters are edited on the Dev Board's dialog until `EPIC-033P` moves it.
