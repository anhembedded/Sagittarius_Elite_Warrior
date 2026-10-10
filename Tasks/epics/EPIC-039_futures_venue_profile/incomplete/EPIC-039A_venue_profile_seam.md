# EPIC-039A — One place decides what a venue allows: every `is SPOT` branch in `bots` becomes a question to the venue profile

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10: any bot added later must have a Futures and a Spot side; see the [epic README](../README.md).
**Risk:** 🟡 — a refactor across `bots` domain, application and UI; Spot behaviour must not move
**Complexity:** M — nine non-UI sites, six UI sites, one port, one adapter, one guard
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) is read for the Spot journeys that must stay as they are; it is changed only if a user-visible word changes.
**Design:** [DESIGN §1.2, §3](../DESIGN_2026-10-10_futures_venue_profile.md) · **Decision:** D1, D4, D5 ([record](../DECISION_2026-10-10_futures_venue_profile.md))
**Depends on:** None. Blocks everything else.

---

## 1. Context and problem
`bots` decides "is this Spot?" in many places by comparing `venue.market_type` with `MarketType.SPOT`. Futures would add a second `if` at each. The owner wants a Futures side for *every* kind, so the decision moves behind one port that answers what a venue allows (`VenueProfile`), and a guard keeps it there.

### Facts verified on `master-warrior` `076d339` (re-check each with `grep -rn "MarketType.SPOT\|is not MarketType" src/modules/bots`)
Non-UI (9): `domain/bot.py:120` (`venue_locked_reason`) · `domain/bot.py:136` (`moved_to`) · `application/services/bot_run_facts.py:60` (`_venue_problem`) · `application/services/planner_numbers.py:59` · `application/queries/get_planner_market/handler.py:72` · `application/queries/run_grid_backtest/handler.py:70,86,97` · `application/services/exchange_facts_reader.py:63-64,183` (`SpotHolding`).
UI (6): `ui/strategies/arm_strategy_dialog.py:94` (`setRowVisible(self.leverage, venue.market_type is not MarketType.SPOT)`) · `ui/bots_screen/venue_choice.py:48` · `ui/bots_screen/bot_chart_host.py:80` · `ui/bots_screen/bots_presenter.py:118` · `ui/kinds/grid/backtest/grid_backtest.py:47` · `ui/kinds/grid/backtest/grid_backtest_presenter.py:262` (and `preview.py:92`, a preview, may stay).
Generic already, do not touch: `application/services/bot_price_watch.py:178`, `application/event_handlers/bot_event_router.py:123`.
`TradingVenue.market_type` is defined in `src/support/binance_gateway/contracts/trading_venue.py`; `MarketType` is `src/core/vo/market_type.py`. `bots` may import both (they are shared/support contracts today: confirm with `tests/unit/architecture/test_module_boundaries.py`).

## 2. Acceptance criteria
- [ ] `VenueProfile` (frozen dataclass), `TradeDirection` (`LONG`, `SHORT`, `NEUTRAL`), `MarginMode` (`ISOLATED`, `CROSS`) and the port `IVenueProfiles.for_venue(venue) -> VenueProfile` exist in `src/modules/bots/contracts/`. Fields exactly as DESIGN §3 lists, **no speculative field**: `market_type`, `directions`, `margin_modes`, `has_funding`, `exposure_kind` (`INVENTORY` | `POSITION`), `needs_reduce_only_exits`, `title_word` ("Spot" | "Futures", the word the UI shows).
- [ ] One adapter, `VenueProfilesByMarket` (in `bots/application/services/`), is the **only** file under `src/modules/bots/` that reads `venue.market_type` to decide behaviour. Spot profile: `directions={LONG}`, no margin modes, no funding, `INVENTORY`. Futures profile: all directions, `{ISOLATED}` (CROSS is added by a later epic), funding, `POSITION`, reduce-only exits. It is bound in the bots module's `register()` and resolved, never constructed in a caller.
- [ ] All 9 non-UI and 6 UI sites ask the profile. **The sentences the user reads for a Spot venue are byte-identical** ("Only a Spot bot can change its venue.", "… is not a Spot venue this app trades on"): for a Futures venue they must not claim "Spot"; they are built from `title_word`. A test fixes the Spot sentences verbatim.
- [ ] **Behaviour for Futures venues is still "not supported yet", on purpose:** `venue_choices` lists Spot venues only (as now), `Bot.moved_to` keeps refusing a venue whose profile says the kind cannot run there. A profile can say "Futures exists" while the Grid kind does not yet declare it (`039H` flips that). No Futures bot can be created by this task.
- [ ] A guard test (architecture tier) scans `src/modules/bots/**/*.py` and fails if any file other than the adapter contains `MarketType.SPOT`, `MarketType.FUTURES_USD_M`, `.market_type is`, or `SpotHolding` (the `SpotHolding` read moves behind the Spot adapter of `IVenueFacts` in `039E`; until then it is the **one** allowlisted file, listed by name in the test with the task that removes it). **Shown red** by re-adding one branch.
- [ ] `IBotKind` gains `supported_profiles(self) -> frozenset[MarketType]`, abstract; `GridKind` returns `{SPOT}`; every implementer in `src/`, `scripts/` and `tests/` is updated in the same commit.
- [ ] The Spot integration journeys (`tests/integration/modules/bots/`) and the unit tests of `bots` pass **unchanged** (no test edited to make them pass except to add the new constructor argument).

