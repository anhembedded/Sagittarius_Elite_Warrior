# EPIC-038K — `bot start` on the running host, through the command directory

**Status:** ✅ Done (2026-10-17) — owner decision of 2026-10-17 (below); the reviewer's verdict is on the pull request
**Branch:** `claude/epic-038k-start-delete-running-host`
**Source:** the owner, 2026-10-17, relayed by the coordinator session: the running headless host takes `bot start <id>` through the command directory (EPIC-038J, channel A), next to `bot stop`, `bot pause` and `bot resume`. *Why, as relayed:* a stopped bot can only be started today by restarting the whole host with `run --start-planned`; a restart turns every other RUNNING bot RECOVERING and needs `--resume-recovering` to bring them back; the owner runs several bots at once and wants Stop, edit the plan, then Start of ONE bot without touching the others. **Scope change the same day (relayed by the coordinator session): `bot delete` is dropped** — deleting stays `bot apply --prune` on a stopped host, and the command file gets no `delete` word. The first version of this work, with delete, is parked on the local and remote branch `claude/epic-038k-delete-parked` (not for merge) in case the owner reverses it.
**Risk:** 🔴 — a new path by which a bot starts trading with real money; the mainnet confirmation (decision O8), the venue-wide reconcile and the one-bot-per-symbol rule all sit on it
**Complexity:** S — one table row and one verb on a channel that exists; two refusals added to the existing host Start
**Epic:** [EPIC-038](../README.md)
**SPEC:** SPEC-015 (§3a, §4, §7, §8) is updated.
**Depends on:** 038J (done, merged as PR #560); BUG-224 (the optional-key style of the command file, PR #563).

---

## 1. Context and problem
`bot stop|pause|resume` reach a running host through `state/control/` (038J). A stopped bot still had no way back to RUNNING except a host restart with `run --start-planned`, and a restart turns every other RUNNING or PAUSED bot RECOVERING (`restarts_into_recovering`), which a person must then resume (decision O2). The owner runs several bots at once; the wanted loop is Stop, edit, Start of one bot, with the others untouched.

## 2. Acceptance criteria
- [x] `bot start <id>` runs the same Start the Bots tab and `--start-planned` run, once, and audits it; one implementation. *Evidence:* `test_each_action_dispatches_its_contract_command_and_only_that` (START → `StartBotForHostCommand`, the command `--start-planned` dispatches); `test_a_spot_bot_is_stopped_then_started_again_while_the_host_keeps_running` (composed app, the command directory); mutation: START mapped to Pause turned all 7 integration tests of the first version red.
- [x] Only a DRAFT or STOPPED bot starts, decided by the lifecycle table; a HALTED or AWAITING_RECOVERY bot is refused in words that name `run --resume-halted` and the Bots tab. *Evidence:* `test_a_bot_that_is_not_at_rest_is_never_started_and_nothing_is_opened` (every other state), `test_a_halted_or_awaiting_bot_is_refused_with_the_way_back_in_words`, `test_a_halted_bot_is_not_started_from_a_file_and_stays_halted`, `test_a_second_process_start_of_a_halted_bot_is_refused_in_the_screens_words` (real host and second process, exit 2, audited); mutations: removing the HALTED answer → 2 red, removing the table gate → 6 red.
- [x] A mainnet venue needs `--confirm-venue <venue>` exactly as `bot stop` does (O8): without it nothing is opened or started, and the refusal names the venue's other RECOVERING bots (owner decision "1. keep as is"). *Evidence:* `test_a_mainnet_start_without_the_venue_typed_opens_and_starts_nothing` (Spot and Futures mainnet, `session.ready_requests == 0`), `test_a_mainnet_start_with_another_venues_name_typed_is_refused`, `test_the_refusal_for_a_mainnet_venue_names_the_other_bots_the_open_would_reconcile`, `test_the_recovering_bots_of_another_venue_are_not_named`, `test_a_futures_mainnet_start_is_not_run_until_the_venue_is_typed` (composed app); mutations: dropping the names → 1 red, counting other venues' bots → 1 red.
- [x] The J1a/J1b rule is reused, not copied: a start refused by `ONE_ACTIVE_BOT_PER_SYMBOL`, `MAX_ACTIVE_BOTS_PER_VENUE` or `VENUE_RECOVERING` says so in words. *Evidence:* `test_a_start_on_a_symbol_another_bot_holds_is_refused_in_words`, `test_a_start_on_a_full_venue_is_refused_in_words_at_the_cap_and_not_below_it`, `test_with_the_venue_typed_a_waiting_recovering_bot_still_refuses_the_start_in_words`, `test_a_start_the_screen_would_refuse_is_refused_in_its_words_and_changes_nothing`.
- [x] Starting one bot touches no other. *Evidence:* `test_starting_one_bot_leaves_every_other_bot_as_it_was`.
- [x] A Futures start is covered as well as Spot. *Evidence:* `test_a_futures_bot_is_started_stopped_and_started_again_from_the_command_directory` (the ladder rests, `--close-position` stop, start again), `test_a_futures_mainnet_start_is_not_run_until_the_venue_is_typed`.
- [x] The command file stays `sew.host-command/1`: `start` is a new `action` word, no new key; there is **no** `delete` word; what an older host does is stated. *Evidence:* `test_the_new_action_is_a_new_word_not_a_new_key`, `test_delete_is_not_an_action_the_host_knows`, `test_a_start_survives_the_round_trip`, `test_the_refusal_of_an_unknown_action_lists_every_action_the_host_knows`; `close_position` is still refused on any action but stop.
- [x] Same account rules, replay protection, expiry and audit as the existing verbs. *Evidence:* the verb goes through the unchanged `HostCommandProcessor`; the process test reads the audit of a real host (`received`, `refused`).
- [x] The CLI registry guards list the verb. *Evidence:* `test_the_verbs_are_a_table_not_a_chain`, `test_the_verbs_are_registered_under_the_words_the_operator_types`, `test_command_access.py` (`("bot","start")` read-only), the generated `exit_codes.md`.
- [ ] **Not run:** a real `bot start` accepted by a live host in a process test (a start needs a funded fake account in a child process; the composed-app journey over the fake exchange proves the dispatch, the process test proves the refusal and the audit). Windows. Any exchange but the fake.

## 3. Design

### 3.1 What is built
| Piece | Decision |
| :--- | :--- |
| Wire | One new member of `HostControlAction` (`start`); the codec's closed set is derived from the enum, so the malformed message lists what the host knows. No new key. |
| Start | The executor's START row dispatches `StartBotForHostCommand`, the command `--start-planned` already uses (P5: no second start path). Its handler gained two answers that serve both callers: the state is judged first (HALTED / AWAITING_RECOVERY get the way back in words; the lifecycle table decides the rest), and the typed-venue refusal names the venue's RECOVERING bots. |
| Verb | `StartBotVerb` in `bot_control_verbs.py`, registered in `BOT_VERBS`; `cli_commands.json` entry (`read_only`, `--confirm-venue`, `--wait`). |

### 3.2 Decisions the records did not settle (the owner may veto)
1. **The recovering-names sentence lives in the host Start handler, not in the verb**, so `--start-planned` gains it too; it only appears when the venue is mainnet, the venue is not typed, and another bot of the venue is RECOVERING. A typed venue followed by a waiting RECOVERING bot is refused by the readiness (`VENUE_RECOVERING`) before anything opens, so the names are an early warning, not the guard.
2. **START is judged before the real-money question.** A HALTED mainnet bot gets the HALTED answer, not `--confirm-venue`, because typing the venue would not make it start.
3. **An older host** reads `start` as a malformed document (the closed set `stop | pause | resume`): audited `malformed`, file removed, nothing executed, the verb exits 1. Stated in the codec, SPEC-015 and the runbook; upgrade the host first.
4. **Delete.** Dropped by the owner's scope change. The applied-plan question it raised (should a host delete drop the bot's entry from `state/bot_plan.json`?) was decided as "no, `bot apply` is the record's one writer" in the parked version; it is open again only if delete returns.

