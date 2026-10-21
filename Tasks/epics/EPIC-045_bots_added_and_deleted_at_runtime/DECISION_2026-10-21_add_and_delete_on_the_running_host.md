# ADR — A bot is added and deleted on the running host through the command directory, and the Bots tab's actions are the host's actions

**Epic:** [EPIC-045](README.md)
**Date:** 2026-10-21
**Status:** Accepted
**Decided by:** the owner for D1 and D2 (quoted below); the author session for D3–D6 under ONBOARDING §7 ("modify code within task scope"), each reversible and touching no dependency, setting or Engine file
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
| D4a | The exposure the record shows is valued at the highest price the record holds, and a base worth less than `DUST_QUOTE_VALUE` (10 quote units) is let go; a base with no price to value it by, a live order, an owed order and an open protective stop are never let go. | Accepted | 🤖 agent | The fake-exchange journey showed a bot that sold everything it could still holds a sliver the venue will not take (0.000006 BTC), the same dust `exit_dust.py` leaves; refusing on any nonzero base would make no Grid deletable from the VPS. At most 10 quote units are orphaned per delete. The owner may veto or change the figure. |
| D5 | `bot apply` beside a running host is a separate slice (`EPIC-045C`) built after A and B, and sits **beside** `bot add`, not in place of it. | Accepted | 🤖 agent | `add` is one entry, small, and unblocks the owner today; `apply` is many entries, edits and prunes, and writes `state/bot_plan.json`, which needs a design of its own (document size, atomicity of a partial apply). |
| D6 | The `entry` crosses a trust boundary and is shaped strictly: name 1–64 characters of letters, digits, space and `_ . : + -`; kind `[a-z0-9_]{1,32}`; venue a venue word; symbol `[A-Z0-9]{1,32}`; params at most `MAX_SETTINGS_PER_EDIT`, each a `ParameterSetting`. The document stays inside `MAX_COMMAND_BYTES`. | Accepted | 🤖 agent | A plan name with a parenthesis is refused by `bot add` in words; rename it in the plan. |

## 3. Alternatives considered
- **A second lock-free write path for `add`** (the CLI writes the bot file itself): rejected; the host owns the data root and a second writer is the failure the lock exists for.
- **Only `bot apply` through the directory** (no `add`): rejected for now; larger (D5), and the owner needs one bot.
- **A confirmation word for delete** (`--confirm`): rejected; the tab asks, but a DRAFT or STOPPED bot with no exposure loses only a definition that a plan file can restore.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Is refusing delete on recorded exposure (D4), with the 10-quote-unit dust figure (D4a), what the owner wants for a Spot bot stopped with its coin kept? | none | 2026-10-21 |
| O2 | `bot add` lands DRAFT on every venue (D3), not STOPPED on mainnet as the brief said: no code path creates a STOPPED bot and a DRAFT starts exactly like one. Confirm, or name the state wanted. | none | 2026-10-21 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [045D](incomplete/EPIC-045D_the_tab_and_the_host_cannot_drift.md) | Not started | Not yet verified |
| D2, D4, D4a | [045B](incomplete/EPIC-045B_bot_delete_on_the_running_host.md) | Built; PR open | `tests/unit/modules/bots/application/test_bot_delete_for_the_host.py`, `tests/integration/modules/bots/test_bot_add_and_delete_on_the_running_host_on_the_fake_exchange.py`; the `-Full` run on the PR head is Not yet read |
| D3, D6 | [045A](incomplete/EPIC-045A_bot_add_on_the_running_host.md) | Built; PR open | `test_bot_add_for_the_host.py`, `test_host_command_codec_add_delete.py`, the same integration file; the `-Full` run is Not yet read |
| D5 | [045C](incomplete/EPIC-045C_bot_apply_beside_a_running_host.md) | Not started | Not yet verified |
