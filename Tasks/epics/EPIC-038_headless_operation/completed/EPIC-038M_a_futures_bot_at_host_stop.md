# EPIC-038M — The host's default stop leaves a Futures bot only under a covering stop, and closes the rest

**Status:** ✅ Done (2026-10-20) — GitHub Actions' `-Full` run and the review verdict are on the pull request
**Branch:** `claude/o12-futures-host-stop-policy`
**Source:** the owner delegated O12 to the coordinator session on 2026-10-20 (*"bạn tự quyết định đi"*, translated: you decide); the coordinator decided (a) with a per-bot fallback and handed it over. Decision record: [`DECISION_2026-10-20_a_futures_bot_at_host_stop.md`](../DECISION_2026-10-20_a_futures_bot_at_host_stop.md).
**Risk:** 🔴 — real-money path: a mainnet Futures position is closed at market, or left standing, when the host stops
**Complexity:** M — one query across the module boundary, one policy, one shared stop loop; no stored format, setting or unit changes
**Epic:** [EPIC-038](../README.md)
**SPEC:** SPEC-015 (§3 steps 8 and 9, the stop's outcomes, the known gaps) is updated.
**Depends on:** `EPIC-038D` (the host and its policies), `EPIC-039L` C2 (the stop on the exchange, PR #550).

---

## 1. Context and problem
`LeaveOrdersResting` left every bot as it was, so a Futures bot whose stop was gone stayed leveraged and unwatched through a `systemctl stop`, a `sew-update` or a restart; O12's accepted answer (2026-10-13) said that is not acceptable. The reading of "does a stop cover this position" existed only for a halt's words (`ProtectiveStopService.describe_stop`).

## 2. Acceptance criteria
- [x] A Futures bot whose position a stop on the exchange covers is left exactly as it is: position, resting orders, stop; the server sees no order placed or cancelled; no WARNING. *Evidence:* `test_a_bot_whose_position_stands_under_its_stop_is_left_as_it_is` (fake Futures exchange); unit `test_a_futures_bot_whose_stop_covers_its_position_is_left_as_it_is`.
- [x] A Futures bot whose stop is missing, not on the exchange, on the wrong side or unreadable is closed through the Stop the Bots tab uses (`CLOSE_AT_MARKET`) and ends flat. *Evidence:* `test_a_bot_whose_stop_was_cancelled_by_hand_is_closed_flat_before_exit`, `test_a_bot_whose_stop_cannot_be_read_is_closed_not_left` (fake exchange: STOPPED, position 0, nothing resting); unit `test_a_futures_bot_whose_stop_is_missing_wrong_or_unread_is_closed_before_exit` (three cases).
- [x] Every bot so closed is named at WARNING and in the stop ledger until it is STOPPED; a close that does not finish stays in the ledger. *Evidence:* the WARNING assertions of the tests above; `test_a_bot_that_closes_is_named_in_the_ledger_until_it_is_stopped`, `test_a_stop_that_never_finishes_ends_when_the_host_gives_up`, `test_a_close_the_lifecycle_refuses_is_a_warning_and_the_bot_stays_in_the_ledger`.
- [x] A Spot bot is never closed, whatever the read budget or a failed read says (review of #626, finding 1). *Evidence:* `test_a_spot_bot_is_never_closed_when_the_read_budget_runs_out_before_it`, `test_a_spot_bot_is_left_even_when_its_coverage_cannot_be_asked`, `test_the_report_says_whether_a_bots_venue_holds_a_position_from_the_venue_profile` (four venues; not in the JSON payload). Red against the first push: the Spot bot was closed.
- [x] A host that gives up mid-read names the bots it never reached, and the summary counts accepted closes only (findings 2 and 4). *Evidence:* `test_the_ledger_names_the_bots_not_yet_read_while_the_first_is_being_read`, `test_the_summary_counts_only_the_closes_that_were_accepted`.
- [x] A NEUTRAL grid long under its one stop, with a ladder resting, is closed (finding 3, D8). *Evidence:* `test_a_neutral_bot_long_under_its_one_stop_is_closed_because_its_ladder_can_flip_it` (fake exchange; mutation: rule off, 1 red).
- [x] A flat bot is left only when no ladder rests (D5). *Evidence:* `test_a_flat_bot_whose_ladder_still_rests_is_closed_because_a_fill_would_open_a_position`, `test_a_flat_bot_with_nothing_resting_is_left`.
- [x] Spot is unchanged and asks the exchange nothing. *Evidence:* `test_a_spot_bot_has_no_stop_to_cover_and_the_exchange_is_not_asked`, `test_a_spot_bot_is_left_with_no_stop_asked`, the unchanged `test_stop_policies.py` and the Spot journey of `test_the_run_hosts_stop_policies_on_the_fake_exchange.py`.
- [x] The deadline holds: reading is bounded by a share of `--stop-timeout`, a bot unread by then is closed, and the log says the deadline made closing the safe side; no constant of the unit moves. *Evidence:* `test_when_the_read_budget_runs_out_the_rest_are_closed_unread_and_the_log_says_so`; `STOP_GRACE_SECONDS`, `TimeoutStopSec=62` and `render_service_files.py` untouched (`test_service_files.py` green).
- [x] A bot already STOPPING is waited for, not read or asked again; a stop the host stopped waiting for is not started. *Evidence:* `test_a_bot_already_stopping_is_waited_for_and_not_read_or_asked_again`, `test_a_bot_not_looked_at_because_the_host_stopped_waiting_stays_in_the_ledger`.
- [x] An unread answer is never covered at any layer. *Evidence:* `test_a_read_that_fails_is_unread_never_covered`, `test_a_position_venue_whose_bot_has_no_protection_is_not_covered`, `test_only_a_stop_that_covers_or_a_bot_with_nothing_exposed_may_be_left`.
- [x] The desktop Stop dialog and the Emergency Stop are not changed. *Evidence:* no file of either is in the diff.
- [ ] **Not run:** a real exchange; the real `systemd` stop of a host with a Futures bot (the runbook's checklist row 4 is updated and unsigned); Windows.

## 3. Design

### 3.1 What is built
| Piece | Decision |
| :--- | :--- |
| Contract | `bots/contracts/bot_stop_coverage.py`: `StopCoverage` (`NOT_APPLICABLE`, `NOTHING_EXPOSED`, `COVERED`, `UNCOVERED`, `UNREAD`; `leaves_standing`), `StopCoverageReading`, `GetBotStopCoverageQuery`, `BotStopCoverage`. |
| Read | `StopCoverageReader` (`bots/application/kinds/grid/protection/`) judges the recorded stops against the exchange's open protective orders and the position through `judge_stop` (extracted from `stop_words`); `describe_stop` and `IExposureProtection.read_coverage` are its two renderings. |
| Path | `GetBotStopCoverageQueryHandler` → `IBotRunner.stop_coverage` → `IBotExecutor.stop_coverage` → the bot's `IExposureProtection`. The venue profile (`ExposureKind.POSITION`) gates it in the handler. |
| Policy | `LeaveOrdersResting(dispatcher, stop_timeout_s)` decides per bot (`_Action`: leave, close, await, skip), on `BotStatusEntry.may_hold_position` first (a Spot bot is left, never read), reads inside `READ_SHARE` of the timeout, closes through `HostBotStopper`, and keeps the unread bots in the ledger until it has decided them (`StopLedger.forget`). |
| Shared stop loop | `HostBotStopper` (`operations/adapters/host_bot_stopper.py`): the dispatch-and-wait `StopBotsFirst` had, parameterised by the exposure handling; `StopBotsFirst` keeps its words and its behaviour. |

### 3a. Reuse
`describe_stop`'s reading (the new reader is that code, moved), `StopBotForHostCommand`, `StopLedger`, `read_bot_status`/`active_bots`, `BotAccountReads.protective_orders` and `ladder_orders`, `venue_profile_of`/`ExposureKind` (no new market comparison), the booted Futures world of `futures_bots_world.py`. Catalogue (`.claude/rules/capabilities.md`): `ICommandDispatcher` used; no UI need.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/bot_stop_coverage.py` (new) | the contract |
| `src/modules/bots/contracts/i_exposure_protection.py`, `i_bot_executor.py`, `i_bot_runner.py` | `read_coverage`, `stop_coverage`, `stop_coverage` |
| `.../grid/protection/stop_words.py`, `stop_coverage_reader.py` (new), `protection_futures.py`, `protection_spot.py` | `judge_stop`; the reader; the service delegates; Spot answers `NOT_APPLICABLE` |
| `.../grid/grid_executor.py`, `services/lifecycle/bot_runner.py`, `read_only_bot_runner.py` | the read, off the worker; the runner's door |
| `.../queries/get_bot_stop_coverage/` (new), `composition/query_bindings.py` | the query and its binding |
| `src/modules/operations/adapters/host_bot_stopper.py` (new), `stop_bots_first.py`, `leave_orders_resting.py`, `cli/run_command.py` | the shared loop; the policy; it is given `--stop-timeout` |
| `src/support/log_view/template_catalogue.json` | regenerated (`render_log_templates.py --write`) |
| tests, docs | §5, §6 |

## 5. Testing
Unit (`tests/unit/modules/operations/adapters/test_leave_orders_on_a_position_venue.py`, `.../bots/application/test_get_bot_stop_coverage.py`, the existing `test_stop_words.py` and `test_stop_policies.py`) and integration on the fake Futures exchange (`tests/integration/modules/bots/test_the_run_hosts_default_stop_on_a_futures_bot_on_the_fake_exchange.py`, five journeys). Every test was red against the unchanged policy for the behavioural reason (nothing read, nothing closed) before the code. Mutations, each red: unread counted as left (6 red), the flat-ladder branch removed (1 red), the read budget never spent (1 red), the close carrying KEEP (7 red), only `UNCOVERED` closed (4 red), the position-venue gate removed (2 red). Full unit, architecture, and the touched bots/operations integration suites green locally; GitHub Actions' `ci-local.ps1 -Full` is the full gate.

## 6. Docs touched
`Docs/MODULES/bots/06-runtime.md` (new section, new diagram `diagrams/06-host-stop.puml`) and `07-deployment.md` (the host's stop); `Docs/OPERATIONS/headless_runbook.md` §0, §3c ("what a restart does to the market"), §8, §11 row 4; `Docs/SPEC/SPEC-015_run_the_bots_headless.md` (steps 8, 9; the gaps; the evidence table); `Docs/OPERATIONS/LOGGING.md` (the `[stop-policy]` lines), `Docs/VOCABULARY/README.md`; `Tasks/COORDINATION.md` (the stale O12 line).

## Implementation notes (written when done)
- **Review round 1 (blocking, fixed):** the first push closed Spot bots once the read budget was spent (an unread answer was applied to every bot). The venue profile now decides before the budget; a NEUTRAL grid is closed while its ladder rests (D8); the ledger names unread bots; the summary counts accepted closes. The window between a `COVERED` read and the app's stop is accepted and named in the decision record (D4).
- **A flat bot with a resting ladder is closed (D5).** Not in the delegation's words; the author's reading, flagged for the owner's veto. It costs no market order.
- **`--on-stop stop-bots` still refuses KEEP for a Futures bot** and leaves it (an open question, decision O1), as the runbook says.
- **The read is not queued behind the bot's worker.** A read racing a placement finds the stop missing and closes: the safe side.
- Two test files (`test_bot_lifecycle_commands.py`, `test_start_bot_readiness.py`) sat 3 and 6 lines under the 400-line ceiling; their runner doubles take the new abstract method as `raise NotImplementedError`, the file's own idiom, rather than an import.
