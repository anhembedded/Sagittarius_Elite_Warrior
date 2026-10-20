# BOT-208 — The owner-budget open-order cap is 150, not 100

**Status:** ✅ Done (2026-10-20)
**Board:** ADR O1's `max_open_orders` cap rises from 100 to 150 (owner decision; Binance Spot allows about 200 resting orders per symbol, so 150 leaves room for exits and protective stops); the rate (60 a minute) and spacing (250 ms) are unchanged. See [the O1 revision](epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-03_bots_module_and_grid_bot.md).
**Source:** the owner, 2026-10-20: "nâng lên 150" (raise it to 150), asked by the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu) whether to keep 100 or raise it to 150.
**Risk:** 🟡 — a configuration value that bounds how many orders a bot may keep open; a larger ladder now passes the Design check and trading's registration.
**Complexity:** S — two values, one test updated, one added, two documents.
**Epic (optional):** [EPIC-029](../epics/EPIC-029_bots_tab_grid_fast_track/README.md)
**Depends on:** None

---

## 1. Context and problem
ADR O1 (2026-10-03) set the global caps on an owner budget at 100 open orders, 250 ms and 60 orders a minute, as `trading.bot_limits.*` keys in `src/config/app_config.json` with the same figures in `DEFAULT_OWNER_BUDGET_CAPS`. The owner asked to raise the open-order cap.

## 2. Acceptance criteria
- [x] `trading.bot_limits.max_open_orders` is 150 in `src/config/app_config.json` and `DEFAULT_OWNER_BUDGET_CAPS.max_open_orders` is 150.
- [x] A grid of 140 levels passes the Design check (`grid_budget_problem`); 160 is refused, naming `max_open_orders` and the cap.
- [x] `max_orders_per_minute` (60) and `min_order_spacing` (250 ms) are unchanged.
- [x] ADR O1 carries a dated revision citing the owner's words; the bots quality table states 150.

## 3. Design
Only the two figures change. The readers take the cap from configuration (`adapter_bindings._build_owner_budget_caps`), so the Design step (`grid_budget_problem`), trading's registration (`OwnerBudgetCaps.exceeded_by`) and the grid's `ExchangeTerms` follow without code. The `max_open_orders=100` in preview and sample-replay fixtures is a venue-terms figure for sample data, not this cap, and stays.

## 4. Implementation notes
- Tests: `test_a_budget_above_a_global_cap_is_refused_naming_it` now overshoots with 151; `test_a_ladder_of_140_levels_passes_the_design_check_and_160_is_refused` is new.
- Docs: ADR O1 revision line; `Docs/MODULES/bots/10-quality.md` default caps row. Earlier completed task records that state 100 are point-in-time and stay as written.
- No design change to `Docs/MODULES/trading/`: it does not draw the figure.
