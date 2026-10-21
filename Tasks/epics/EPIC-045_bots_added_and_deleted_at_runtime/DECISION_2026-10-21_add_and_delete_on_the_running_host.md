# ADR — A bot is added and deleted on the running host through the command directory, and the Bots tab's actions are the host's actions

**Epic:** [EPIC-045](README.md)
**Date:** 2026-10-21
**Status:** Accepted
**Decided by:** the owner for D1, D2, D3's landing state, D4/D4a's dust figure, D5 and D7 (quoted below); the author session for the rest under ONBOARDING §7 ("modify code within task scope"), each reversible and touching no dependency, setting or Engine file
**Supersedes / superseded by (optional):** D2 reverses the 2026-10-17 owner choice recorded in [`EPIC-038K`](../EPIC-038_headless_operation/completed/EPIC-038K_start_on_a_running_host.md) and in `headless_runbook.md` §6 ("Delete is not a running-host command")

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at commit `970b77b` (`origin/master-warrior`) |
| 🟢 User decision | decided by the user; quoted, then translated |
| 🤖 Agent decision | delegated and decided under ONBOARDING §7 |

## 1. Context
- ✅ A running host takes `stop`, `pause`, `resume`, `start` and `edit` from `state/control/` (`src/core/contracts/host_control.py` → `HostControlAction`; executor table `src/modules/bots/composition/command_bindings.py` → `_REQUESTS`). Creating or deleting a bot needs `bot apply` (`src/modules/bots/cli/bot_plan_verbs.py` → `ApplyBotPlanVerb`), which exits 3 beside a running host because the host holds the data root's writable lock.
- ✅ So adding one bot designed in the desktop app costs a host restart, which puts every RUNNING bot through RECOVERING and a manual resume.
- ✅ The Bots tab creates with `CreateBotCommand` and deletes with `DeleteBotCommand` (`src/modules/bots/ui/bots_screen/bot_commands.py` → `command_for`, `BotAction.DELETE`); the delete is allowed in DRAFT and STOPPED only (`Bot.require_deletable`) and removes the bot's file (`JsonBotStore.delete`), after a dialog saying "Its definition and its run's record are removed from this computer. Nothing is sent to the exchange."
- ✅ `CreateBotCommandHandler` always saves a DRAFT (`Bot.draft`); no code path creates a bot as STOPPED.
- 🟢 The owner, 2026-10-21: "build a mechanism to add a bot and delete a bot at runtime; the UI can do it. Whatever the UI can do at runtime, the VPS must be able to do."

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | Standing rule: an action of the Bots tab that changes a bot has a host verb, or an explicit, reasoned exclusion in a guard (`EPIC-045D`). | Accepted | 🟢 owner | The tab and the host cannot drift silently again. |
| D2 | `bot delete` returns to scope, on the running host, for a DRAFT or STOPPED bot. | Accepted | 🟢 owner | Reverses the 2026-10-17 choice; the runbook line "Delete is not a running-host command" goes. |
| D3 | `bot add <plan.json> [--name X]` is a new `HostControlAction` word `add`. The plan entry (name, kind, venue, symbol, params) travels in a new optional document key `entry`; the host dispatches the tab's own `CreateBotCommand` under `BotCommandLock`. The bot always lands **DRAFT**, `desired_state` is ignored, nothing is started, `confirmed_venue` must be null. | Accepted | 🤖 agent | One more verb on the proven edit path (`EPIC-038L`); money stays at `bot start --confirm-venue`. The brief said "or STOPPED for a mainnet venue": the Bots tab and `bot apply` create DRAFT on every venue, DRAFT starts exactly like STOPPED, so no second landing state is built. |
| D4 | `bot delete <id>` is `DeleteBotCommand` under `BotCommandLock`, plus one refusal the tab does not make: a bot whose record still shows exposure (a held base, a live order, an order owed) is refused. The kind answers (`IBotKind.exposure_left`, closed by default, like `parameter_problem`). | Accepted | 🤖 agent | Delete stays an unattended act with no confirmation dialog, so the host may not forget a bot that still holds coin. Stricter than the tab: a Spot bot stopped with its coin kept is deleted in the Bots tab, or after `bot start` and `bot stop` selling it. The owner may veto. |
| D4a | The exposure the record shows is valued at the highest price the record holds, and a base worth less than `DUST_QUOTE_VALUE` (10 quote units, **on a symbol quoted in a USD stable coin only**) is let go; any base on another quote (`ETHBTC`), a base with no price to value it by, a live order, an owed order and an open protective stop are never let go. Review round 1 (finding 1) found the figure quote-blind (10 was ten bitcoin on `ETHBTC`) and above Binance Spot's usual minimum order value of 5; the check is now quote-aware. The owner kept the figure at 10 (2026-10-21), knowing that a remainder worth 5 to 10 that a stop could still have sold is let go. | Accepted | 🤖 agent for the mechanism; 🟢 owner for the figure of 10 (2026-10-21) | The fake-exchange journey showed a bot that sold everything it could still holds a sliver the venue will not take (0.000006 BTC), the same dust `exit_dust.py` leaves; refusing on any nonzero base would make no Grid deletable from the VPS. At most 10 quote units are orphaned per delete. The owner may veto or change the figure. |
| D5 | `bot apply` beside a running host is a separate slice (`EPIC-045C`) built after A and B, and sits **beside** `bot add`, not in place of it. | Accepted | 🟢 owner, 2026-10-21 ("bot apply nằm cạnh bot add") | `add` is one entry, small, and unblocks the owner today; `apply` is many entries, edits and prunes, and writes `state/bot_plan.json`, which needs a design of its own (document size, atomicity of a partial apply). |
| D7 | `run --start-planned` skips a planned bot that needs a venue confirmation it was not given (a mainnet bot) instead of exiting 2 before boot: a WARNING log and an alert name `bot start <id> --confirm-venue <venue>`, then the host boots and runs the rest of the plan. Whether the refusal stays fatal when no bot at all could start is decided with the slice (recommendation: never fatal for this reason, because a host with no bot running is harmless and `bot start` / `bot add` then fill it, while the exit leaves every other bot unattended since systemd does not restart exit 2; an unreadable applied plan stays fatal, exit 5). | Accepted | 🟢 owner, 2026-10-21 ("bỏ qua bot đó, cảnh báo, và vẫn chạy các bot còn lại"); the no-bot-at-all case 🤖 built as never fatal, owner may veto | Found on the VPS on 2026-10-21: one unconfirmed mainnet bot left every testnet bot unattended until the owner intervened. Built in `EPIC-045F`; runbook §8's "exit 2 before anything boots" changes with it. |
| D6 | The `entry` crosses a trust boundary and is shaped strictly: name 1–64 characters of letters, digits, space and `_ . : + -`; kind `[a-z0-9_]{1,32}`; venue a venue word; symbol `[A-Z0-9]{1,32}`; params at most `MAX_SETTINGS_PER_EDIT`, each a `ParameterSetting`. The document stays inside `MAX_COMMAND_BYTES`. | Accepted | 🤖 agent | A plan name with a parenthesis is refused by `bot add` in words; rename it in the plan. |

