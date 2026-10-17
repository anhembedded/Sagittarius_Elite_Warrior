# EPIC-038L — `bot edit` on the running host, through the command directory

**Status:** ✅ Done (2026-10-17) — owner decision of 2026-10-17 (below); the reviewer's verdict is on the pull request
**Branch:** `claude/bot-edit-on-running-host-EPIC-038L`
**Source:** the owner, 2026-10-17, relayed by the coordinator session: the running headless host takes `bot edit <id> --set key=value [--set key=value ...]` through the command directory (EPIC-038J, channel A), next to `bot stop`, `pause`, `resume` and `start`, changing the parameters of ONE bot that is DRAFT or STOPPED, without stopping the host. *Why:* on the owner's VPS `bot start sj9rno` was refused by the existing start guard ("The price 81233 is below the range's lower bound 81305. Starting now would buy about 714.9 USDT of BTC at market, 357% of the capital. Lower the range to include the price"). The fix is to edit `lower`, but `bot apply` needs the data-root lock, which the running host holds, so the owner would have to stop the host, which turns every other RUNNING bot RECOVERING. The owner has several bots running and wants to edit one stopped bot while the others keep trading.
**Risk:** 🔴 — a real-money-adjacent path: an edit places no order, but it decides the range a bot starts with; the money question and the start guard stay at `bot start` and are untouched
**Complexity:** M — one action word and one optional key on a channel that exists; one host handler; one new method on the kind seam
**Epic:** [EPIC-038](../README.md)
**SPEC:** SPEC-015 (header, §3a, §6, §8) is updated.
**Depends on:** 038K (done, merged as PR #565); BUG-224 (the optional-key style of the command file, PR #563).

---

## 1. Context and problem
After 038K the loop is Stop, `start`; the middle step, editing, still needed a stopped host (`bot apply` is a writable boot). The Bots tab's Save is `EditBotCommand`; `bot apply`'s EDIT entry dispatches the same command. The need is that command, reached through the command directory, for one bot.

## 2. Acceptance criteria
- [x] `bot edit <id> --set k=v ...` runs the screen's own `EditBotCommand` once, audits it, and changes that bot and no other; no second edit path (P5). *Evidence:* `test_a_bot_at_rest_is_edited_by_the_screens_own_edit_and_lands_on_draft` (the dispatched command is the screen's); `test_each_action_dispatches_its_contract_command_and_only_that`; `test_the_owners_incident_a_start_refused_for_the_range_is_fixed_by_an_edit` (a bystander RUNNING bot is untouched); composed app: `test_a_stopped_spot_bot_is_edited_and_started_again_while_the_host_keeps_running`.
- [x] Only a DRAFT or STOPPED bot; every other state is refused in words by the lifecycle table, nothing changes. *Evidence:* `test_a_bot_that_is_not_at_rest_is_refused_in_words_and_nothing_changes` (all eight other states), `test_a_bot_that_can_be_stopped_is_told_to_stop_it_first`, `test_a_bot_that_is_already_stopping_is_told_to_wait_not_to_stop_it`; process: a RECOVERING bot is refused with exit 2 and audited `refused`. Mutation: the state gate always true → 16 red.
- [x] The same parameter validation as the Bots tab / `bot apply`; an invalid key or value is refused in words and changes nothing. *Evidence:* `test_an_unknown_key_is_refused_in_words_and_the_stopped_bot_stays_stopped`, `test_a_value_the_kind_cannot_read_is_refused_and_changes_nothing` (ten values), `test_one_bad_setting_among_good_ones_refuses_the_whole_edit`; `test_the_check_agrees_with_the_parser_a_start_uses` (for a complete definition the verdict is exactly `GridParams.from_config`'s: no second rule). Mutations: kind not asked → 14 red; unknown keys accepted → 2 red; the pair not judged → 19 red.
- [x] An edit places no order and needs no `--confirm-venue`, even on mainnet. *Evidence:* `test_a_mainnet_bot_is_edited_without_a_typed_venue_and_nothing_is_opened` (Spot and Futures mainnet: `session.ready_requests == 0`, runner started nothing), `test_a_futures_bot_changes_its_leverage_and_a_mainnet_one_needs_no_typed_venue` (composed app: nothing rests). The codec refuses a `confirmed_venue` on an edit (`test_an_edit_document_that_is_not_exactly_one_is_malformed`).
- [x] Values typed from the strategy's parameter schema, not guessed. *Decision (§3.2):* every parameter is text (`BotDefinition.config: Mapping[str, str]`, as in a plan file), so the verb types nothing; the kind's parser is the schema and judges the text. A Futures bot and a Spot bot are both covered (`test_a_futures_bot_changes_its_leverage_and_direction_as_a_pair`, `test_a_spot_bot_cannot_be_given_a_leverage_without_a_direction`).
- [x] Refuse unknown keys; at most a bounded number of `--set`; the reply shows old -> new. *Evidence:* `MAX_SETTINGS_PER_EDIT = 16`: `test_more_settings_than_the_bound_are_refused`, the verb's `test_a_set_that_is_not_sound_is_a_usage_error_and_asks_the_host_nothing`, the codec's bound case; `test_the_reply_shows_each_change_as_old_to_new_and_the_plan_reminder`, `test_a_parameter_the_bot_never_held_is_shown_as_unset`, process test `"lower 48000 -> 47000"` from a real host.
- [x] The command file stays `sew.host-command/1`, backward compatible; what an older host does is stated; size and key shape are tight. *Evidence:* `test_an_edit_adds_a_new_key_and_a_new_word_so_an_older_host_refuses_it_unread`, `test_every_other_action_is_still_the_document_an_older_host_reads` (`set` only for an edit), `test_the_largest_edit_fits_the_commands_size_limit` (under `MAX_COMMAND_BYTES`), `test_a_malformed_setting_is_refused_without_repeating_its_value`, `test_parameter_setting.py` (shapes). Mutations: edit may name a venue → 1 red; `set` on any action → 2 red; bound lifted → 1 red; an edit without `set` → 1 red.
- [x] Concurrency: under the existing bot command lock, so it cannot race a start. *Evidence:* `test_the_edit_is_made_under_the_command_lock_a_start_holds` (the lock is held when the screen's edit saves), `test_a_refusal_releases_the_lock_for_the_next_command`. Mutation: no lock → 1 red.
- [x] The plan file: decided, recorded, and in the runbook and the verb's help. *Decision (§3.2):* `bot edit` does not write `state/bot_plan.json`; *evidence:* `test_the_help_of_edit_tells_the_operator_the_plan_file_is_theirs_to_update`; runbook §6 and §8.
- [x] The registry guards list the verb as `start` was. *Evidence:* `test_the_verbs_are_a_table_not_a_chain`, `test_the_verbs_are_registered_under_the_words_the_operator_types`, `test_command_access.py` (`("bot","edit")` read-only), the generated `exit_codes.md`, `test_the_shipped_declaration_parses_repeated_sets_in_order`.
- [ ] **Not run:** Windows; any exchange but the fake; a real `bot start` after a real `bot edit` in a child-process host (the composed app proves the start after the edit; the process test proves the edit across the boundary).

## 3. Design

### 3.1 What is built
| Piece | Decision |
| :--- | :--- |
| Wire | `HostControlAction.EDIT` (`edit`) and the optional key `set`: an object of 1 to 16 text pairs, present only for an edit (`ParameterSetting`, `MAX_SETTINGS_PER_EDIT` in `core/contracts/parameter_setting.py`). |
| Host handler | `EditBotForHostCommandHandler`: under `BotCommandLock`, lifecycle table (`permits_edit`) → sound set → the kind's `parameter_problem` → something changes → the screen's `EditBotCommand`; the reply is `key old -> new` plus the plan reminder. |
| Kind seam | `IBotKind.parameter_problem(config, changed)`, concrete and closed by default (a kind that declares nothing is edited by no command line; no implementer changes, `BUG-026`). The Grid answers by building a probe from a neutral Grid plus the changed keys and asking `GridParams.from_config`. |
| Verb | `EditBotVerb` in `bot_control_verbs.py` (a `_request_of` hook on `_ControlVerb`), registered in `BOT_VERBS`; `cli_commands.json` entry (`read_only`, repeatable `--set` with a `metavar`, `--wait`). `cli_parser.py` passes `metavar` on. |

### 3.2 Decisions the owner's text left to this session (the owner may veto)
1. **Values are text, judged by the kind.** The brief asked to type values "from the strategy's parameter schema rather than guessing". A bot's parameters are `Mapping[str, str]` by design ("a float never touches a price"); a Grid reads them with its own parsers. There is no separate schema to type from, so `--set` carries text, as a plan file does, and `IBotKind.parameter_problem` judges it. Booleans do not exist as Grid parameters (`on_range_exit` is `hold | close`).
2. **The applied record is not updated.** `state/bot_plan.json` holds a desired state per bot and no parameters, so there is nothing to update in it; the plan file is the owner's. The runbook and the verb's help say: after `bot edit`, change the same value in `plan.json`, or the next `bot apply` of the old plan edits the bot back (an EDIT entry lands it on DRAFT again).
3. **A set that changes nothing is refused.** An edit lands a STOPPED bot on DRAFT; doing that for no change would be a surprising side effect.
4. **Only the changed keys are judged.** A key the bot already held (a legacy or blank one) is not this edit's doing; the other end of `lower`/`upper` and the `direction`/`leverage` pair are judged with a change to either, because that is what the change is judged against.
5. **No `--confirm-venue`, and the codec refuses one on an edit.** An edit places no order; accepting a typed venue would suggest it was needed.
6. **"On the bot's own executor".** A bot at rest has no executor and no worker, so there is no queue to run on; the write is the one the Save makes, on the host's command thread, serialized with a Start by `BotCommandLock`. The screen's Save does not take that lock; whether that matters on the screen was not examined here and is out of scope.
7. **Older host:** `edit` is an unknown word and `set` an unknown key; it reads the document as malformed, audits it, and does nothing (exit 1).

### 3a. Reuse
`EditBotCommand` / `EditBotCommandHandler` (reused unchanged), `permits_edit`, `BotLookup`, `BotCommandLock`, `IBotKindCatalog`, `GridParams.from_config`, `HostControlAction` and the whole processor / inbox / audit / poller / `DirectoryHostControl` chain, `_ControlVerb`, `control_report`, `render_exit_codes.py`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/parameter_setting.py` (new), `host_control.py` | `ParameterSetting`, the bound, `EDIT`, `HostControlRequest.settings` |
| `src/modules/bots/application/use_cases/edit_bot_for_host/` (new), `contracts/host_bot_requests.py`, `composition/command_bindings.py` | the host handler, its command, its binding |
| `src/modules/bots/contracts/i_bot_kind.py`, `domain/grid/grid_kind.py`, `domain/grid/grid_parameter_check.py` (new) | the kind seam and the Grid's answer |
| `src/modules/operations/contracts/host_command.py`, `application/host_command_codec.py`, `application/bot_host_command_executor.py`, `adapters/directory_host_control.py` | the key, the codec, the executor row, the request |
| `src/modules/bots/cli/bot_control_verbs.py`, `bot_verbs.py`, `src/config/cli_commands.json`, `src/presentation/cli/cli_parser.py` | the verb, its help, `metavar` |
| `src/support/cli_host/exit_code_table.py`, `Docs/OPERATIONS/exit_codes.md` | the verb listed for exits 5, 10, 11 |
| Tests | see §5 |

## 5. Testing
Unit (real chain behind a routing dispatcher, `edit_host_world.py`): `test_bot_edit_for_the_host.py`, `test_bot_edit_for_the_host_validation.py`; the Grid's judgement: `test_grid_parameter_check.py`; contract: `test_parameter_setting.py`; codec, executor, verbs, parser: `test_host_command_codec.py`, `test_bot_host_command_executor.py`, `test_bot_control_verbs.py`, `test_bot_verbs.py`, `test_cli_parser.py`, `test_command_access.py`. Integration (composed app, fake exchange, Spot and Futures): `test_bot_edit_on_the_running_host_on_the_fake_exchange.py` (the operator helpers moved to `host_control_world.py`, shared with the 038K test). Process (real host, real second process): `test_control_of_a_running_host_process.py`. Mutation-checked: the state gate, the kind's judgement, the lock, the no-op refusal, repeated keys, unknown keys, the pair rule, and four codec rules; each went red.

## 6. Docs touched
`Docs/SPEC/SPEC-015_run_the_bots_headless.md` (header, §3a steps 1 and 5, §6 bullet, §8 rows), `Docs/OPERATIONS/headless_runbook.md` (§6 table and "Control one bot", §8 plan-files), `Docs/OPERATIONS/exit_codes.md` (generated), `Docs/MODULES/bots/06-runtime.md` (the host-request paragraph), `Docs/VOCABULARY/README.md` (Host control), the decision record (fourth follow-up), the epic `README.md`, `TRACKING.md`, `Tasks/epics/README.md`.

## Implementation notes (written when done)
Decisions are in §3.2. Findings the brief lacked: (1) `EditBotCommandHandler` judges no parameter at all (it only builds a `BotDefinition`; a kind's `validate` runs when a bot starts), so "the same validation as the Bots tab" is the screen's form plus the start's `validate`; the host edit therefore needed a kind-level offline judgement, which is the new `parameter_problem`; (2) the Grid's parameter parsing is already one function, so the probe approach reuses it instead of copying its rules (a parity test locks that); (3) `grid_params.py` was at 342 lines, so the check is its own file; (4) the executor used a fixed sentence for every accepted command; an edit's reply must name what changed, so `BotCommandResult.message` wins when the host handler sets one (only the edit does).
Verification at the checked revision: the unit, integration and process tests above green; the commit tier (`ci-local.ps1 -SkipTests`) green; the full gate is GitHub Actions' `ci-local.ps1 -Full` on the PR head.

## Resume
Done in the pull request for branch `claude/bot-edit-on-running-host-EPIC-038L`. A reviewer session is spawned at the push; nothing else is open in this task.
