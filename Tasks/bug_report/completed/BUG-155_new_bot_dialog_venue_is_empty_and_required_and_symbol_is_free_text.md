# BUG-155 — New bot: the Venue list is empty yet required, and Symbol is a free-text field

- **Reported:** 2026-10-06 (the user, in chat, with two screenshots)
- **Severity:** 🟡 P2 — no bot can be created: Create bot stays disabled because no venue can be chosen
- **Status:** Fixed (2026-10-06)
- **Board:** New bot: Create bot stayed disabled with no enabled Spot venue because `BotsPresenter._on_new_bot` offered only enabled venues and the dialog required one, and Symbol was a free-text `QLineEdit`; fixed by always offering the Spot venues (enabled first, preselected, never blocking: Start and the planner already refuse a disabled venue) and by choosing the symbol in the shared `SymbolPickerOverlay` over `ISymbolCatalog` (`NewBotSymbols`, read off the UI thread).
- **Context:** [SPEC-014 Run a grid bot](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `src/modules/bots/` → New bot dialog, `ui/` layer
- **Environment:** Windows (the user's desktop). App commit, engine commit, Python version and the enabled venues not captured.

## Reproduction
1. Start the app and open the New bot dialog in the Bots mode.
2. Leave Kind on Spot Grid; open the Venue list.
3. Type a symbol (`BTCUSDT`) and a name (`asdas`).

**Expected (the user's words, translated):**
1. Venue: "the venue value cannot be entered; this value should not be required."
2. Symbol: "the symbol field should have a symbol-picker widget, like the other screens."

**Actual:**
1. The Venue list is empty. The dialog says "No Spot venue is enabled. Enable one in Tools > Options > Trading first." Create bot stays disabled with Symbol and Name filled.
2. Symbol is a plain text field with the placeholder "e.g. BTCUSDT".

**Frequency:** Not yet established (one occurrence reported). Not yet reproduced here.

## Symptom
- The user's words: "1. giá trị venue k nhập được, giá trị này ko nên bắt buộc. 2. chổ nhập symboy thì phải là có cái widget chọn symboy chứ, giông mấy màng hình khác đó".
- The dialog with the Venue list empty, Venue highlighted by the user: [`BUG-155_new_bot_venue_empty.png`](BUG-155_new_bot_venue_empty.png).
- The dialog with Symbol and Name filled and Create bot still disabled: [`BUG-155_new_bot_symbol_typed.png`](BUG-155_new_bot_symbol_typed.png).
- The dialog's own hint sends the user to Tools > Options > Trading, which in the same period fails with [BUG-154](BUG-154_tools_options_fails_on_a_deleted_trading_settings_page.md). Whether the two are related is not established.

## Root cause
- `bots_presenter.py` `_on_new_bot` passed `self._venues.enabled()` filtered to Spot, so with no venue enabled the dialog got `[]`; `new_bot_dialog.py` `_sync_create` required `venue.count() > 0`, so Create stayed disabled (the user's scenario, and the dialog's hint sent them to Options, which BUG-154 was breaking at the time). Venue was a precondition of *creating* a Draft although only Start and the planner need an enabled venue (`grid_start_preconditions.py`, `get_planner_market/handler.py` both refuse one that is not enabled).
- Symbol was a `QLineEdit` ("e.g. BTCUSDT") although the app has one shared picker, `SymbolPickerOverlay`, used by Backtest and Data Management.

## Fix
- Owner decision (chat, 2026-10-06): "Optional in dialog, resolved on create". Realised without a nullable venue: `TradingVenue.SPOT_TESTNET` is the only Spot venue, so the dialog always offers the Spot venues, enabled first (`spot_venues_enabled_first`), preselects one and never blocks on it; a venue that is not enabled is refused at Start and in the planner with their existing messages, and a hint says so. No domain, persistence or engine change. A venue-less Draft was not built: nothing could set the venue afterwards (`EditBotCommand` keeps it as created).
- Symbol is a button opening the shared `SymbolPickerOverlay`; `NewBotSymbols` reads `ISymbolCatalog` (Spot) on the thread pool and hands it over by a queued signal, favourites and recents are the shared `SymbolPreferences`. A failed read is shown in the dialog.
- `SPEC-014` §3.2 updated.

## Regression test
`test_new_bot_venues.py::test_new_bot_offers_the_spot_venue_even_when_none_is_enabled` (red before: the dialog was asked with `[]`) and `test_bots_dialogs.py` (Symbol is a picker, not a line edit; Create needs only a picked symbol; the catalog read failure is shown).

## Verification
The new tests and the bots unit and integration suites (1477 passed), the architecture guards, ruff and mypy on the touched files. Positive proof that the new path ran: the presenter test records the dialog being asked with `spot_testnet` while no venue is enabled, and the dialog tests choose a symbol through the picker's `symbol_chosen` and save the command through the real handler. Not run: the Windows desktop with real input.
