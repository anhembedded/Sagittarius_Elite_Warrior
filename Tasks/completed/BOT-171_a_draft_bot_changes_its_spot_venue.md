# BOT-171 — A draft bot changes its Spot venue from the Plan, and New bot lists every Spot venue with its connection state

**Status:** ✅ Done (2026-10-07)
**Board:** A draft bot that never ran can be moved between Spot Testnet and Spot Mainnet from the Plan's Venue field; Connect re-reads the new venue's account, the chart switches to its market and readiness is judged again, with unsaved parameters kept. A bot that has run or runs keeps its venue (`Bot.moved_to`); New bot lists each Spot venue with "API key saved" or "no API key".
**Source:** the owner, 2026-10-07, approved as one pull request with `BUG-181` and `BOT-170`: a bot's venue is fixed at creation; allow changing it between Spot venues while it is a Draft, from the bot's editor; never once it has run or is running.
**Risk:** 🟡 — the Connect step, the chart, the planner and the fills are all bound to the selected bot's venue, so the screen must follow a move; the rule that nothing real is touched by a draft is what makes the move safe
**Complexity:** M — one aggregate rule, one use case, one Plan field, and a screen that follows a bot whose venue moved
**SPEC:** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** `BUG-172` (a bot charts its own venue's market)

---

## 1. Context and problem
`EditBotCommandHandler` states it: kind, venue and symbol are not editable, because orders, the symbol's lease and derived inventory are tied to them (ADR D6). A trader who made a bot on Spot Testnet and wants to run it on Spot Mainnet had to rebuild it. A draft that never ran owns none of those things.

## 2. Acceptance criteria
- [x] The Plan has a Venue field listing every Spot venue; choosing another moves a Draft that never ran at once.
- [x] After the move Connect reads the new venue's account, the chart reads the new venue's market, and readiness is judged on both.
- [x] A bot that has run or is running (any state but a Draft that never ran) refuses: the field is disabled with the reason, and the command refuses `VENUE_FIXED` in words with the bot unchanged.
- [x] Futures venues are never offered to a Spot Grid; a Futures bot does not change venue here (`EPIC-029K`).
- [x] Moving to Spot Mainnet asks no confirmation; the real-money question stays at Start (D11).
- [x] New bot lists every Spot venue with its connection state.
- [x] Parameters not yet saved stay on screen across the move.

## 3. Design
- **The rule lives in the aggregate** (`Bot.venue_locked_reason`, `Bot.moved_to`): DRAFT with no `run_started_at`, Spot to Spot. A STOPPED bot edited back to DRAFT keeps its `run_started_at`, so it still counts as having run. `BotSnapshot.venue_locked` carries the reason to the screen, so the field never copies the rule.
- **Its own use case** (`ChangeBotVenueCommand`), not a flag on `EditBotCommand`: a venue change is not an edit of parameters, and Save and start must keep judging exactly the parameters on screen.
- **Immediate, not part of Save**: Connect, the chart and readiness are bound to the saved bot's venue, so an unsaved venue would be judged against an account that is not the one that would run.
- **The screen follows a bot whose venue moved, whichever writer moved it** (`BotVenues.moved/follow`): selecting it again restarts Connect, the planner, the fills and the chart on the new venue, keeping the unsaved parameters.
- **Connection state** is what is known without a network call: whether the venue has an API key (the venue's own stored key, ungated). Whether the key works is the Connect step's read once a bot is on the venue.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/bot.py` | `Bot.venue_locked_reason`, `Bot.moved_to`, `BotVenueFixedError`. |
| `src/modules/bots/application/use_cases/change_bot_venue/` | The command and its handler; bound in `composition/command_bindings.py`. |
| `src/modules/bots/contracts/bot_snapshot.py`, `bot_command_result.py` | `venue_locked`; `BotRefusal.VENUE_FIXED`. |
| `src/modules/bots/ui/bots_screen/venue_choice.py` | Every Spot venue with its connection state; shared by New bot and the Plan. |
| `…/bot_plan_panel.py`, `bots_view_model.py` | The Venue field and its intent signal. |
| `…/bot_venues.py`, `bots_presenter.py`, `bot_commands.py`, `connect_step.py` | The command for a pick; following a moved bot; the presenter's imports are relative so the file stays under 400 lines. |
| `…/new_bot_dialog.py`, `bots_dependencies.py` | New bot takes `VenueChoice`s; the venue contexts are a dependency. |

## 5. Testing
- `tests/unit/modules/bots/domain/test_bot_venue.py`, `tests/unit/modules/bots/application/test_change_bot_venue.py` — the rule over every state, a draft edited back from Stopped, Futures, a missing bot, the same venue.
- `tests/unit/modules/bots/ui/bots_screen/test_bots_change_venue.py` — a draft moved to Spot Mainnet reads Spot Mainnet's account and market (the testnet's account is not read again); a failing mainnet account fails Connect on the mainnet and is one bar; unsaved parameters stay; no confirmation; a running bot's field is disabled and a stray request is refused in words; a stopped bot's field is disabled; New bot's list. Mutation-checked: removing the re-select fails two of them.
- `tests/integration/modules/bots/test_a_draft_bot_and_its_venue_on_the_fake_exchange.py` — the real handler and store on the composed app over the fake Binance server.

## Implementation notes (written when done)
- First wiring read the move as a creation (`PendingAction.action is None` means "a new bot"): the screen re-selected the bot and dropped unsaved edits. `PendingAction.moves_venue` separates the two.
- `IVenueContexts.enabled()` is every venue the build assembles (`EPIC-034B`), so "enabled" says nothing about a key; the connection state reads the venue's stored key instead. This is a judgement call: it is the state known without a request; the live state is Connect's.
- Delivered in the pull request that also carries `BUG-181` and `BOT-170`; not merged.