## 3. Alternatives considered
- **A second lock-free write path for `add`** (the CLI writes the bot file itself): rejected; the host owns the data root and a second writer is the failure the lock exists for.
- **Only `bot apply` through the directory** (no `add`): rejected for now; larger (D5), and the owner needs one bot.
- **A confirmation word for delete** (`--confirm`): rejected; the tab asks, but a DRAFT or STOPPED bot with no exposure loses only a definition that a plan file can restore.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Is refusing delete on recorded exposure (D4), with the 10-quote-unit USD-only dust figure (D4a), what the owner wants for a Spot bot stopped with its coin kept? The only routes to a delete are the desktop app (no order) or `bot start` then `bot stop --close-position` (places a live ladder first). **Answered 2026-10-21 by the owner: yes, keep the dust line at 10.** | none | 2026-10-21 |
| O2 | `bot add` lands DRAFT on every venue (D3), not STOPPED on mainnet as the brief said. **Answered 2026-10-21 by the owner: DRAFT always.** | none | 2026-10-21 |
| O2 | `bot add` lands DRAFT on every venue (D3), not STOPPED on mainnet as the brief said: no code path creates a STOPPED bot and a DRAFT starts exactly like one. Confirm, or name the state wanted. | none | 2026-10-21 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [045D](completed/EPIC-045D_the_tab_and_the_host_cannot_drift.md) | Built; PR open | `tests/unit/architecture/test_the_bots_tab_and_the_host_stay_in_step.py` (seeded failures red, tree green); it records three open gaps as reasoned exclusions: a DRAFT's venue change, Arm and Disarm strategy. The `-Full` run is Not yet read |
| D2, D4, D4a | [045B](completed/EPIC-045B_bot_delete_on_the_running_host.md) | Verified (#692) | `tests/unit/modules/bots/application/test_bot_delete_for_the_host.py`, `tests/integration/modules/bots/test_bot_add_and_delete_on_the_running_host_on_the_fake_exchange.py`; the `-Full` run on #692's head 0ec9b44 (run 39607929553) is green, reviewer round 3 PASS |
| D3, D6 | [045A](completed/EPIC-045A_bot_add_on_the_running_host.md) | Verified (#692) | `test_bot_add_for_the_host.py`, `test_host_command_codec_add_delete.py`, the same integration file; the `-Full` run on #692's head 0ec9b44 (run 39607929553) is green, reviewer round 3 PASS |
| D7 | [045F](completed/EPIC-045F_start_planned_skips_an_unconfirmed_mainnet_bot.md) | Verified (#694) | `StartPlannedBots._skip`; `tests/unit/modules/operations/application/test_start_planned_skips_unconfirmed.py`, `tests/integration/modules/alerting/test_a_planned_bot_the_host_skipped_reaches_discord.py`, `tests/integration/modules/bots/test_the_run_hosts_start_up_steps_on_the_fake_exchange.py`, `tests/integration/modules/operations/test_run_command_on_the_composed_app.py`; the `-Full` run 39618180144 on #694's head bba7832 is green, reviewer round 2 PASS. The no-bot-at-all case was built as never fatal (the recommendation in D7); the owner may veto. |
| D5 | [045C](incomplete/EPIC-045C_bot_apply_beside_a_running_host.md) | Not started | Not yet verified |
