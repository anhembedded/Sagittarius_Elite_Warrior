# BUG-261 — The Plan group of a bot whose design is not saved shows "—" for capital, step, edges and exits

- **Reported:** 2026-10-21 (the owner, Bots > Live, via the coordinator session)
- **Severity:** 🟢 P3 — the checks and the chart already used the design on screen while the Plan figures beside them read "—"
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** The Plan's figures read the saved config while the checks and the chart judged the edited one; the figures now come from the design on screen, under the heading "Plan (not saved)".
- **Context:** Bots tab → `src/modules/bots/ui/bots_screen/` (`bot_detail.py`, `bot_facts.py`, `plan_property_rows.py`)
- **Environment:** master-warrior at `68e1227`. Reproduced at the unit tier and in a preview frame.

## Reproduction
Create a Grid, design it in the Plan's editor without saving. Expected: the Plan group shows capital, step, profit per cycle, edges and exits. Actual: only Venue and Symbol; the rest "—".

## Symptom
The Plan group listed Venue and Symbol and dashes, while "Ready to start" and the checks already judged the design.

## Root cause
`detail_for` (`bot_detail.py:135`, at `68e1227`) judged `config = inputs.edited or bot.config` but built the figures from the saved bot: `bot_facts(bot, …)` reads `bot.config` for the capital (`bot_facts.py:151`) and `grid_ladder_of(bot, …)` the saved parameters for the step, the profit per cycle, the edges and the exits. A bot not yet saved with its design has none, hence "—". The gate was green because no test held the figures to the edited parameters.

## Fix
`detail_for` builds the figures from the bot with the edited config (`shown`) and marks them (`BotFacts.unsaved`); the panel's group heading reads "Plan (not saved)" (`PlanPropertyGrid.set_group_title`); the row "Saved grid step" is now "Grid step, top to bottom", since it may be a draft's. The Backtest tab shares `PlanColumn` but not this table: it shows its own sandbox figures from the edited parameters and is unchanged.

## Regression test
`tests/unit/modules/bots/ui/bots_screen/test_the_plan_group_shows_the_draft_not_the_saved_config.py` (red before: capital "—") and `test_plan_property_grid.py` (heading). Frames, light and dark (a dark Fusion palette stands in for the Windows scheme on the offscreen platform): `images/BUG-261-plan-not-saved-light.png`, `images/BUG-261-plan-not-saved-dark.png`, rendered from `plan_dock_frames.py` → frame `unsaved_design`.

## Verification
Commit tier and `tests/unit/modules/bots/ui` green locally; the frames show Capital 2000, step 0.93% to 1.14%, edges, exits and "Plan (not saved)". Not run on Windows.
