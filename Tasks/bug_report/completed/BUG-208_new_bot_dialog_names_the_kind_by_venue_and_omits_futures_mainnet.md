# BUG-208 — New bot shows the kind as "Futures Grid"/"Spot Grid" by venue, and silently omits Futures Mainnet

- **Reported:** 2026-10-14 (owner, desktop Bots → New bot, screenshots described; relayed by the coordinator session)
- **Severity:** 🟡 P2 — the owner could not tell the dialog's choices from the app's venues; nothing was placed wrongly
- **Status:** ✅ Fixed (2026-10-14)
- **Board:** The kind was titled from the chosen venue's market ("Futures Grid"/"Spot Grid", `kind_title(kind_id, profile)`) and the venue list dropped Futures Mainnet without a word (`is_offered`); the kind is now "Grid" everywhere and every venue a Grid runs on is listed, Futures Mainnet greyed out as "closed" with its reason.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) step 2 → `src/modules/bots/ui/` (`bots_screen/new_bot_dialog.py`, `bots_screen/venue_choice.py`, `kinds/kind_panels.py`) and `contracts/venue_profile.py`
- **Environment:** Desktop app on `master-warrior` `cb3f931`, offscreen render of the dialog. Nothing was placed, tested or simulated against Binance mainnet.

## Reproduction
1. Bots → New bot…, default venue Futures Testnet. Expected: kind "Grid". Actual: "Futures Grid"; choose Spot Testnet and it retitles to "Spot Grid".
2. Open the Venue list with all four venues enabled. Expected: four venues. Actual: Futures Testnet, Spot Testnet, Spot Mainnet; Futures Mainnet absent.

## Symptom
Owner: the Kind combo should say one kind, "Grid", valid on Spot and Futures; "Futures Mainnet" is enabled (the boot log lists it, the account tabs read it) but is not in the Venue combo. The Bots table showed "Spot Grid" for a Spot bot by the same rule.

## Root cause
Two deliberate-by-design choices that read as defects, and one unannounced omission:
1. **Label.** `kind_panels.kind_title(kind_id, profile)` built the title as `profile.title_word + " " + name`, and `NewBotDialog._follow_venue` and `BotsTableModel._value` both called it, so one kind carried two names and the label changed with the venue (`EPIC-039J`). The kind is one (`GRID_KIND_ID`), valid on both markets (`PROFILE_MARKETS`); the market belongs to the venue, which the Venue field and the table's Venue column already say.
2. **Venue.** `venue_choice.venue_choices` filtered with `is_offered(venue)`, which is false for `CLOSED_VENUES = {FUTURES_MAINNET}` (`EPIC-039` decision O7: no real-money Futures bot before an exchange-side stop and the testnet soak, `EPIC-039L`). The omission is deliberate, not a regression (`git log -S is_offered`: introduced with `EPIC-039J`), but it was silent: the user could not tell "closed" from "missing", and the dialog's own hint ("Start needs the venue enabled in Tools > Options > Trading") pointed at a setting that cannot open it.

## Fix
- `kind_title(kind_id)` returns the kind's name alone ("Grid"); the dialog no longer retitles on a venue change and the table shows the same label; the Venue column carries Spot/Futures. Decision under `domain-truth-rule.md`: a label states a fact of the thing it names; the market is a fact of the venue, so it is shown once, there.
- `venue_choices` lists every venue a kind runs on; a venue in `CLOSED_VENUES` carries `closed_reason` (the existing `bot_closed_reason` sentence), connection text "closed", and sorts last so the preselected venue is always one that can start. `add_venue_choice` lists it in a combo greyed out with the reason as tooltip; New bot and the Plan's Venue field both use it. `is_offered`, now unused, is removed. The mainnet gate itself (`CLOSED_VENUES`, `bot_closed_reason` on create/start/resume) is unchanged.
- Same defect family scanned: the Plan's Venue field shared the list (fixed by the same change); the Strategies panel has a fixed venue per card and no picker; plan import (`bot_plan_parser._venue`) accepts every non-disabled venue and the mainnet gate refuses it on creation.

## Regression test
`tests/unit/modules/bots/ui/bots_screen/test_new_bot_names_one_grid_and_lists_every_venue.py`:
- `test_the_kind_is_grid_whatever_venue_is_chosen` — red before: `{'Spot Grid', 'Futures Grid'}`.
- `test_futures_mainnet_is_listed_closed_with_the_reason` — red before: `KeyError: FUTURES_MAINNET` (venue absent).
- `test_a_closed_venue_is_listed_last_so_the_preselected_one_can_start`, `test_the_dialog_shows_a_closed_venue_greyed_out_with_its_reason` — red before for the same absence.
Existing tests that pinned the old behaviour were updated, not weakened: the Spot/Futures kind titles in `test_new_bot_follows_the_venues_market.py`, and the offered-venue lists in `test_the_picker_offers_venues_by_kind_and_profile.py`, `test_new_bot_venues.py`, `test_bots_change_venue.py`, `test_bots_presenter.py`, `test_venue_profile.py`.

## Verification
- Preview render of the dialog (offscreen): kind "Grid"; venues Futures Testnet, Spot Testnet, Spot Mainnet, then "Futures Mainnet — closed" greyed out.
- `pytest tests/unit/modules/bots tests/integration/modules/bots`: green; `tests/unit/architecture`: green except the known `grid_reconciler.py` 411-line guard, which another session splits. `ruff check`/`ruff format` clean; mypy clean on the touched files.
- Not verified: the owner's own build and the tooltip on a real display; nothing run against Binance.

## Docs touched
`Docs/SPEC/SPEC-014_run_a_grid_bot.md` (step 2: the kind is "Grid", a closed venue is listed with its reason). `Docs/MODULES/bots.md` states neither.
