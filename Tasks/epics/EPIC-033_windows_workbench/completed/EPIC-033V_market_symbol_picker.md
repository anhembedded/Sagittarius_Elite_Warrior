# EPIC-033V — The Market mode lets the person choose a symbol and keep a Watchlist of their own

**Status:** ✅ Done (2026-10-20)
**Source:** The owner, 2026-10-20, from the desktop app on Windows: *"the Market screen has no symbol picker, fix it; it seems a design gap: if it is missing it must exist"*.
**Risk:** 🟢 — read-only market data; a new choice of which public symbol to chart and stream, remembered like the market choice.
**Complexity:** M — one catalog read off the UI thread, a remembered Watchlist, three commands, the shared picker.
**Epic (optional):** [EPIC-033](../README.md)
**SPEC (optional):** [SPEC-002](../../../../Docs/SPEC/SPEC-002_watch_the_live_market.md)
**Depends on:** EPIC-033H, EPIC-033Q (done)

---

## 1. Context and problem
Checked at `01d188a`. It is a design gap, not a lost feature: HLD §11.2.1 gives the Market mode "chart, one tab per open symbol" and a Watchlist, and `EPIC-033H`'s criterion was "picking a symbol *in the Watchlist* drives the chart". The Watchlist's symbols come from `DEFAULT_SYMBOLS` in Settings (`market_dependencies.py`, `default_symbol_options`), with the floor `BTCUSDT, ETHUSDT, BNBUSDT`; the empty-state text said "Choose them in Tools → Options". Nothing in the mode names a symbol the person types or searches for. The only symbol choice in the old Dev Board (a combo, `EPIC-033P` row for `test_dev_board_known_gaps.py`: "its symbol combo … (c)") was dropped with it; the shared `SymbolPickerOverlay` was never wired here, while Backtest, New bot and Data use it. The repository is a shallow clone, so the Dev Board's own history is not readable here; the HLD, `EPIC-033H`/`P`/`Q` and the code are the evidence.

## 2. Acceptance criteria
- [x] View → Symbol… (Ctrl+L, on the toolbar) opens the shared symbol picker over the chosen market's symbols; choosing one opens its chart tab, or brings it forward if open.
- [x] View → Add to Watchlist… (toolbar) opens the same picker; choosing a symbol adds a row, streams it when the mode is live, and remembers it. A symbol already tracked is not added twice.
- [x] View → Remove from Watchlist removes the selected row, stops streaming it and remembers it; it is off while no row is selected. An open chart of the symbol stays open.
- [x] The Watchlist is remembered across restarts; with nothing remembered it starts from the configured symbols.
- [x] The picker lists the symbols of the market View → Spot market / Futures market chose, read once per market through `ISymbolCatalog` off the UI thread (never per keystroke); a failed read says so and the next open asks again. Favourites and recents are the app-wide `SymbolPreferences`.
- [x] Double-click or Enter on a Watchlist row opens its chart (or brings it forward), as before.
- [x] Every command is a View menu action with an access key, reachable by keyboard; the conformance suite and the access-key guards pass.

## 3. Design
Three commands in the Market mode's View menu, one `QAction` each (`ui-presentation-rule.md` §3): `Symbol…` (Ctrl+L: the Engine's shortcut policy refuses Ctrl+K, and a mode's menus hold only its own commands, so Data's Sync history may share Ctrl+L), `Add to Watchlist…` and `Remove from Watchlist`. Two small objects, as the mode already splits `MarketChoice` and `ChartHistoryCommands` out of the presenter:
- `WatchlistSymbols` holds the tracked list, adds and removes, and remembers it as an `IStateContributor` (scope `market_watchlist`), exactly as `MarketChoice` remembers the market.
- `MarketSymbolPicker` reads the catalog of the chosen market once, on the thread pool, and hands it to a `SymbolPickerOverlay` built for each opening; what a choice means (open a chart, or add a row) is the callback the opening passes.

The Watchlist stays one list for both markets (`EPIC-033Q`'s recorded choice); the picker offers the chosen market's symbols, so a symbol added on Futures that Spot lacks is the exchange's refusal on the Spot stream, as for a configured symbol today.

## 3a. Reuse
`SymbolPickerOverlay`, `SymbolPreferences`, `find_symbol_preferences` (`capabilities.md`, "Choose a trading pair"): used. `ISymbolCatalog`: used (the Bots dialog's read pattern, `new_bot_symbols.py`, followed; its class is Bots' own and is not imported across modules). `MarketChoice`'s remembered-state shape: used. `SpecTable.selected_row`: used.

Also: the catalog read New bot already had moved to the shared `SymbolListReader` (`support/ui_kit/symbol_picker/`), used by New bot and the Market mode, because a second copy raised the presenter-duplication guard.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/market/watchlist_symbols.py` | new: the tracked list, remembered |
| `src/modules/trading/ui/market/market_symbol_picker.py` | new: catalog read and the overlay per opening |
| `src/modules/trading/ui/market/symbol_commands.py` | new: the three commands' performer |
| `market_commands.py`, `market_presenter.py`, `market_view.py`, `watchlist_stream.py`, `market_dependencies.py` | the commands, the Watchlist read from `WatchlistSymbols`, the selection, the catalog and preferences |
| `Docs/HLD/11_desktop_workbench.md`, `Docs/SPEC/SPEC-002_watch_the_live_market.md` | the View rows; the flow and proof rows |

## 5. Testing
Unit (offscreen): `WatchlistSymbols` add/remove/dedupe/remember; the picker's single catalog read per market, its failure and retry; the commands' enabled state; choosing opens or focuses a chart; adding streams the new symbol when live. Integration: the booted Market mode with the real commands. Mutation-checked.

## 6. Docs touched
HLD §11.2.3 (View rows); SPEC-002 (surfaces, §4, §8); no `Docs/MODULES/trading` change if the folder does not describe the Market mode.

## Implementation notes (written when done)
- Commit tier PASS; unit Market/Bots/support/architecture and Market integration green locally; four mutations (stream restart, dedupe, remove, retry after failure) each turn tests red.
- Ctrl+L, not Ctrl+K: the Engine refuses Ctrl+K at build time. The booted conformance suite is the gate's to confirm.
- Not built: a Watchlist context menu, a per-market Watchlist.
