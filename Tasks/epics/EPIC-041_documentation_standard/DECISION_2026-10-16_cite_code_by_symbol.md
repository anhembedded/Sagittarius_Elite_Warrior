# ADR — A design cites code by path and symbol, never by line; a point-in-time record may cite a line, at a named commit

**Epic:** [EPIC-041](README.md)
**Date:** 2026-10-16
**Status:** Accepted
**Decided by:** the owner, relayed by the coordinator session on 2026-10-16. On the citation `alerting/composition/channel_bindings.py:91-93` the owner wrote: *"\"alerting/composition/channel_bindings.py:91-93\" với doc đâu cần link kiểu này nhỉ? link kiểu này code change thì update doc nhiều quá"* ("a doc does not need links like this, does it? With links like this, every code change means many doc updates"). The coordinator proposed the policy below; the owner answered *"ok chốt hết theo đề xuất"* ("ok, settle all of it as proposed"). The citation form, the guard's mechanism and its scope are the agent's, under ONBOARDING §7.
**Supersedes / superseded by:** supersedes in part [`DECISION_2026-10-16_module_docs_one_folder_arc42.md`](DECISION_2026-10-16_module_docs_one_folder_arc42.md): the `file:line` form of citation its D2 template and D4 migration used, and "a `file:line` citation" among the facts D5's clause keeps in step. Everything else in it stands.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at the commit named in §1; cited as `file:line` there |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |

