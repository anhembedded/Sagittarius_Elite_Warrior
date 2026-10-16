# EPIC-041J — A module's design is one arc42 folder, `alerting` is its pilot, and every change to a documented module answers for its design on the pull request

**Status:** ✅ Done (2026-10-16)
**Source:** The owner, 2026-10-16, relayed by the coordinator session: *"1. co / 2. dung / 3. ve tay theo high level. chu y la cac rule phai cap nhat khi change code hay fix bug thi can nhac update design"* ("1. yes / 2. right / 3. drawn by hand at a high level. Note: the rules must be updated so that changing code or fixing a bug makes the author consider updating the design")
**Risk:** 🟡 — a new CI step on every pull request; rules every session loads change
**Complexity:** M — one template, one migrated document, one stdlib script with its tests, four rule clauses
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041A](EPIC-041A_docs_skeleton.md) (done)

---

## 1. Context and problem
- `Docs/MODULES/alerting.md` (330 lines, seven views plus the skeleton) was one file every `EPIC-036` task edits; 11 of its 139 citations were wrong on `455dec2`, the commit that last rewrote it.
- The only clause tying code to the module document was `task-execution-rule.md`'s, tagged `[review: K4; eye]`; a bug fix had none. The reasons and the owner's decision: [`DECISION_2026-10-16_module_docs_one_folder_arc42.md`](../DECISION_2026-10-16_module_docs_one_folder_arc42.md).

## 2. Acceptance criteria
- [x] The decision record supersedes the 2026-10-14 D3 (module documents) and D4 (design diagrams) in part, with its Constitution check; the old record marks the superseded parts.
- [x] `Docs/MODULES/README.md` is the folder template: fixed arc42 numbers, the required core, diagrams by hand, tables generated.
- [x] `Docs/MODULES/alerting/` holds the same facts as `alerting.md`, every citation re-verified; the old file is gone and no link points to it.
- [x] A pull request changing `src/modules/<m>/` for a documented module fails CI unless it changes `Docs/MODULES/<m>/` or writes `No design change: <reason>` under `## Design`; a module without a folder is not checked.
- [x] The rule is stated once (`commit-rule.md` §1) and cited by `task-execution-rule.md`, `fix-bug-rule.md` §6.2 and `architecture-rule.md` §7.4; the PR template has a `## Design` section; the rubric has K10 and the count reads 111.
- [x] `EPIC-041E` builds `bots` in the folder layout.

## 3. Design
arc42's published order (P5) with one named deviation (`state-machines.md`, which arc42 has no section for). The check mirrors `scripts/check_fix_pr_body.py` and reuses its section parser (`sections`), so a PR body is read one way. Changed paths come from `git diff --name-only base...head`: three dots, so a commit landing on the base after the fork is not the pull request's.

## 3a. Reuse
- PR-body checking: `scripts/check_fix_pr_body.py` — used `sections` (renamed from `_sections`), and its workflow, `commit-lint.yml`.
- The landmark import of the package: `scripts/check_skill_prompt_references.py` — used the same block.
- `None: no UI or application need` otherwise; no `src/` behaviour changes.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `DECISION_2026-10-16_module_docs_one_folder_arc42.md`, `DECISION_2026-10-14_documentation_philosophy.md` | New record; superseded parts marked |
| `Docs/MODULES/README.md` | The folder template |
| `Docs/MODULES/alerting/` (`README.md`, 03–10, `state-machines.md`, eight `.puml`, split one question each) | The migrated design; `Docs/MODULES/alerting.md` deleted |
| `scripts/check_design_in_step.py`, `tests/unit/scripts/test_check_design_in_step.py` | The check and its probes |
| `scripts/check_fix_pr_body.py` | `_sections` → `sections`, shared |
| `.github/workflows/commit-lint.yml`, `scripts/rule_integrity/tags.py` | The step; the `design pr body` gate tag |
| `commit-rule.md`, `task-execution-rule.md`, `fix-bug-rule.md`, `architecture-rule.md` | The clause and its citations |
| `.github/PULL_REQUEST_TEMPLATE.md`, `.claude/templates/task.md`, `Docs/README.md` | `## Design`; the folder path |
| rubric, `pr-review/SKILL.md`, `reviewer.md`, `ONBOARDING.md` | K10; 110 → 111 |
| `EPIC-036` files, `Tasks/epics/README.md`, `src/modules/alerting/module.py` (docstring) | Links to the folder |

## 5. Testing
Unit tier: `tests/unit/scripts/test_check_design_in_step.py`, `test_check_fix_pr_body.py`, `tests/unit/scripts/rule_integrity/`; the commit tier; `python3 scripts/check_skill_prompt_references.py`; every `.puml` passes `plantuml -checkonly`. Kind of pull request: code (a script, a workflow step, rules).

## 6. Docs touched
`Docs/MODULES/README.md`, `Docs/MODULES/alerting/` (new; replaces `alerting.md`), `Docs/README.md` ("Writing a document").

## Implementation notes (written when done)
- The 11 wrong citations, corrected in the move: `BotAlertSource` `:86` → `:95`, `ALERT_ON_ENTRY` `:73-76` → `:82-84`, `on_stop_gave_up` `:129-142` → `:140-153`, `CLEARED_ON_ENTRY` `:78-84` → `:86-92`, the entry-only compare `:113-127` → `:122-138` (twice), `seed` `:99-111` → `:108-120`, `CHANNEL_DESCRIPTORS` `:31-55` → `:91-93`, `discord_channel` `:65-85` → `:65-88`, the catalog skip `:93-109` → `:96-112`, `NullAlertPublisher` `:97-104` → `:132-139`, `discord_payload` `:53` → `:54`.
- Where the old views went: 1 → `03-context.md`; 2 → `05-building-blocks.md`; 3 → `state-machines.md`; 4 and the skeleton's journey → `06-runtime.md` (the mermaid diagram redrawn as `diagrams/06-halt-to-discord.puml`); 5 → `08-concepts.md`; 6 → `07-deployment.md`; 7 → `10-quality.md`; §8's strategy, real-and-stand-in table and proof → `04-solution-strategy.md`. The design records of the old preamble → `09-decisions.md`.
- The script runs bare on the runner, whose checkout is named `Sagittarius_Elite_Warrior` (`ci.yml`), so the landmark import resolves there as locally.
- Verification evidence (commands and the CI run) is recorded on the pull request.
