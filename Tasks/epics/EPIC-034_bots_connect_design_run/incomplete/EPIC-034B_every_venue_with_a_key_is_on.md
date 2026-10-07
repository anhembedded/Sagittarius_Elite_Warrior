# EPIC-034B — Every venue with a usable key is on; the Options venue toggles and the restart leave

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🟡 — changes how the app assembles its venues at start-up
**Complexity:** M — configuration, composition and the Options page
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-003](../../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md), [SPEC-004](../../../../Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md)
**Depends on:** None

---

## 1. Context and problem
The venues are read once at start-up from configuration (`src/support/binance_gateway/binance_endpoints.py:130-167`) and chosen with two check boxes in Tools → Options → Trading (`trading/ui/settings/trading_settings_view.py:30`). A change needs a restart, and until then the panels disagree: on the owner's screen the status bar said "connected (FUTURES_TESTNET)" while the Strategies panel said "No trading venue is enabled… restart the app". Decision D2 removes the toggles.

## 2. Acceptance criteria
- [ ] Tools → Options → Trading has no venue check boxes; every testnet venue is assembled at start-up.
- [ ] A venue without a key is still listed where venues are listed, with "no key" as its state, and no order path reaches it.
- [ ] Saving a key in Options takes effect without a restart for every reader that resolves credentials per call (they already do: `futures_account_reader.py:209`), and the Options text no longer says a key needs a restart.
- [ ] An existing configuration that names venues still loads; the setting is ignored and logged once.
- [ ] SPEC-003 and SPEC-004 describe the new behaviour.

## 3. Design
Make the enabled set a derived fact (venues whose credentials resolve) rather than a stored setting. Keep `TradingVenue.DISABLED` only if something still needs it; otherwise remove it in this task. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/binance_gateway/binance_endpoints.py` | venues no longer from configuration |
| `src/modules/trading/composition/venue_*` | every venue assembled |
| `src/modules/trading/ui/settings/*` | toggles removed, text corrected |
| `Docs/SPEC/SPEC-003*`, `SPEC-004*` | updated |

## 5. Testing
A composition test on the graph `create_app()` builds: both venues present with and without keys. An Options page test: no venue control. A legacy-configuration test. Not run.

## Implementation notes (written when done)
Not started.