### 3a. Reuse
`StartBotForHostCommand` and handler (reused and extended), `StartBotCommand` / readiness (`occupancy_of`, `venue_recovering` for the names), `BotCommandGate`, `RESUME_PROPOSES_STATES`, `HostControlAction` and the whole processor / inbox / audit / poller / `DirectoryHostControl` chain unchanged, `_ControlVerb`, `control_report`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/host_control.py` | `START` |
| `src/modules/bots/application/use_cases/start_bot_for_host/handler.py` | state gate, HALTED words, RECOVERING names |
| `src/modules/operations/application/host_command_codec.py`, `bot_host_command_executor.py` | the action, the older-host paragraph, the accepted-words row |
| `src/modules/bots/cli/bot_control_verbs.py`, `bot_verbs.py`, `src/config/cli_commands.json` | the verb and its help |
| `src/support/cli_host/exit_code_table.py`, `Docs/OPERATIONS/exit_codes.md` | the verb listed for exits 5, 10, 11 |
| Tests | see §5 |

## 5. Testing
Unit (real chain behind a routing dispatcher): `tests/unit/modules/bots/application/test_bot_start_for_the_host.py`; codec, executor, verbs: `test_host_command_codec.py`, `test_bot_host_command_executor.py`, `test_bot_control_verbs.py`, `test_bot_verbs.py`, `test_command_access.py`. Integration (composed app, fake exchange, Spot and Futures): `test_bot_start_on_the_running_host_on_the_fake_exchange.py`. Process (real host, real second process): `test_control_of_a_running_host_process.py`. The handler tests were mutation-checked (above) and fail for the right reason.

## 6. Docs touched
`Docs/SPEC/SPEC-015_run_the_bots_headless.md` (header, §3a steps 1 and 5, §7 bullet, §8 rows), `Docs/OPERATIONS/headless_runbook.md` (§6 table and "Control one bot", §8 plan-files and multi-venue sections), `Docs/OPERATIONS/exit_codes.md` (generated), `Docs/MODULES/bots/06-runtime.md` (the host-request paragraph: the Start request, its answers, the older host), `Docs/VOCABULARY/README.md` (Host control), the decision record (§4b follow-up), the epic `README.md`, `TRACKING.md`, `Tasks/epics/README.md`. There is no `Docs/MODULES/operations/` folder.

## Implementation notes (written when done)
Decisions are in §3.2. Findings the task text lacked: (1) the host Start already existed (`--start-planned`) with the mainnet question but **no state check**: a HALTED bot reached the readiness and the runner's generic invalid-transition text, so the HALTED words were added in the handler both callers share; (2) the readiness lists everything left, so with a mainnet venue typed and a waiting RECOVERING bot the first refusal in the unit world is the venue's account item, with the recovering sentence inside the same message; the composed app orders them; (3) a process test cannot assert that the exchange saw no request, because the host reads it by itself.
Verification at the checked revision: the files above green; the commit tier is run before the push (`ci-rule.md` §1); the full gate is GitHub Actions' `ci-local.ps1 -Full` on the PR head.

## Resume
Done in the pull request for branch `claude/epic-038k-start-delete-running-host`. A reviewer session is spawned at the push; nothing else is open in this task.
