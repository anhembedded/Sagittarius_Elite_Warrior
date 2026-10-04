# BUG-144 — Creating a bot from the Bots tab fails: `'str' object has no attribute 'value'`

- **Reported:** 2026-10-04 (the user, in chat, with the dev-mode log of a real session)
- **Severity:** 🔴 P1. No bot can be created from the Bots tab; the New bot dialog's Create is refused every time.
- **Status:** ✅ Fixed (2026-10-04)
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (create a Grid bot) → `src/modules/bots/` → `ui/bots_screen/new_bot_dialog.py`
- **Environment:** Windows, PySide6 6.11.1, `master-warrior` `b50de106`, Spot Testnet only enabled.

## Reproduction

1. Open the Bots tab and press New bot.
2. Pick Grid on `spot_testnet`, type `BTCUSDT`, fill the Grid panel, and press Create.

Expected: the bot is saved as DRAFT. Actual: refused, every time.

## Symptom

```
App - DEBUG - Payload: CreateBotCommand(name='HoangAnh', kind='grid', venue='spot_testnet', symbol='BTCUSDT', config={...})
App - ERROR - CreateBotCommand failed: 'str' object has no attribute 'value'
App.Bots.Screen - INFO - Bots screen: Create HoangAnh refused
```

`venue='spot_testnet'` is a plain string. A `TradingVenue` member would print as `<TradingVenue.SPOT_TESTNET: 'spot_testnet'>`.

## Root cause

- `NewBotDialog` stores each venue as its combo's item data (`self.venue.addItem(venue.value, venue)`) and reads it back with `self.venue.currentData()`.
- `TradingVenue` is a `str`-based enum, so Qt stores the item data as a `QString` and hands back a plain `str`. `CreateBotCommand.venue` is typed `TradingVenue`, and nothing checks it at runtime.
- `JsonBotStore.save` → `bot_record_codec.encode` (`bot_record_codec.py:57`) then called `definition.venue.value` and raised.

**Why the gate was green.** `test_create_waits_for_a_symbol_and_names_what_it_does` asserted `command.venue == VENUE`, and `'spot_testnet' == TradingVenue.SPOT_TESTNET` is true for a `str` enum. Every other bots test builds `CreateBotCommand` with the member itself. `chart_controls.py` already records the same Qt behaviour for its filters and rebuilds the enum. No case study: the trap is now one line in `.claude/rules/pitfalls/ui.md`, and a scan of `currentData()` found no other place that keeps a `str` enum's item data unrebuilt (`grid_panel.py` and `chart_controls.py` rebuild it, `order_options_bar.py` reads by index, `system_controls_card.py` stores the plain `.value` on purpose).

## Fix

`new_bot_dialog.py` rebuilds the member at the boundary that lost it: `venue=TradingVenue(self.venue.currentData())`.

## Regression test

`tests/unit/modules/bots/ui/bots_screen/test_bots_dialogs.py::test_the_new_bot_command_carries_the_venue_enum_and_saves` drives the real dialog, then saves its command through the real `CreateBotCommandHandler` and `JsonBotStore`, and asserts `type(command.venue) is TradingVenue`.

- Before the fix it failed with the user's exact error: `AttributeError: 'str' object has no attribute 'value'` at `bot_record_codec.py:57`.
- After the fix it passes.

## Verification

- `tests/unit/modules/bots` and `tests/integration/modules/bots`: 771 passed.
- The commit-tier gate, and the PR's `ci-local.ps1 -Full` run on GitHub Actions.
- The user's next Create in the Bots tab is the live confirmation.
