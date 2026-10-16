# ADR — A module's design is one folder in arc42's order, drawn by hand at a high level, and every change to the module's code answers for it

**Epic:** [EPIC-041](README.md)
**Date:** 2026-10-16
**Status:** Accepted; the `file:line` form of citation in module designs superseded on 2026-10-16
**Decided by:** the owner, on three questions the coordinator session put on 2026-10-16, relayed to this session: *"1. co / 2. dung / 3. ve tay theo high level. chu y la cac rule phai cap nhat khi change code hay fix bug thi can nhac update design"* ("1. yes / 2. right / 3. drawn by hand at a high level. Note: the rules must be updated so that changing code or fixing a bug makes the author consider updating the design"). On splitting diagrams the owner added, the same day: *"so do nao phuc tap, nhieu component thi nen tach ra nhe"* ("a diagram that is complex, with many components, should be split"). The questions were: (1) replace "one file per module" with one folder per module laid out arc42-style; (2) pilot on `alerting` first, then `bots`; (3) how diagrams are made. The file set and the mechanism are the agent's, under ONBOARDING §7.
**Supersedes / superseded by (optional):** supersedes in part [`DECISION_2026-10-14_documentation_philosophy.md`](DECISION_2026-10-14_documentation_philosophy.md): D3 for module documents (their location and file naming) and D4 for diagrams of design (no generated class diagram). D2 stands; D3 for application documents, D4 for tables, and D8 stand. Superseded in part by [`DECISION_2026-10-16_cite_code_by_symbol.md`](DECISION_2026-10-16_cite_code_by_symbol.md): module designs cite code by path and symbol, not `file:line` (D2's template, D4's migration), and D5's clause no longer lists a `file:line` citation among the facts kept in step.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |

## 1. Context
✅ Measured on `455dec2`:
- **One file had outgrown itself.** `Docs/MODULES/alerting.md` was 330 lines in seven numbered views plus an eighth section for the walking skeleton. A reader who wanted the timing table or the thread model scrolled past the components; a task that changed one view rewrote a file that every other `EPIC-036` task also edits.
- **The view numbers were the repository's own.** "View 3" meant state machines here and "solution strategy" in arc42, the template every reviewer and every outside reference uses. The 2026-10-14 record (D3) named files by question to avoid arc42 numbers *because unused sections would be dropped*; with fixed numbers that keep their place when a section is left out, the objection falls (§3).
- **Nothing tied a code change to the design.** `task-execution-rule.md` said a task that changes a module's shape updates its document, tagged `[review: K4; eye]`: a reviewer's or the author's memory. Rubric K4 names `Docs/HLD/`, not `Docs/MODULES/`. A bug fix carried no such clause at all. 11 of the 139 `file:line` citations in `alerting.md` were already wrong on the commit that last rewrote it, `455dec2` (`bot_alert_source.py` off by 9 lines, three composition ranges, one blank line), found by re-verifying them for this record: a design written beside the code still drifts when nothing asks.
- **What already held a pull request's body:** `scripts/check_fix_pr_body.py`, run by `.github/workflows/commit-lint.yml` on every `pull_request` event, with its `[gate: fix pr body]` tag checked by `scripts/rule_integrity/tags.py`.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **One folder per module, in arc42's order.** A module's design is `Docs/MODULES/<module>/`, never inside `src/`. Its files carry arc42's section numbers, which are **fixed**: a section with no content is left out and the files after it keep their numbers. Supersedes the 2026-10-14 D3 for module documents (`Docs/MODULES/<module>.md`; "files are named by the reader's question, not by arc42 section numbers"). Application documents keep D3's naming | Accepted | 🟢 the owner (*"1. co"*) | A reader finds §5 in every module at the same name. A task edits the one file its change concerns |
| D2 | **The file set.** `README.md` (one screen: reader, question, reader map, Built/Planned), `01-goals-use-cases.md`, `02-constraints.md`, `03-context.md`, `04-solution-strategy.md`, `05-building-blocks.md`, `06-runtime.md`, `07-deployment.md`, `08-concepts.md`, `09-decisions.md`, `10-quality.md`, `11-risks-debt.md`, `state-machines.md` and `diagrams/*.puml`. Required: `README.md`, 03, 05, 06, 07, 09; the rest when they have something to say (2026-10-14 D7). The old "data model" view goes to `08-concepts.md` (arc42 §8 lists the domain model and persistence among its concepts); the old "timing" view goes to `10-quality.md` with the quality scenarios; `state-machines.md` has no arc42 number because arc42 has no section for it. Use cases are linked to `Docs/SPEC/`, terms to `Docs/VOCABULARY/`, decisions indexed in `09-decisions.md`: never copied (P3). The template is `Docs/MODULES/README.md` | Accepted | 🤖 agent, under P3 and P5 (arc42 as published, the one deviation named) | Six required files make a small module small; the reader map in `README.md` keeps the folder navigable |
| D3 | **Diagrams by hand, at a high level.** A diagram is drawn by hand in PlantUML (2026-10-14 D8), in the module's `diagrams/`, named `<arc42 number>-<what it shows>.puml`, and answers one stated question. Components, ports and arrows; the class diagrams of `05-building-blocks.md` hold the domain types and the contracts only. **A complex diagram is split:** more than about seven boxes, or two journeys or questions in one picture, becomes several diagrams, one question each. A class diagram is never generated from code. Tables stay generated (2026-10-14 D4): a state machine's transition table and the timing table are the code's own data | Accepted | 🟢 the owner (*"3. ve tay theo high level"*; then *"so do nao phuc tap, nhieu component thi nen tach ra nhe"*, "a diagram that is complex, with many components, should be split") · 🤖 agent (the seven-box threshold; where tables stay generated) | A picture shows what the code cannot; a generated table cannot drift |
| D4 | **Pilot on `alerting`, then `bots`.** `Docs/MODULES/alerting.md` moves to `Docs/MODULES/alerting/` with the same facts, every citation re-verified; `EPIC-041E` builds `bots` in the folder layout | Accepted | 🟢 the owner (*"2. dung"*) | The layout is proven on a module that is half built and half planned before the largest module uses it |
| D5 | **Every code change answers for the design, by mechanism.** A pull request that changes `src/modules/<m>/` for a module that has `Docs/MODULES/<m>/` changes that folder too, or writes `No design change: <reason>` under its `## Design` section. The clause lives once, in `commit-rule.md` §1 ("Design in step"), which loads every session; `task-execution-rule.md`, `fix-bug-rule.md` and `architecture-rule.md` (which loads with every source file) cite it. `scripts/check_design_in_step.py` holds it on every `pull_request` event, beside `check_fix_pr_body.py`; review check K10 judges whether the answer is true | Accepted | 🟢 the owner (*"cac rule phai cap nhat khi change code hay fix bug thi can nhac update design"*) · 🤖 agent (the mechanism, mirroring `check_fix_pr_body.py`) | The question is asked on every change, by the gate, instead of remembered. The check holds that the question was answered, not that the answer is right: that is K10 |

