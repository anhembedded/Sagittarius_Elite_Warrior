# ADR — The host does the four Bots tab actions it cannot yet do, one verb each

**Epic:** [EPIC-045](README.md)
**Date:** 2026-10-21
**Status:** Accepted for G1; G2 and G3 Proposed (real money, the owner decides)
**Decided by:** the owner's rule of 2026-10-21 ("whatever the UI can do at runtime, the VPS must be able to do", recorded in `Tasks/COORDINATION.md`) for the four verbs; the author session for G1's shape under ONBOARDING §7 (no real money, reversible); the owner for G2 and G3 (pending)
**Supersedes / superseded by (optional):** closes the four `OPEN GAP` rows of [EPIC-045D](completed/EPIC-045D_the_tab_and_the_host_cannot_drift.md)'s guard

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at commit `35354c0` |
| 🟢 User decision | decided by the user |
| 🤖 Agent decision | delegated and decided under ONBOARDING §7 |
| 🔵 Proposed | an option awaiting a decision |

## 1. Context
- ✅ The parity guard (`tests/unit/architecture/test_the_bots_tab_and_the_host_stay_in_step.py`) lists four tab actions with no single host verb: (G1) a DRAFT's **venue change** (`ChangeBotVenueCommand`); (G2) **confirm-resume** of a HALTED bot (`ConfirmBotResumeCommand`), which only `run --resume-halted` answers, at host start; (G3) **Arm strategy** and (G4) **Disarm strategy**, the trading module's armed-strategy controls.
- ✅ The venue change is `Bot.moved_to`: only a Spot DRAFT that never ran, between Spot venues; `ChangeBotVenueCommandHandler` saves it with no order and no confirmation (the money question is at Start).
- 🟢 The coordinator: "Delete+add is not parity", and an arm on a mainnet venue needs `--confirm-venue`.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| G1 | The venue change is a new verb `bot move <id> --venue <venue>`: a `move` action word and a `to_venue` document key, dispatching the tab's own `ChangeBotVenueCommand` under `BotCommandLock`, with one refusal the tab does not make (a bot of the same name already on the target venue, because a plan's identity is name and venue). | Accepted | 🤖 agent | Built in the first pull request of slice G. No real money: a move places no order and asks no venue, as on the tab. Delete-and-add made a new bot id; this keeps the id. |
| G2 | Confirm-resume at runtime: a verb that confirms a HALTED or AWAITING_RECOVERY bot's resume on a running host. Shape not decided: see O1. | Proposed | 🔵 | Decided with the owner: it lets a ladder be confirmed that a person has read. |
| G3 | Arm and disarm a strategy at runtime through the command directory, reusing the tab's arm and disarm use cases; an arm on a mainnet venue needs `--confirm-venue`. Shape not decided: see O2. | Proposed | 🔵 | Decided with the owner: it arms real-money trading headless. |

## 3. Alternatives considered (G1)
- **`bot edit <id> --set venue=<venue>`** (the coordinator's first suggestion): rejected. The edit path treats the venue as unchangeable (`edit_bot_for_host/handler.py` docstring: "the unchangeable kind, venue and symbol"), merges settings into the bot's kind parameters and asks the kind whether each key is one (`IBotKind.parameter_problem`), and its lifecycle allows a STOPPED bot, while a move needs a DRAFT that never ran. Folding the two would put two lifecycle rules behind one verb and special-case one key in the edit handler.
- **Delete then add:** rejected by the coordinator (a new id, and it needs a plan file).
- **A `venue` field on every command:** rejected; one new key, `to_venue`, only a move may carry.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | **Confirm-resume on a running host (G2).** The tab shows a person the proposed ladder, then confirms. Options: (a) `bot resume <id>` also accepts a HALTED bot, proposes, and a second command `bot confirm-resume <id>` confirms (the operator reads the proposal in between); (b) one verb `bot resume <id> --confirm` that takes the proposal as shown without reading it (the `--resume-halted` flag already does this at start); (c) leave `run --resume-halted` as the only way and accept a restart. Recommendation: (a), because decision D13 says a person reads the ladder. | G2 | 2026-10-21 |
| O2 | **Arm and disarm at runtime (G3).** Arm takes the strategy's parameters and a venue; real money on mainnet. Options: (a) `strategy arm <venue> ...` and `strategy disarm <venue>` verbs of the command directory, mainnet needing `--confirm-venue`; (b) none: arming stays a desktop act and the exclusion stays, recorded as a reasoned decision. Recommendation: (a), parameters from a saved arming (`armed_strategy_config`), not typed on a command line. | G3 | 2026-10-21 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| G1 | [045G](incomplete/EPIC-045G_the_four_tab_actions_the_host_cannot_do_yet.md) | Built; PR open | `tests/unit/modules/bots/application/test_bot_move_for_the_host.py`, `tests/integration/modules/bots/test_bot_move_on_the_running_host_on_the_fake_exchange.py`, the guard row now a `HostVerb`; the `-Full` run is Not yet read |
| G2, G3 | [045G](incomplete/EPIC-045G_the_four_tab_actions_the_host_cannot_do_yet.md) | Not started | Not yet verified |
