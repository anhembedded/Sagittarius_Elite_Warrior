# BOT-187 — `main.py bot order <id>` prints the orders a bot's file records, read-only

**Status:** ✅ Done (2026-10-17; awaiting merge by the owner)
**Board:** `bot order <id>` next to `bot list|show`: the orders the Bots tab's table shows (level, side, price, quantity, executed, stored level state, client order id), read from the bot's saved run record through `GetBotQuery`; stored and labelled so, never live, never an exchange call (`src/modules/bots/cli/bot_order_verbs.py`). Live open orders are a named follow-up.
**Source:** The owner, 2026-10-17, via the coordinator session: *"giao luôn bot order <id>"* ("assign `bot order <id>` right away"), read by the coordinator as a read-only listing of one bot's orders.
**Risk:** 🟢 — read-only verb, no exchange call, no write; one defaulted field added to a read model.
**Complexity:** S — one verb, one report, one registry entry, one defaulted field.
**SPEC:** [SPEC-015](../../Docs/SPEC/SPEC-015_run_the_bots_headless.md)
**Depends on:** None (BOT-186 merged, `db5a961`).

---

## 1. Context and problem
The operator can see a bot's state (`bot show`) but not what it has on the exchange without opening the desktop app. **Reading confirmed from the code** (at `db5a961`): the coordinator's reading is right. The Bots tab's "orders" table is `BotProgress.orders` (`BotOrderLine`), built by `bot_progress` from the bot's saved Grid runtime (`StoredBot.runtime`) with no exchange call (`src/modules/bots/application/services/readiness/bot_progress_reader.py`, `src/modules/bots/ui/bots_screen/bots_table_models.py` → `BotOrdersTableModel`). So `bot order <id>` is a **read-only listing**. If the owner meant placing or cancelling orders, that is a different real-money feature that this task does **not** build.

**Live orders need an exchange call; none is made.** A read-only process holds no order session: opening one needs credentials and spends the venue's request budget (`ExchangeCallPolicy`), and `bot stop` shows what opening one costs on mainnet. The host writes `state/health.json` (counters per bot, no order list) and no per-order snapshot exists; inventing a writer is out of scope. So this task shows the stored record, labelled as stored.

## 2. Acceptance criteria
- [x] `bot order <id>` prints, per order, level, side, price, quantity, executed, stored state and client order id, in text and `--json`/`--format` like `bot show`. Evidence: `test_the_orders_are_the_ones_the_file_records_with_their_stored_state`, `test_the_text_view_says_stored_and_lists_one_row_per_order`, `test_the_bot_order_payload_keys_are_pinned`.
- [x] The output says it is stored, not live (first line; `source: "stored"`), and says the file may be behind when no copy of the app runs. Evidence: `test_with_no_copy_running_the_text_and_json_say_the_file_may_be_behind`.
- [x] A bot with no orders prints `No orders.`; a running bot whose run record cannot be read says `Orders unknown`, not `No orders.`. Evidence: `test_a_bot_at_rest_with_no_run_prints_no_orders`, `test_a_running_bot_whose_runtime_cannot_be_read_does_not_claim_no_orders`.
- [x] An unreadable bot file is reported with its path, not crashed; an unknown id is refused in words (exit 2). Evidence: `test_an_unreadable_bot_file_is_reported_with_its_path_not_crashed`, `test_an_unknown_id_is_refused_in_words`, and the same two through `main()`.
- [x] Read-only: declared `"read_only": true`, so it boots as a read-only copy and its log goes to the CLI log file (BOT-186 guard). Evidence: process test `test_bot_order_prints_the_stored_orders_and_changes_nothing` (file unchanged, no `instance.lock`); the every-command-declares-its-log guard.

## 3. Design
A new `IBotVerb` (`OrderBotVerb`) in its own file and a `Report` builder in its own file (P7: a verb is a table entry; the live source is the later variant). The payload's `source` names the source. Orders come from `GetBotQuery`, the Bots tab's own query; `GetBotStatusReportQuery` supplies `app_running` and names a refused file (`GetBotQuery` returns `None` for both unknown and refused). `BotOrderLine` gains `state` (the level's stored `LevelState`), defaulted to `""` so the tab and its preview are untouched: the stored status the task asks for was not in the read model.

Honesty (domain truth, F3): `bot_progress` returns `None` for both "no run yet" and "runtime cannot be read". For a bot at rest (`DRAFT`, `STOPPED`) `None` means no orders; for any other state it means the record is unreadable, and the report says `Orders unknown` (`orders_known: false`) instead of `No orders.`.

## 3a. Reuse
- Query: `GetBotQuery`, `GetBotStatusReportQuery` — used. Read model `BotProgress.orders`/`BotOrderLine` — used, one field added.
- Output: `Report`, `ReportPrinter`/`print_report` (`--json`, `--format`) — used; `AT_REST_STATES` — used. Unreadable entry `UnreadableBotEntry` — used.
- Registry: `cli_commands.json` `read_only` — used; `capabilities.md` has no row for a CLI order listing. Searched `src` for another order lister (`grep -rn "client_order_id" src/modules/bots`): none outside the runtime codec and the tab.
- Live open orders (order session): not used because a read-only process holds none and no snapshot of orders exists.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/cli/bot_order_verbs.py`, `bot_order_reports.py` | the verb and the report (new) |
| `src/modules/bots/cli/bot_verbs.py` | register `OrderBotVerb` in `BOT_VERBS` |
| `src/config/cli_commands.json` | `bot order <id>` entry, `read_only: true` |
| `src/modules/bots/contracts/bot_progress.py`, `.../bot_progress_reader.py` | `BotOrderLine.state` (defaulted), filled from the level state |
| tests | `test_bot_order_verb.py` (unit), `test_bot_order_command_process.py` (process through `main()`), `test_bot_verbs.py` (verb table) |

## 5. Testing
Unit and process tests above, tier per `ci-rule.md` §2. Mutation checks, each turned red: `known` forced true; `state=` dropped from the reader; `read_only` removed from the entry; the no-host note removed. Commit tier and architecture guards: see the notes.

## 6. Docs touched
`Docs/SPEC/SPEC-015` (surfaces), `Docs/OPERATIONS/headless_runbook.md` §6, `Docs/MODULES/bots/07-deployment.md` and `README.md` (design: the verb and its source).

## Implementation notes
- Follow-up (not built): **live open orders** — a command that opens an order session or asks the running host through `IHostControl`; needs an owner decision on the call budget. Name: `BOT-188` candidate.
- Known limit: an unreadable runtime still logs the `[bot-progress]` WARNING (stderr); the report no longer says `No orders.` for it.