## 2a. Constitution check
| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | `scripts/check_design_in_step.py` in `commit-lint.yml`; `tests/unit/scripts/test_check_design_in_step.py` goes red when the check is weakened; `[gate: design pr body]` is checked by `rule_integrity` |
| P2 Verify, don't restate | ✅ | Every citation in the moved document was re-verified against `455dec2`; the 11 that were wrong are corrected, no claim added |
| P3 A copy drifts | ✅ | The rule is stated once (`commit-rule.md` §1) and cited elsewhere; the section parser is `check_fix_pr_body.sections`, imported rather than copied; the old file is deleted, not kept beside the folder |
| P4 Green proves only what was tested | ✅ | The check proves an answer was given; K10 is the reviewer's check of its truth, and the record says so |
| P5 Apply before you invent | ✅ | arc42's published section order; the repository's existing PR-body gate as the model |
| P6 Fix the mechanism | ✅ | The drift came from nothing asking; the fix asks on every pull request, not in one document |
| P7 Seam now, variant later | ✅ | One module migrated; the rest each in their own task |
| P8 Ratchets only fall | ✅ | A new check is added; nothing is loosened. The rubric grows to 111 IDs |
| P9 Decide alone | ✅ | The owner answered the three questions; the file set and the mechanism are decided here |
| P10 Pyramid and units | ✅ | The decision is the title; counts are measured (139 citations, 11 drifted) |
| P11 Prompt-grade artifacts | ✅ | The template states required files and their questions; the rule clause is imperative and tagged |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | Documents, one stdlib script, one workflow step; removing the step and the clause undoes it |

## 3. Alternatives considered
- **Keep one file per module, with the 2026-10-14 question-named views.** Rejected by the owner (D1). It also kept the one-file conflict between tasks of the same epic.
- **Number files only for the sections present (renumber when one is dropped).** Rejected: the 2026-10-14 record's own objection to arc42 numbers. Fixed numbers keep a file's name stable across modules and across time.
- **A separate `data-model.md`.** Rejected: arc42 §8 already holds the domain model and persistence; an unnumbered file is kept only for the state machines, which arc42 has no place for.
- **Generated class and component diagrams (pyreverse, py2puml).** Rejected by the owner (D3): a picture of every class answers no question a reader asks.
- **A review row only, with no check.** Rejected: that is the memory P1 forbids, and the clause it would replace was already `[review: K4; eye]`.
- **Require the design folder on every change to the module, with no waiver.** Rejected: most changes (a log line, a test helper, a rename inside a class) leave the design true; a forced edit would teach authors to touch the folder without reading it. The waiver must carry a reason a reviewer can check (K10).

## 4. Open questions
None.

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1, D2, D3 | [EPIC-041J](completed/EPIC-041J_module_folder_layout_and_design_in_step.md) | Verified | `Docs/MODULES/README.md` (the template); `Docs/MODULES/alerting/` |
| D4 | EPIC-041J (alerting); [EPIC-041E](incomplete/EPIC-041E_bots_module_doc.md) (bots) | In progress | `Docs/MODULES/alerting/`; `bots` not started |
| D5 | EPIC-041J | Verified | `commit-rule.md` §1; `scripts/check_design_in_step.py`; `tests/unit/scripts/test_check_design_in_step.py`; rubric K10 |