## 1. Context
✅ Measured on `30a75f9`:
- **Line citations rot within a day.** `EPIC-041J` re-verified the 139 `file:line` citations of `alerting.md` on `455dec2` and found 11 wrong. On `30a75f9`, two pull requests later, the `alerting/` folder held 163 line citations and more had drifted again: `alerting/module.py:83` (the module's `dependencies`) now points at the closing bracket of an import, `alerting_bindings.py:88, :91` (the lane and housekeeping periods) at two import lines, `discord_webhook_channel.py:46` (the class) at the secret's name. `Docs/MODULES/bots.md` held 57; 11 of them pointed at the wrong code (`bot_run_state.py:54` at a logger, `grid_facts.py:136` at the end of another class).
- **Why they rot.** A line number changes with every edit above it, including one that changes nothing the design says. Keeping them true would make every code change edit the design, which teaches authors to touch the folder without reading it: the failure `EPIC-041J` §3 rejected for a mandatory design edit.
- **What does not rot that way.** A class, a function, a constant or an enum member changes only when the code it names really changes, which is when the design should be read again.
- **Two kinds of record already exist** (2026-10-14 D5): *descriptions*, true of `master` and changed with the code, and *decisions*, immutable once accepted. A bug report, a case study, a decision's "Established" facts and a task's implementation notes are evidence of one moment; they are never updated afterwards, so a line there is true forever if the moment is named.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **A design cites by path and symbol.** Everything under `Docs/MODULES/` cites code as `` `<path>.py` → `<symbol>` `` (a class, a function, `Class.method`, a constant, an enum member; more symbols of the same file follow with `` , `<symbol>` ``), and never by line number. A module docstring or a whole file is cited by its path alone | Accepted | 🟢 the owner (*"ok chốt hết theo đề xuất"*) · 🤖 agent (the arrow form, from the owner's own example) | A citation changes only when the code it names changes |
| D2 | **A point-in-time record may cite a line, at a named commit.** A bug report, a decision's "Established" facts, a case study, a task's implementation notes and a pull request's root cause may keep `file:line`, but name the commit sha the line was read at. They are evidence of that moment and are never updated afterwards | Accepted | 🟢 the owner | The evidence stays checkable (`git show <sha>:<path>`) and nobody maintains it |
| D3 | **A guard holds D1 and keeps a name from rotting.** `tests/unit/architecture/test_module_docs_cite_code_by_symbol.py` fails when any file under `Docs/MODULES/` holds a line citation (`x.py:12`, ranges, lists, a bare `` `:56-72` ``, `#L12`, the same on any other file), and when a cited symbol is not defined in the file its path names (a class, a function or an assigned name anywhere in the file's AST) or the path does not name exactly one file under `src/`, `scripts/` or `tests/`. Its probes plant each form and go red when the check is weakened | Accepted | 🟢 the owner (the guard and its probes) · 🤖 agent (a pytest guard under `tests/unit/architecture/`, beside the other document guards, run in the commit tier) | A renamed or deleted symbol turns CI red, so a name citation cannot rot silently. The check does not prove a method belongs to the named class (kept simple, the owner's brief); review K10 judges the rest |
| D4 | **The rule is stated once.** `commit-rule.md` §1 ("Citing code") states D1 and D2; the template (`Docs/MODULES/README.md`), the decision, bug-report and task templates and `fix-bug-rule.md` cite it. "Design in step" no longer lists a `file:line` citation among the facts a pull request keeps in step; a renamed symbol is caught by D3 instead | Accepted | 🤖 agent, under P3 | One clause to change; the list of design facts shrinks to what a reader needs |
| D5 | **Every existing design citation is converted now.** `Docs/MODULES/alerting/` and `Docs/MODULES/bots.md`, each citation checked against the code at the PR's head, so the guard is green from its first commit. `bots.md` moves to its folder in `EPIC-041E`, which follows D1 | Accepted | 🟢 the owner (`alerting/`) · 🤖 agent (`bots.md`, which the guard also covers) | No allowlist is needed |

## 2a. Constitution check
| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | `test_module_docs_cite_code_by_symbol.py` holds D1 and D3 in the commit tier; its probes go red when a form is no longer caught; the `[guard: …]` tag on the rule is checked by `rule_integrity` |
| P2 Verify, don't restate | ✅ | Every converted citation was opened at `30a75f9`; the drifted ones are named in §1 and in the task's notes |
| P3 A copy drifts | ✅ | The rule lives once in `commit-rule.md` §1; templates and other rules cite it |
| P4 Green proves only what was tested | ✅ | The guard proves a name exists in the file, not that the sentence about it is true; D3 and rubric K10 say so |
| P5 Apply before you invent | ✅ | The guard follows the existing document guards (`test_spec_index_is_consistent.py`, `test_case_study_index_is_consistent.py`) and the scanned-roots registry; symbol references are how Sphinx and mkdocstrings cite code |
| P6 Fix the mechanism | ✅ | The rot came from the citation form; the form changes, rather than a re-verification pass |
| P7 Seam now, variant later | ✅ | A simple name check; a stricter owner check (method of class) can be added inside the same guard if a real miss appears |
| P8 Ratchets only fall | ✅ | A guard is added; nothing is loosened. Point-in-time records gain a requirement (the sha) |
| P9 Decide alone | ✅ | The owner settled the policy; the form and the mechanism are decided here |
| P10 Pyramid and units | ✅ | The decision is the title; counts are measured on a named commit |
| P11 Prompt-grade artifacts | ✅ | The rule clause is imperative, tagged and gives the form with an example |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | Documents, one test file, one registry row |

## 3. Alternatives considered
- **Keep `file:line` and re-verify on each change.** Rejected by the owner: every unrelated edit rewrites the design.
- **A permalink to a commit (`blob/<sha>/x.py#L12`) in designs.** Rejected: true forever, but of an old tree; a design must describe `master`.
- **Paths only, no symbol.** Rejected: a 400-line file cited by path alone sends the reader searching, and a deleted function goes unnoticed.
- **The `path::Symbol` form (pytest node ids).** Considered; the arrow form is the owner's own example and reads as prose. The guard parses one form.
- **Prove that a method belongs to its class.** Deferred (P7): the owner asked for the simple check, and the name check already catches a rename or a deletion.
- **A guard for point-in-time records.** Not added: the sha is checkable by a reviewer (rubric N8), and a regex over the history of every bug report would flag the 213 existing reports, which D2 does not rewrite.

## 4. Open questions
None.

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1–D5 | [EPIC-041K](completed/EPIC-041K_cite_code_by_symbol.md) | Verified | `commit-rule.md` §1 ("Citing code"); `tests/unit/architecture/test_module_docs_cite_code_by_symbol.py`; `Docs/MODULES/alerting/`, `Docs/MODULES/bots.md` |
