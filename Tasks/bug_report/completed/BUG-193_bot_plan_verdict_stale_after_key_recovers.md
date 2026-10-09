# BUG-193 — The bot's Plan and Save do not follow the screen: a stale "no Spot credentials" verdict after the key recovers, and a Save that keeps the old Grids

- **Reported:** 2026-10-09 (the owner, in chat, with a screenshot and the app log)
- **Severity:** 🟡 P2 — Start stays blocked for a valid key, the text sends the owner to check permissions that are fine, and a Save says "done" over parameters it did not store
- **Status:** ✅ Fixed (2026-10-09)
- **Board:** Cause 1: the planner's numbers were read once per selection, so a read made while the key was refused stayed the Plan's verdict after the header went Connected; now the first connected answer re-reads them, and a refused key is worded as the exchange's refusal (`-2015`, IP whitelist), not as a missing one. Cause 2: the Grids spin box raised no edit signal for its arrows, wheel or Up/Down, so Save stored the old count and the chart and verdict never moved; now every way of setting it is an edit and Save reads the editor at the click.
- **Context:** SPEC-014 (run a grid bot) → `src/modules/bots/` (Plan readiness, Bots screen) and `src/modules/trading/` (mainnet key gate, Spot commission reader)
- **Environment:** Linux (Wayland), the owner's desktop, master-warrior around `ed9bf34`, Spot Mainnet key in the OS keyring, IP whitelist `103.199.56.160`.

## Reproduction
**Symptom 1 — key recovered, verdict stale.**
1. Bot `Test_Real_Cash` (`vce9z8`) on Spot Mainnet; the key works (10:05:08 open orders and prices read).
2. On Binance, edit the key's IP restriction; for a short time the exchange refuses the key (`-2015`).
3. During that window, select the bot / press Save bot (10:07:09): the planner's numbers are read and fail.
4. The refusal ends; the header turns to "Spot Mainnet: Connected · 35.77 USDT available · key can trade".

Expected: the Plan is judged again and Start is allowed. Actual: the Plan keeps "The plan cannot be judged: ETHUSDT on Spot Mainnet: ETHUSDT: no Spot credentials configured". An app restart clears it, so the state is held in memory only.

