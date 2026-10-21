# EPIC-043E — B5 + B6: risk tones and Lucide icons

**Status:** ✅ Done (2026-10-21; pull request open) — partly: the live risk level and command icons are filed as `BOT-215` and `BOT-216`, for the reasons in §3
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟡 — a UI change that must not reintroduce a style layer; the three guards hold it
**Complexity:** M — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** 043D (merged, #659)

---

## 1. Context and problem
PRO-009 B5 says the liquidation read-out and the risk watch's SAFE / WARN / CRITICAL "use a warning tone that already has a word beside it"; B6 says commands and states get SVG icons from the Lucide set under `src/support/ui_kit/assets/icons/`. Reading the code at `137fe0a6` shows two premises that do not hold: the risk watch's level reaches no screen, and a toolbar command with an icon loses its text.

## 2. Acceptance criteria
- [x] SAFE, WARN and CRITICAL each carry a word and a tone from the meaning table; the liquidation read-out is toned the same way. **Partly.** The liquidation read-out (the Grid editor's "Liquidation (est.)" row, the only liquidation text on a screen) is toned per side from the guard's own severity, with its words (`Blocks Start:`, `Advice:`) unchanged. SAFE / WARN / CRITICAL themselves are on no screen, so there is nothing to tone: showing them is `BOT-215`.
- [x] Every new icon is an SVG from the Lucide set; no emoji; icon-only actions keep a tooltip naming the shortcut. No new file was needed: the states below use `zap`, `circle-check-big`, `circle-x` from the set. No action became icon-only. Command icons are `BOT-216`.
- [x] A before/after preview frame for each touched screen; the epic's success criteria (README §2) are all measured. See §5 and the epic README's measured table.

## 3. Design
**What is toned (B5).** `LiquidationReadout` (`bots/ui/kinds/grid/`) is one label per side, each in `verdict_tone(severity)`: refused → loss, warned → caution, passed → none. A Neutral plan shows a Long and a Short line, and they can differ, so one tone over both would paint the fine side as the refused one. `verdict_tone` (`bots/ui/verdict_tone.py`) is the one severity → tone map; the Plan checks list, which had its own copy from 043C, uses it.

**What is not built, and why (B5, B6).**
- **The live risk level (`BOT-215`).** `RiskLevel` is published once per change (`BotRiskChangedEvent`) and kept nowhere, and a bot that stays SAFE never announces it. A UI fed by the event would be empty when opened, and "SAFE" or an absent row would be a claim the application cannot back (`domain-truth-rule.md`). A current-level read model in the running-bot domain, a real-money path, is a task of its own with its own reviewer pass.
- **The headline's "Nearest liquidation" tone.** Its thresholds are the bots guard's; the trading UI may not import them. The figure stays plain; `BOT-215` can give it the guard's verdict.
- **Command icons (`BOT-216`).** The Engine's toolbars draw an action with an icon as the icon alone (`workbench_shell`, `action_registry`), so an icon on "Check gaps" would hide its words. Text beside icon is an Engine decision (`ONBOARDING.md` §2).

**What B6 delivers: states.** The leftovers 043C recorded: the Strategies table's "Armed" state is a word with a `zap` icon and the profit tone (`ARMED_LOOK`); an Options → Trading venue's state is a `StateBadge` (a check and the profit tone for "Connected", a cross and the loss tone for an "Error: …", the words alone for "No key" or "Not checked yet"); the K-line inspector's Change cell is a `signed_key` column (`▲ +1.00%`) so its direction is in words, and a candle that closed where it opened has no colour (it was painted green by "the colour has to pick one", a claim the text beside it did not make: the same zero rule as the Watchlist, owner may veto). The inspector's candle colours stay the chart theme's constants, a documented decision, not a raw value of its own.

## 3a. Reuse
`StateBadge`, `StateLook`, `tone_icon`, `paint_label_tone`, `RowTableModel._tone`/`_role_data`, `signed_key`, `meaning_colours`, `verdict_tone` (new, the shared map), `plain_label`: used. No catalogue row for a new mechanism: `LiquidationReadout` and `verdict_tone` are bots-module helpers.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `modules/bots/ui/verdict_tone.py` | new: severity → tone, one map |
| `modules/bots/ui/bots_screen/plan_checks_view.py` | uses it (its private copy gone) |
| `modules/bots/ui/kinds/grid/liquidation_readout.py`, `grid_exposure_fields.py` | one toned label per side |
| `modules/bots/ui/strategies/strategy_rows.py` | `ARMED_LOOK`, icon and tone on the armed state |
| `modules/trading/ui/settings/trading_settings_view.py` | a venue's state is a `StateBadge` |
| `modules/market_data/ui/kline_inspector_table_model.py` | `change.signed`; no colour for no direction |
| `Tasks/backlog/BOT-215_…`, `BOT-216_…` | the two follow-ups |

## 5. Testing
New: `test_liquidation_readout.py` (per-side tones, the real planner's refused and warned plans, the severity map), `test_strategy_state_look.py`, state-badge cases in `test_trading_settings_page.py`, signed-change and flat-candle cases in `test_kline_inspector_table_model.py`. Mutation (testing-rule), each turns a test red and was restored: one tone for both sides, no tone painted, the editor's wiring, warning = loss, the Armed tone and icon, the Connected and Error looks, the zero rule and the signed key of the inspector.
Not run: Windows High Contrast on a real host; the glyphs in the platform's fixed-pitch font.

## 6. Docs touched
`.claude/rules/ui-presentation-rule.md` §1 (the state clause now names the Strategies and Options states), the epic README and TRACKING, `Tasks/epics/README.md`. `Docs/MODULES/bots/` has no change to a shape or a boundary: nothing here moves a component, a port or a thread.

## Implementation notes
Delivery: `claude/epic-043e-risk-tones-and-icons`, from master after `043D`; a reviewer session reads it; the owner merges. The scoping was told to the delivery coordinator before the code (the live risk row was first the default and was dropped after reading the watch: the level is not kept anywhere).
