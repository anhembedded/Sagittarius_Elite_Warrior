# EPIC-035U — Exchange filters are refreshed during a run

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L5 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — a tick/step change otherwise surfaces as `-1013` and ERROR
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035E
**Board:** a bot that holds orders asks the exchange for its symbol's terms every 15 minutes and halts, naming old and new values, when tick size, step size or minimum notional changed; Start and Resume read from the exchange too, not trading's day-old catalog.

---

## 1. Context and problem
Audit L5: symbol terms are read once per executor, so a mid-run filter change surfaces as `-1013` and the bot goes to ERROR (Binance terminates its own grids in this case). Cited: `src/modules/bots/application/services/grid_run_context.py:44-55`. Verify.

**Claim re-verified on `d563c0f` (`master-warrior`, 2026-10-08): holds, with one line moved.**
- The cited `grid_run_context.py:44-55` is now `LazyExchangeTerms` (`grid_run_context.py:60`): the terms are read once on first use and kept. `EPIC-035E` added `refresh()` to it, called by `SymbolStatusGate.admits()` at each Start and Resume, so that part of the claim no longer holds: the terms *are* re-read per Start and Resume.
- But that re-read went to `IOrderEntryTerms.terms_for`, which answers from trading's symbol catalog (`SpotMetadataProvider.get_or_fetch`, cache-first, 24 h: `symbol_order_metadata.py:35`). So `refresh()` re-read a cache, not the exchange; a tick size changed two hours ago reads as the old tick size, and `035E`'s own docstring said it waits for this task. Established by reading `get_symbol_order_rules/handler.py` and `spot_metadata_provider.py`.
- A running bot never re-read at all: nothing outside Start and Resume called `refresh()`. The mid-run consequence the audit names (`-1013` on a later order, ERROR) is what `GridLadderPlacer` and the gateway do with an exchange refusal of an order built on stale numbers.

## 2. Acceptance criteria
- [x] `exchangeInfo` for the bot's symbol is refreshed on a named interval: `TERMS_REFRESH_EVERY_SECONDS = 900` (15 min), on the price watch's beat, in the states that hold or lay orders (`PRICE_STALENESS_HALTS`), the same shape as the key probe of `035F`. Evidence: `test_unchanged_terms_are_asked_for_again_and_change_nothing`, `test_the_terms_are_not_asked_for_before_the_interval_has_passed`.
- [x] A change in tick size, step size (and the market step) or minimum notional HALTs the bot with `EXCHANGE_TERMS_CHANGED` and "tick size 0.01 -> 0.001"-style detail; the symbol status of `EPIC-035E` is refreshed by the same read, because `SymbolStatusGate` and the watch both go through `LazyExchangeTerms.refresh()`. Evidence: `test_a_tick_size_change_halts_the_bot_with_the_old_and_new_values`, `test_a_minimum_notional_change_is_named_too`.

## 3. Design
One refresh path feeds `EPIC-035E` and this task: `LazyExchangeTerms.refresh()` now asks the exchange (`IOrderEntryTerms.fresh_terms_for`, a new port method; the real service sends `GetSymbolOrderRulesQuery(refresh=True)`, whose handler calls `IMarketMetadataProvider.refresh()` first, the explicit always-hits-the-network path that already existed). `GridTermsWatch` (new, a collaborator of `GridFacts` like `GridKeyProbe`) compares the terms before and after.
- A changed fee only replaces the kept terms (a fee moves no level). A symbol the exchange stopped listing halts with `SYMBOL_DELISTED`. A read that fails is logged and asked again at the next interval.
- A symbol status that turned non-TRADING is **not** acted on by the watch: it keeps the status current for the gate and for the next refusal, and the pause stays the placer's (`035E`). Proactively pausing on a status change is a separate choice; not made here.
- `fresh_terms_for` is a second method, not a flag on `terms_for` (`code/quality.md` §7).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_order_entry_terms.py` | `fresh_terms_for`; `application/orders/order_entry_terms_service.py` implements it; `application/queries/get_symbol_order_rules/{query,handler}.py` carry and honour `refresh` |
| `src/modules/trading/contracts/testing/fake_order_entry_terms.py` | `fresh_terms_for`, `fresh_reads`, `fail_fresh_reads_with` (verified in `test_order_entry_terms_fake.py`) |
| `src/modules/bots/application/services/bot_exchange_terms.py` | `fresh_exchange_terms_for` beside `exchange_terms_for` |
| `src/modules/bots/application/services/grid_run_context.py` | `LazyExchangeTerms` takes a second reader; `refresh()` uses it |
| `src/modules/bots/application/services/grid_terms_watch.py` (new) | the interval check |
| `src/modules/bots/application/services/{grid_facts,grid_executor,grid_executor_factory}.py` | the watch is beaten with the price watch; the factory passes the fresh reader |
| `src/modules/bots/domain/grid/grid_runtime.py` | `GridReason.EXCHANGE_TERMS_CHANGED` |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | one row in §5, one in §8; the `035E` row no longer says "until 035U" |

## 5. Testing
Unit tier, the real executor on the simulated venue. `tests/unit/modules/bots/application/services/test_grid_terms_refresh.py` (seven tests), `test_get_symbol_order_rules.py` and `test_order_entry_terms_service.py` (one each), `test_order_entry_terms_fake.py` (two). Shown red before the change: with `src/` stashed the bot stays `RUNNING` on a changed tick size (`assert RUNNING is HALTED`) and the two trading tests fail on the missing `refresh`; green after. Not run: a real exchange (never done here).

## Implementation notes
- The interval is the price watch's beat, so the resolution is the beat's; the 15 minutes is a floor, not a schedule.
- `exchangeInfo` for the whole venue is fetched (`IMarketMetadataProvider.refresh()` has no per-symbol form), one call per bot per 15 minutes and one per Start or Resume.

## Resume
Done. Nothing owed.