**Symptom 2 — Save does not follow the screen (added 2026-10-09, owner's real app).** Draft `Test_Real_Cash`, Grid on Spot Mainnet ETHUSDT, Lower 2381, Upper 2718, Arithmetic, Capital 35, SL price 2288, TP price 2887. Grids changed from 10 to 5, Save bot pressed. The log says "Save Test_Real_Cash: done. Saved as they are." but the chart still draws the old ladder (L3…L9, about 10 levels) and the verdict still says "A level's order is worth 3.33 after the fee, below the exchange minimum of 5; raise the capital to about 52.56 or use fewer grids" (35/10 = 3.5 less fees; with 5 grids about 7 per level, which passes). The owner reports Save is broken in general, not only around the API key.

## Symptom
Log:
```
10:07:09,125 App.Bots.Screen - Bots screen: Save Test_Real_Cash
10:07:09,475 App.TradingAdapter - Spot Mainnet connection check rejected: Binance code -2015 -> KEY_REJECTED [connection-failure]
10:07:09,483 App.Shell.Notifier - Background failure, shown in the 'bots' message bar: bots.connect.spot_mainnet
```
Screenshot (owner, after the IP was confirmed `103.199.56.160`): the header reads Connected / key can trade; the Plan pane and the left Bots note read "no Spot credentials configured".

## Root cause
Three mechanisms, one per layer they live in.

1. **The planner is read once, and nothing reads it again** (`bots_presenter.py` `_select`: `self._queries.planner(bot)` is the only automatic call). The Connect step re-reads the account every minute and tells the screen (`connect_step.py` `_on_timer` → `changed`), so the header recovers; `ConnectEffects._apply` refreshed the detail but the detail judged the *cached* `SelectedBot.market`, which carried the `problem` text of the read made during the refusal. The family: any planner read that failed (key refused, exchange down) stayed the verdict until a restart or another selection.
2. **The Grids spin box was an edit only by typing.** `grid_panel.py` connected `grid_count.lineEdit().textEdited` and `editingFinished`. The spin box's arrows, the mouse wheel and Up/Down change the value through `stepBy` and raise `valueChanged` only, so `config_changed` never fired, `SelectedBot.edited` stayed `None`, and `command_for(SAVE)` sent `dict(edited or bot.config)`: the stored 10 grids, reported as "done". The chart and the verdict judge the same cache, so they never moved. (Which gesture the owner used is not recorded; typing worked, the other three did not.) This is the real cause of "Save is broken": Save and Start trusted a cache fed by per-widget signals instead of what the editor shows.
3. **The refusal reason was dropped on the way to the reader** (`key_gated_credentials.py` `resolve`): the key gate returned a `ConnectFailure` whose `reply` already holds `-2015 Invalid API-key, IP, or permissions … IP whitelist …`, and the provider turned it into `ResolvedCredentials(None, NONE)`, indistinguishable from "no key". `SpotCommissionRateReader` (`spot_commission_rate_reader.py`), its Futures twin and `FuturesAccountControl` then said "no … credentials configured" (truthful-UI rule).

No existing net covered any of the three: the tests that edit the Grid panel emit `textEdited` by hand after `setText` (the one signal that did work), and the connect-step tests stop at the header.

## Fix
- `grid_panel.py`: the count's edit signal is `valueChanged` (it hears typing, arrows, wheel and keys); `set_config` blocks it so showing a bot is still not an edit.
- `selected_bot.py` `read_editor`, called by `BotsPresenter._on_action` before the command is built: Save and Start send what the editor shows at the click, so a widget that misses a signal, now or in another kind's editor, cannot save old values.
- `planner_recovery.py` (new, 60 lines) subscribed to the Connect step: the first connected answer while the selected bot's market has a `problem` reads the planner again. One INFO line per distinct problem (`[plan-rejudge]`: the bot, the problem), DEBUG while it stands, at most one read a minute (the Connect refresh).
- `ResolvedCredentials.refusal` + `absence(market)` (`i_exchange_credentials_provider.py`), set by `KeyGatedCredentials` from the gate's own words; the Spot and Futures commission readers and `FuturesAccountControl` word a refused key as "the Spot key cannot be used: -2015 Invalid API-key, IP, or permissions … IP whitelist …", and a missing one as before.

Not changed, same family, listed for a follow-up: `history_reads.require_credentials`, the two `_resolve_client` messages and the user-data-stream log lines still say "no … credentials configured" for a refused mainnet key. A planner read that *raised* (as opposed to answering a problem) still waits for its message bar's Retry.

## Regression test
- `tests/unit/modules/bots/ui/bots_screen/test_bots_plan_is_rejudged.py` (the real Bots presenter, view, store, use cases and queries over `open_screen`; the real Grid panel driven by `QTest` key events; only the venue's ports are fakes):
  - `test_grids_stepped_with_the_arrows_are_judged_and_drawn_at_once` — red before: the verdict kept "below the exchange minimum" after the Down keys; green: 5 ladder levels drawn.
  - `test_save_stores_the_grids_on_screen_and_judges_what_it_stored` — red before: `AssertionError: '10' == '5'` (the stored bot kept 10 grids after Save said "done"); green after.
  - `test_save_stores_what_the_editor_shows_even_when_a_widget_said_nothing` — Save with a silent widget change; red with `read_editor` removed.
  - `test_a_recovered_connection_judges_the_plan_again_without_a_user_action` — red before: the readiness still read "The plan cannot be judged: … no terms seeded" after the connection answered again; green after, and the `[plan-rejudge]` INFO line is asserted.
- `tests/unit/modules/bots/ui/kinds/test_grid_panel.py::test_every_way_of_setting_the_grid_count_is_an_edit` — arrow key, `stepBy`, typing.
- `tests/unit/modules/trading/adapters/binance/test_commission_rate_readers.py::test_a_key_the_exchange_refused_is_not_reported_as_missing` (Spot, Futures, account control) and `::test_a_key_that_is_missing_still_says_so`; `mainnet/test_key_gated_credentials.py::test_a_key_the_exchange_refused_resolves_with_the_exchange_s_reason`.
- Mutation check: reverting `grid_panel.py` reddens the arrows test and the panel test; removing the `read_editor` call reddens the silent-widget test; removing the `PlannerRecovery` construction reddens the recovery test.

## Verification
- `tests/unit/modules/bots`, `tests/unit/modules/trading/adapters/binance` and `tests/unit/support/binance_gateway` green locally; the commit tier (`ci-local.ps1 -SkipTests`) and `tests/unit/architecture` green on the fix commit. The `-Full` run is GitHub Actions'.
- Positive proof the new mechanisms ran: the recovery test captures the `[plan-rejudge]` INFO line from `App.Bots.Screen` and the planner's second read; the Save test reads the stored bot back from the store (`grid_count == "5"`).
- Not verified: the owner's real mainnet key and gesture. No order was placed, tested or simulated on any exchange.
