# EPIC-045 — A bot is added and deleted on the running host, as the Bots tab does

- **Status:** 🟡 Phases 1 and 2 done (A, B, E, F, D); C (`bot apply` beside a host) is next
- **Repositories:** Elite
- **Origin:** the owner, 2026-10-21: "build a mechanism to add a bot and delete a bot at runtime; the UI can do it. Whatever the UI can do at runtime, the VPS must be able to do." (translated; the brief reads "xây cơ chế thêm bot và xoá bot lúc runtime…")
- **North star:** [`Docs/SPEC/SPEC-015_run_the_bots_headless.md`](../../../Docs/SPEC/SPEC-015_run_the_bots_headless.md), [`Docs/OPERATIONS/headless_runbook.md`](../../../Docs/OPERATIONS/headless_runbook.md) §6 and §8
- **Decisions:** [DECISION_2026-10-21_add_and_delete_on_the_running_host.md](DECISION_2026-10-21_add_and_delete_on_the_running_host.md) · [DECISION_2026-10-21_the_host_does_the_four_tab_actions_left.md](DECISION_2026-10-21_the_host_does_the_four_tab_actions_left.md)
- **Dependencies:** [EPIC-038](../EPIC-038_headless_operation/README.md) (the command directory, `J`/`K`/`L`), done

---

## 1. Decisions already made
1. The owner's rule is the epic's standing requirement: **a thing the Bots tab does to a bot, the host does too** ([decision](DECISION_2026-10-21_add_and_delete_on_the_running_host.md) D1). It reverses the 2026-10-17 choice that dropped `bot delete` from `EPIC-038K` (D2).
2. `bot add` and `bot delete` ride the command directory the way `bot edit` does: one `HostControlAction` word each, the Bots tab's own `CreateBotCommand` and `DeleteBotCommand`, the Start/Edit lock (D3, D4).
3. `bot apply` beside a running host is its own slice, after A and B (D5, the owner's word).
4. `run --start-planned` skips an unconfirmed mainnet bot, warns, and runs the rest (D7, slice F, the owner's word).
5. O1 (delete refuses recorded exposure, dust line 10) and O2 (add lands DRAFT) are answered by the owner.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-21) | When the epic is done |
| :--- | :-: | :-: |
| Bots tab actions that change a bot and have a host verb | 5 of 7 (Start, Stop, Pause, Resume, Save); New and Delete have none | all, or an explicit reasoned exclusion. Now (G1): 8 of 9 bot commands have a verb; open: confirm-resume of a HALTED bot, plus Arm and Disarm strategy (`EPIC-045G`, O1 and O2 are the owner's) |
| Host restarts needed to add one bot designed in the desktop app | 1 (every RUNNING bot goes through RECOVERING and a manual resume) | 0 |
| A test that fails when a tab action has no host verb | none | 1 (`D`) |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-045A](completed/EPIC-045A_bot_add_on_the_running_host.md) | `bot add <plan.json> [--name X]`: a plan entry becomes a DRAFT bot on the running host | Elite | None | 🟡 | ✅ Done (2026-10-21, #692) |
| [EPIC-045B](completed/EPIC-045B_bot_delete_on_the_running_host.md) | `bot delete <id>`: a DRAFT or STOPPED bot with nothing left on the exchange is forgotten, under the Start lock | Elite | None | 🟡 | ✅ Done (2026-10-21, #692) |
| [EPIC-045E](completed/EPIC-045E_the_runbook_says_add_then_start.md) | Runbook §6 and §8: export, scp, `bot add`, `bot start`; no restart | Elite | A, B | 🟢 | ✅ Done (2026-10-21, #692) |
| [EPIC-045G](incomplete/EPIC-045G_the_four_tab_actions_the_host_cannot_do_yet.md) | The four Bots tab actions the host cannot do at runtime yet: a DRAFT's venue change, confirm-resume of a HALTED bot, Arm and Disarm strategy; each deletes its exclusion from the parity guard | Elite | D | 🔴 | 🟡 G1 (`bot move`) built; G2, G3 await the owner |
| [EPIC-045C](incomplete/EPIC-045C_bot_apply_beside_a_running_host.md) | `bot apply` (create, edit, prune) through the command directory | Elite | A, B | 🔴 | Planned |
| [EPIC-045F](completed/EPIC-045F_start_planned_skips_an_unconfirmed_mainnet_bot.md) | `run --start-planned` skips a mainnet bot that lacks its confirmation, with a WARNING and an alert, and runs the rest (found on the VPS) | Elite | A, B | 🟡 | ✅ Done (2026-10-21, #694) |
| [EPIC-045D](completed/EPIC-045D_the_tab_and_the_host_cannot_drift.md) | A guard: every Bots tab action that changes a bot maps to a host verb or a reasoned exclusion | Elite | A, B | 🟢 | ✅ Done (2026-10-21) |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1 — A, B, E | An operator adds a bot from a plan file and deletes a DRAFT or STOPPED one with the host running; neither places or cancels an order; the runbook says so | ✅ the unit and integration tests of A and B, green; the `-Full` run on #692's head (run 39607929553) green; the VPS check is the owner's (Not run) |
| 2 — D | A new Bots tab action without a host verb fails CI | ✅ the guard red on its seeded failures (a new command however imported, a stale row, a wrong or undeclared verb, a reasonless exclusion, an unclassified menu command), green on the tree; it records four open gaps (confirm-resume at runtime, DRAFT venue change, Arm and Disarm strategy), slice `EPIC-045G` |
| 3 — C | A plan-file workflow needs no restart | decided in D5; Not started |

## 5. Out of scope
- Starting a bot from `bot add` (a new bot starts only by `bot start <id> --confirm-venue …`).
- Any change to the Bots tab, a dependency, a setting or the Engine.
- Editing `state/bot_plan.json`: `bot add` records no desired state (the runbook says so).

## Notes (newest first)
- **2026-10-21** — #694 merged (F); D built: the parity guard found four gaps it records as exclusions (confirm-resume at runtime, venue change of a DRAFT, Arm and Disarm strategy); slice G closes them.
- **2026-10-21** — #692 merged (A, B, E); F built in its own pull request, which also closes A, B and E.
- **2026-10-21** — the owner accepted O1, O2 and D5 and asked for slice F; review round 1 of #692 made the dust check quote-aware and returned the created id to the operator.
- **2026-10-21** — epic scaffolded from the owner's decision; slices A, B, E delivered together.
