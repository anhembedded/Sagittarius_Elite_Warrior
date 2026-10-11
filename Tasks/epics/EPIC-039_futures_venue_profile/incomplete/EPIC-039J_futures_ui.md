# EPIC-039J — The Bots screen creates a Futures bot: venues, direction, leverage, margin, and the liquidation estimate in view

**Status:** 🔵 Planned — not started
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
- [ ] The New bot venue picker lists every venue whose profile the **chosen kind supports**; Futures **mainnet** is listed only after the owner opens it (O7, 039L) — a profile-level `offered` flag read from configuration, default off for `FUTURES_MAINNET`.
- [ ] The Grid panel shows, **driven by the profile** (no `market_type` in the widget): *Direction* (only the profile's directions), *Leverage* (Futures only), *Margin mode* (read-only "Isolated" in this epic), *On range exit* (`hold`/`close`), and a read-only **Liquidation** row: the estimate per edge (Neutral shows two), always the word "estimate", with the distance to the stop loss and the verdict colour from the guard's verdicts — never colour alone (`ui-presentation-rule.md`).
- [ ] The existing Verdicts list shows the Futures verdicts of 039F/039E/039G with their codes and plain-language words, in the same widget as Spot's.
- [ ] Reuse: the leverage and margin controls and the estimate wording come from the Futures desk's widgets or a shared support widget (`support/ui_kit`) — no second implementation; the task names what was reused.
- [ ] The chart and the tick feed use the **bot's venue market** (profile), not `SPOT`; a Futures bot's chart shows Futures candles and its stop/take-profit/liquidation lines (overlay lines for liquidation added through `BotOverlay`).
- [ ] Wording: where a sentence said "Spot venue" it says the profile's `title_word`; Spot sentences are byte-identical (039A's golden strings).
- [ ] The bot's row and Plan show *what stands on the exchange*: position, mark, liquidation (exchange-reported) and the protective stop (once 039L exists), via the same read model the rest of the screen uses — no widget calls the exchange.
- [ ] Every new state has a `preview.py` frame (`test_every_presenter_package_has_a_preview.py` rule): Futures Long/Short/Neutral plan, a refused plan, a liquidation warning, a drift halt.
- [ ] Background work (reads of brackets, mark, settings) goes through the async-action coordinator (`async-ui-action-rule.md`: fencing, cooperative cancellation); a stale read never overwrites a newer one.
- [ ] Spot screens and their tests unchanged.

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
Not started.

## Resume
Not started. First action: list every `Spot`/`SPOT` string and `MarketType` use under `src/modules/bots/ui` and tick them off against 039A's list.
