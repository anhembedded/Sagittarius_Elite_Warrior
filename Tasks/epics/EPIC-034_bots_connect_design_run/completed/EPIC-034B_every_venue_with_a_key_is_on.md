# EPIC-034B — Every venue with a usable key is on; the Options venue toggles and the restart leave

**Status:** ✅ Done (2026-10-07)
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
- [x] Tools → Options → Trading has no venue check boxes; every testnet venue is assembled at start-up.
- [x] A venue without a key is still listed where venues are listed, with "no key" as its state, and no order path reaches it.
- [x] Saving a key in Options takes effect without a restart for every reader that resolves credentials per call (they already do: `futures_account_reader.py:209`), and the Options text no longer says a key needs a restart.
- [x] An existing configuration that names venues still loads; the setting is ignored and logged once.
- [x] SPEC-003 and SPEC-004 describe the new behaviour.

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

Run (2026-10-07): the unit, integration and sanity tiers on the branch. One failure, `test_workbench_conformance[True-1024x700]` (the Backtest mode needs 706 px of a 700 px window), fails identically on `master-warrior` without this change. The testnet tier was not run: no credentials in this session.

## Implementation notes
- **The enabled set is a fact of the build.** `resolve_trading_venues` (`src/support/binance_gateway/contracts/binance_endpoints.py`) returns every venue with `supports_order_submission`, in `TradingVenue` order, and no longer reads configuration; the primary venue is therefore always Futures Testnet. A venue without a key is assembled like the other: its connection check answers `NOT_CONFIGURED` (`futures_account_reader.py:210`), the one answer SPEC-003 already names, and no order path reaches it because every path needs the venue's session open, which needs that check to pass.
- **Legacy configuration.** `log_ignored_venue_setting` logs once at INFO, from `_build_venue_contexts`, when `exchange.trading_venues` is present or the scalar `exchange.trading_venue` is anything but the defaults file's `"disabled"`. Both keys stay in `ConfigKeys` for that read alone.
- **Options.** The Trading page lost its check boxes, the lock label, the `validation_message` rule, the `user_config.json` write and the restart sentences; `_Fields` is `(key, secret)`. The readers resolve credentials on each call (`futures_account_reader.py:209`; the user data stream at `futures_user_data_stream.py:222`), so the next request uses a key saved there. `test_trading_settings_has_no_venue_control.py` replaces `test_trading_settings_venue.py`.
- **`TradingVenue.DISABLED` stays.** It is still the refusal for a caller that names a venue that cannot trade (`TRADING_VENUE_DISABLED`), the contract's "nothing enabled" shape (`VenueContexts` still accepts an empty tuple, and `FakeVenueContexts` and the contract tests use it) and the CLI's read-only shape. Removing it is a cross-module change with no behaviour to gain; it is a follow-up, not part of this task.
- **Left for EPIC-034C.** The banner's `TRADING_DISABLED` state ("Trading is OFF. Data view only.") can no longer occur at boot, and is removed with the switch.
