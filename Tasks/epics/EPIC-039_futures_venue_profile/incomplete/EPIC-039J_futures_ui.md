# EPIC-039J — The Bots screen creates a Futures bot: venues, direction, leverage, margin, and the liquidation estimate in view

**Status:** 🟡 In progress (implemented but for the items the notes name; waits for the -Full run and review)
**Source:** the owner, 2026-10-10; [DESIGN §10](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🟡 — a screen that lets a user choose leverage; the words must be truthful and the previews must show the states
**Complexity:** M — conditional fields from the profile, a venue picker, chart and tick feed by profile, previews
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (the New bot and Plan journeys).
**Design:** [DESIGN §3, §10](../DESIGN_2026-10-10_futures_venue_profile.md) · **Decision:** O4, O7
**Depends on:** [039A](EPIC-039A_venue_profile_seam.md), [039E](EPIC-039E_futures_settings_gate_and_readiness.md), [039F](EPIC-039F_risk_guard_and_liquidation.md). Its Futures creation path needs [039H](EPIC-039H_futures_grid_long.md) to exist.

---

## 1. Context and problem
The Bots screen is QtWidgets (`ui-presentation-rule.md`: QtWidgets only, OS theme, desktop UX, `preview.py`). Five UI sites hard-code Spot (039A lists them); the Grid panel (`ui/kinds/grid/grid_panel.py`) has no direction, leverage or margin fields, and no place for a liquidation estimate. The manual Futures desk already has leverage and margin chips and a liquidation estimate (`trading/ui/…`; `EPIC-028I`, `028O`, `028G`) whose widgets and wording should be reused, not rebuilt (`EPIC-037`'s lesson: the bot once built its own symbol picker instead of reusing one).

### Facts verified on `master-warrior` `076d339`
- `ui/bots_screen/venue_choice.py:40-50` — the New bot picker lists only Spot venues; `bot_venues.py:64`; `bot_plan_panel.py:210,228`; `bot_commands.py:54` — Spot wording.
- `ui/bots_screen/bot_chart_host.py:80`, `bots_presenter.py:118`, `kinds/grid/backtest/grid_backtest.py:47`, `grid_backtest_presenter.py:262` — market is `MarketType.SPOT`.
- `ui/kinds/kind_panels.py`, `ui/kinds/grid/grid_panel.py:146` (`actSuggestAtr` "Suggest from ATR" and a Bollinger one), `domain/grid/grid_overlay.py` (overlay lines incl. ATR zones).
- The strategy dialog already shows or hides a leverage row by venue: `ui/strategies/arm_strategy_dialog.py:94` (`fields.setRowVisible(self.leverage, venue.market_type is not MarketType.SPOT)`) — the precedent, and a `market_type` comparison to route through the profile too (the guard of 039A covers `src/modules/bots`, which includes this file: it moves to the profile in this task if 039A left it).
- Venue connection states: `bots_screen/venue_choice.py` (`VenueChoice`, `KEY_SAVED`, `NOT_ENABLED`).
- Rules: `.claude/rules/ui-presentation-rule.md` and `pitfalls/ui.md` (Qt threading) load with these files; `Docs/HLD/11_desktop_workbench.md`.

## 2. Acceptance criteria
- [x] The New bot venue picker lists every venue whose profile the **chosen kind supports**; Futures **mainnet** is listed only after the owner opens it (O7, 039L). **Deviation:** the flag is a named set in code (`CLOSED_VENUES`, `venue_profile.py`), not a configuration key: a new `app_config.json` key is a settings change the owner approves, and 039L, which builds the gate, is the task that needs it and replaces the set. Nothing is listed on Futures until 039H raises `BOT_MARKETS`.
- [~] The Grid panel shows, **driven by the profile** (no `market_type` in the widget): *Direction*, *Leverage*, *Margin mode* (read-only "Isolated") and a read-only **Liquidation** row (an estimate per edge, Neutral two, the word "estimate", the distance to the exit, severity in words and the sign beside the field). **Not done: *On range exit*.** `GridParams` has no `on_range_exit` key and nothing consumes one, so a field would offer a choice that does nothing (`domain-truth-rule.md`); it is one more row in `ExposureFields` once 039H adds the key and the behaviour.
- [x] The existing Verdicts list shows the Futures verdicts of 039F/039E/039G with their codes and plain-language words, in the same widget as Spot's: the plan judgement now carries the venue's limits and the symbol's risk facts into `evaluate_grid`, so the same verdicts Start's evaluation returns are the ones listed (`test_a_position_venues_plan_is_judged_for_liquidation_in_the_same_list`). `FUNDING_ADVERSE` arrives through the kind's own constraints; the readiness items of 039E (`RUN_*`) keep the Run step's list.
- [x] Reuse: see "Reuse" below. The Futures desk has no leverage or margin widget in the tree to share (its order form writes the figure "Liq. price (est.)" as a read-out row); the estimate wording is the desk's, the controls are stock `QSpinBox` and `QComboBox`.
- [x] The chart and the tick feed use the **bot's venue market** (profile); the overlay draws the guard's liquidation per side (`OverlayRole.LIQUIDATION`) beside the stop and take-profit.
- [x] Wording: where a sentence said "Spot venue" in the UI it says the profile's `title_word` (the Venue field's tooltip, the kind title, the symbol-list failure, the Connect step's balance); Spot sentences are byte-identical (pinned by tests). The domain sentences of 039A (`bot.py`, `planner_numbers.py`, `bot_run_facts.py`) are true as they stand: they describe a venue that is *not* a Spot venue, and none reaches a venue bots run on.
- [~] The bot's row and Plan show *what stands on the exchange*. **Done:** the run's commissions and funding, apart from the grid profit. **Not done:** position, mark, liquidation (exchange-reported) and the protective stop: no read model carries them yet (039H builds the executor that reads `positionRisk`; 039L the stop), and a widget must not call the exchange. The row is one more `BotFacts` field when that read model exists.
- [x] Every new state has a preview frame (`preview_frames.py`): Futures Long, Short and Neutral plans, a refused plan, a liquidation warning, a drift halt. `build_preview()` stays the Spot screen.
- [x] Background work (the brackets and the account's setting) goes through the fenced read of the screen (`ReadKind.RISK`): a stale answer never overwrites a newer one (`test_a_stale_bracket_read_does_not_overwrite_a_newer_one`, red when the fence is removed).
- [x] Spot screens and their tests unchanged (no Spot expectation edited; the Spot-sentence pins are new tests that pass before and after).
- [x] The backtest's explicit "run without funding" choice (039G's hand-off, 039K merged as `41eba5d`): a Futures period whose funding cannot be read is refused first; the refusal offers "Run without funding", and only that click sends `FundingRequirement.OPTIONAL` (the result's notes then say funding is not included). Run waits for the symbol's brackets (taken from the plan-risk read), the sync and the result chart use the venue's market, and the tab is hidden for a kind/market the kind's backtest does not replay.

## 3. Design
Fields appear because the *profile* lists them (open/closed: a future margin mode or direction appears without a widget edit). Presentation reads view models only; the guard's verdicts and the exchange facts are the single source for what is shown (`domain-truth-rule.md`: a truthful UI shows an estimate as an estimate and an unread value as unknown).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `ui/bots_screen/venue_choice.py`, `bot_venues.py`, `bot_plan_panel.py`, `bot_commands.py`, `bots_presenter.py`, `bot_chart_host.py` | profile-driven |
| `ui/kinds/grid/grid_panel.py`, `kind_panels.py` | direction, leverage, margin, range-exit, liquidation row |
| `ui/kinds/grid/backtest/*` | market from the profile (backtest content is 039K) |
| `domain/bot_overlay.py`, `grid_overlay.py` | liquidation line(s) |
| `ui/**/preview.py` | frames |

## 5. Testing
Tier: unit (view models), integration (presenter with fakes), previews as the visual check (`preview.py` screenshots, owner-viewed); the Qt-free tests run offscreen.
- `test_the_picker_lists_the_venues_the_kind_supports_and_hides_futures_mainnet_until_opened`
- `test_futures_fields_appear_from_the_profile_and_not_on_spot`
- `test_the_liquidation_row_says_estimate_and_neutral_shows_two`
- `test_spot_ui_sentences_are_unchanged`
- `test_a_stale_bracket_read_does_not_overwrite_a_newer_one`
- previews for each state. Not run yet.

## Pitfalls
- Qt threading rules in `.claude/rules/pitfalls/ui.md`: reads off the UI thread, results back through the presenter's feed; do not touch widgets from a worker.
- `configure_item_view` and `IOptionsSection` conventions for any list or options widget (`ui-presentation-rule.md`).
- Do not place a `market_type` comparison in a view; if a widget needs to know, it asks the view model, which asks the profile.

## Implementation notes (written when done)
**What shipped, as five commits.** (1) The Grid editor takes the venue profile (`BotKindPanel.set_profile`, called by `SelectedBot.select`) and shows Direction, Leverage, the margin mode and the Liquidation row because the profile lists them; `ExposureFields` holds them so the panel stays under 400 lines, `ExitField` moved to its own file. A Spot profile lists none: `config()` adds no key and a Spot definition keeps its bytes. Direction and leverage start at long and 2× (O4) and are always written into a Futures definition, so a Futures bot never falls back to the legacy "long at 1" reading. (2) The pickers, symbol list, kind title, chart market and tick feed follow the venue's profile. (3) `GetPlanRiskFactsQuery` reads the symbol's brackets and setting through `IVenueFacts`; the screen asks for them as a fenced read of its own and passes the venue's limits and the facts into the plan judgement. (5) The Futures backtest after 039K merged: brackets, market and the explicit "run without funding" button. (4) Costs, the Connect step's wording, the liquidation chart line and the six preview frames.

**Reuse (A7).** Checked: `capabilities.md`; the Futures desk (`trading/ui/desk/order_entry/side_readout.py` writes "Liq. price (est.)" as a read-out row, and has no leverage or margin control to share; `bots` may not import `trading/ui`); `plain_label`, `ReadoutForm`, `write_value`, `INotifier`, the fenced reads and `ExchangeCheck` (the risk read is composed by it), `venue_profile_of` and the `BotOverlay` drawer's role table. Stock `QSpinBox`/`QComboBox` for the two fields.

**Findings the task text lacked.**
- **The screen's plan judgement had no way to know the venue.** `judge` built `BotKindInputs` without limits, so a Futures direction or leverage would have been refused as Spot's (`exposure_refusal`), and nothing gave the guard its brackets. `VenueExposure` (limits and risk facts) now rides with the judgement. The Start path (`assess_readiness`, `ReadinessInputs`) still builds its inputs without them: **039H** must pass `exposure_limits_of(venue)` and the facts when it wires readiness, or a Futures Start is refused for leverage.
- **`LIQUIDATION_ESTIMATE` could not say which side it was for.** `Verdict.subject` (default `""`) names it; the guard sets it for every side verdict and adds the exit and distance to the estimate's numbers. `FUTURES_PLAN_CODES` holds the field map to the guard's codes.
- **A new `ReadKind` needs no presenter line** when its follower subscribes to the reads itself (`PlanRiskCheck` does, like `ExchangeCheck`, which composes it): the presenter stays at 398 lines.
- **`get_exchange_facts` is still Spot-only** (`ExchangeFactsReader`, not `IVenueFacts`): a Futures bot's readiness snapshot stays "checking" until 039H binds `IVenueFacts` there. The plan-risk read does use `IVenueFacts`.
- **Both mainnet venues read the public mainnet**, so `BotTickFeed` filters on the market as well as the venue, and `listen_to` now takes the market.
- The picker's "per kind" rule is the union over the catalog today (one kind): `AskNewBot` keeps its signature so no Spot test changes; a second kind that supports fewer markets is one filter in `venue_choices`.

**Shared files touched (039H runs in parallel).** `contracts/venue_profile.py` (`CLOSED_VENUES`, `is_offered`, `title_word_of`, `is_in_markets`; `BOT_MARKETS` untouched), `domain/bot_kind_inputs.py` (`PlanRiskFacts`, `BotKindInputs.risk`, defaulted), `domain/grid/grid_evaluation.py` (the guard's verdicts when facts are given), `domain/grid/futures_grid_checks.py` (subject, numbers, `FUTURES_PLAN_CODES`), `domain/verdict.py` (`subject`, defaulted), `domain/bot_overlay.py` and `grid_overlay.py` (the liquidation role and line), `composition/query_bindings.py` (one binding), `support/charting/chart_card/theme.py` (one colour name). No executor, no `supported_profiles`.

**Verified / not.** Commit tier green; `tests/unit` and `tests/integration/modules/bots` green (13 428 tests); the architecture guards green; the fence test and the panel's Spot-bytes test turn red under their mutation. The six frames were rendered offscreen and read as images (`preview_frames.py --png`). **Not verified:** nothing ran against an exchange; the Futures facts come from fakes; no Futures venue is offered until 039H raises `BOT_MARKETS`, so the owner cannot yet open a Futures draft on the real app.

## Resume
Waits for the `-Full` run and review. Open items, each with its owner: *On range exit* (039H adds the key and the behaviour, then one row here); the exchange's position, mark, liquidation and stop on the bot's row (039H/039L read model); `assess_readiness` with the venue's limits and facts, and `IVenueFacts` in `get_exchange_facts` (039H); the mainnet gate replacing `CLOSED_VENUES` (039L, which may need a config key the owner approves).