## 3. Design
Capability object behind a registry (the `ICliCommandTable`/`declare_cli` shape is the in-repo precedent for "ask the table, never the class"). Interface segregation: `VenueProfile` is a value, `IVenueProfiles` a one-method port. A guard instead of a rule: `EPIC-037C`'s "only one" idea — a second copy of the decision turns CI red. Do **not** add `is_futures`/`is_spot` booleans to `VenueProfile`: they would reinvite the branch it removes (Spot-ness is "directions == {LONG}, no leverage", which is what callers actually need).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/venue_profile.py`, `trade_direction.py`, `margin_mode.py`, `i_venue_profiles.py` (new) | the values and the port |
| `src/modules/bots/application/services/venue_profiles_by_market.py` (new) | the one adapter |
| `domain/bot.py` | `venue_locked_reason`/`moved_to` take the profile (domain stays Qt- and port-free: pass the profile in, do not resolve it inside the entity) |
| the 5 other application sites above | ask `IVenueProfiles`; the SPOT-typed reads move to the Spot adapter or take the venue's market from the profile |
| the 6 UI sites | ask the profile through the presenter's dependencies (`bots_dependencies.py`) |
| `contracts/i_bot_kind.py`, `domain/grid/grid_kind.py` and all `IBotKind` implementers incl. tests | `supported_profiles` |
| `module.py`, `composition/` | bind `IVenueProfiles` |
| `tests/unit/architecture/test_bots_decide_the_market_in_one_place.py` (new) | the guard |

## 5. Testing
Tier: unit and architecture; the Spot integration journeys as the unchanged proof.
- `test_the_spot_profile_allows_long_only_with_no_leverage` · `test_the_futures_profile_allows_all_directions_and_isolated_margin`
- `test_the_spot_user_sentences_are_unchanged` (golden strings from the 9 sites)
- `test_only_the_profile_adapter_decides_the_market` (guard; **mutation:** add `MarketType.SPOT` to another bots file → red)
- `test_every_bot_kind_declares_its_supported_profiles`
- run: `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/architecture -q` and the touched tests, then `tests/integration/modules/bots -q`.
Not run yet.

## Pitfalls
- Do not resolve a port inside a domain entity (`Bot`): pass the profile in; `domain-truth-rule.md` and the layer guards forbid it.
- `bot_price_watch.py` and `bot_event_router.py` already use `market_type` correctly (matching, not deciding): leave them, and make the guard's rule about *comparisons with a specific market*, not any use of the attribute.
- `bots` imports `MarketType` from `src/core/vo`, fine; it must **not** import anything from `trading/application` or `trading/adapters`.
- Port gains an abstract method → every implementer in `src/`, `scripts/` and `tests/` changes in the same commit (`architecture-rule.md` §2).

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: `grep -rn "MarketType.SPOT\|is not MarketType" src/modules/bots` and compare with the list above; then write the guard test and run it red.
