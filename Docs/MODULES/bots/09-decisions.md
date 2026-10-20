Status: Current

# `bots` — 9. Decisions

*Which decisions shaped the module?* An index: each record is read where it lives, never copied here.

| Record | What it decided |
| :--- | :--- |
| [ADR 029 of 2026-10-03](../../../Tasks/epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-03_bots_module_and_grid_bot.md) | Bots are their own module and entity with a declared lifecycle; the Grid on Spot first; `trading` executes under an owner budget derived from exchange evidence. §3 holds the lifecycle, the level lifecycle, reconciliation and sliced market orders |
| [ADR 035 of 2026-10-08](../../../Tasks/epics/EPIC-035_spot_grid_unattended_safety/DECISION_2026-10-08_spot_grid_audit_owner_decisions.md) | The Spot Grid audit acted on in four phases; Phase 1 (`035A` the bot owns its price stream, `035B` the user-data stream heals and catches up, `035C` no unmanaged orders and no stuck states) gates unattended mainnet |
| [ADR 038 of 2026-10-09](../../../Tasks/epics/EPIC-038_headless_operation/DECISION_2026-10-09_headless_operation.md) and [design 038](../../../Tasks/epics/EPIC-038_headless_operation/DESIGN_2026-10-09_headless_operation.md) | Headless operation is a `run` host, a status read model and machine-readable output; what stopping does to resting orders (O1) and resuming after a restart (O2) |
| [ADR 039 of 2026-10-10](../../../Tasks/epics/EPIC-039_futures_venue_profile/DECISION_2026-10-10_futures_venue_profile.md) and [design 039](../../../Tasks/epics/EPIC-039_futures_venue_profile/DESIGN_2026-10-10_futures_venue_profile.md) | Futures is a venue profile every bot kind shares; the Futures Grid is its first user; §8 is the protective stop `EPIC-039L` builds |
| [ADR 039L of 2026-10-16](../../../Tasks/epics/EPIC-039_futures_venue_profile/DECISION_2026-10-16_futures_protective_stop_minimum.md) | The protective stop is built by `EPIC-039L` itself (no 026K code exists): a `closePosition` order on mark price, saved before it is sent, cancelled only after flat; the restart table, the halt policy and the mainnet gate; what Binance's pages did not say |
| [ADR 042 of 2026-10-17](../../../Tasks/epics/EPIC-042_halt_auto_recovery/DECISION_2026-10-17_halt_auto_recovery.md) | A halt a kind names transient waits in its own state, `AWAITING_RECOVERY`, and recovers through the person's Resume path after a continuous dwell, three times per rolling 24 h, recorded in the bot record; `run --resume-halted` for the host. Spot Grid `price_feed_stale` and `user_stream_down`; Futures declares nothing but the exchange's pause, which `EPIC-042F` moved onto the mechanism |
| [EPIC-041, 2026-10-16](../../../Tasks/epics/EPIC-041_documentation_standard/DECISION_2026-10-16_module_docs_one_folder_arc42.md) | This folder's layout |
| [EPIC-041, 2026-10-16](../../../Tasks/epics/EPIC-041_documentation_standard/DECISION_2026-10-16_cite_code_by_symbol.md) | This folder cites code by path and symbol, never by line |
