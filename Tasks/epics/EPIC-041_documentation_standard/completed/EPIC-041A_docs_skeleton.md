# EPIC-041A — The documentation skeleton exists: a map, a status on every doc, four homes with their templates, a `bots` module doc ready for EPIC-040 to fill, and a rule that every task updates the docs it changes

**Status:** ✅ Done (2026-10-14)
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now") Then, on scope: *"hãy tạo task đầu tiên là xây skeleton hướng tới epic tách common cho bot"* ("make the first task build the skeleton, aimed at the epic that makes bots common"); the rest of the epic stays as written for later.
**Risk:** 🟢 — Markdown only; one clause added to a rule and one field to two templates
**Complexity:** M — many small files, no code
**Epic:** [EPIC-041](../README.md)
**Depends on:** None. It is the first task; [EPIC-040](../../EPIC-040_backtest_workbench/README.md) fills `Docs/MODULES/bots.md` as it builds.

---

## 1. Context and problem
- `Docs/` has nine areas and no map. Some files are superseded and say so (`Docs/Diagrams/architecture.md`, `ui_architecture.md`). Others carry no status at all, and `Docs/SDD/README.md` still reads "Draft round 3".
- The owner will next work on `EPIC-040`, the epic that makes bots common. They want its bot documentation written while the code is written, not in a separate later pass. They also want the other docs to grow task by task.
- Docs written task by task only happen if each task is required to touch them, and if each new doc has a home and a shape. Neither exists today.

## 2. Acceptance criteria
- [x] **Map.** `Docs/README.md` lists the reader questions and the one file or folder that answers each:
  - what the app must do (`SPEC/`);
  - how the system is built (`ARCHITECTURE/`);
  - how one module works (`MODULES/`);
  - why a decision was taken (`DECISIONS/`);
  - how to run and operate the host (`OPERATIONS/`);
  - what a word means (`VOCABULARY/`);
  - what went wrong and why the gate missed it (`CASE_STUDIES/`);
  - what the process numbers say (`METRICS/`).

  Older trees (`HLD/`, `SDD/`, `Diagrams/`) are listed as *being replaced*, with what each still uniquely holds.
- [x] **Status.** Every `.md` under `Docs/` starts with `Status: Current`, `Status: Superseded by <link>` or `Status: Historical`. Files whose own text says "superseded" take that status with the link they name. A file nobody can vouch for is marked `Historical`, not `Current`.
- [x] **Four homes.** `Docs/ARCHITECTURE/`, `Docs/MODULES/`, `Docs/DECISIONS/` and `Docs/METRICS/` each hold a `README.md` that says:
  - what belongs there and what does not;
  - who reads it, and the question it answers;
  - the file layout and naming;
  - the diagram notation (PlantUML, sources under a `diagrams/` subfolder);
  - the doc ↔ rule ↔ guard linking convention of decision D1, with one worked example.
- [x] **Module template.** `Docs/MODULES/README.md` gives the module-doc template:
  - seven views (context, components, state machines, sequences, data model, threading and deployment, timing);
  - per view, what it answers and where its facts come from;
  - the rule that state machines and timing tables are generated from code (D4), when the task that fills them adds the generator.
- [x] **`Docs/MODULES/bots.md` skeleton.** It has:
  - the seven headings;
  - under each heading, a one-paragraph summary of what exists today, citing `file:line` and the existing design records (ADR 029 §3, design 038, design 039);
  - a `Filled by:` line naming the task that will complete that view: an `EPIC-040` child where the view is the one 040 changes, otherwise `EPIC-041E`.

  No diagram is drawn yet. The facts come from the coordinator's bots explanatory page of 2026-10-14, re-checked against the tree at the time of writing.
- [x] **Docs touched, as a rule.**
  - `.claude/templates/task.md` gains a required section `## 6. Docs touched`: each doc the task changes, or "none, because …".
  - `.github/PULL_REQUEST_TEMPLATE.md` gains the same line.
  - `.claude/rules/task-execution-rule.md` gains one tagged clause: a task that changes a module's shape, a boundary, a lifecycle, a thread or a timing constant updates its module doc in the same PR.
- [x] **Navigation.** `CLAUDE.md`'s "Where to read what" table gains a row pointing at `Docs/README.md`, and the rule-navigation guard passes.
- [x] **EPIC-040 aimed at the skeleton.** EPIC-040's README gains one note: every child updates the `Docs/MODULES/bots.md` views it changes, through the "Docs touched" section.
- [x] Nothing else in `Docs/` changes content. Moving, merging or rewriting old docs is `041D` and `041I`.

## 3. Design
- **Thin first and one fact in one place** (decisions D2, D7). The skeleton gives each future doc a home, a shape and an owner, and writes no view twice.
- **The "Docs touched" section is the mechanism** that turns "the docs will grow task by task" into work (P1 mechanism over memory). Without it, docs fall behind from the second task on.
- **The bots skeleton links, it does not copy.** Each summary points at the code and the existing records, so a later view replaces a paragraph rather than reconciling two texts.

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Skeleton plus the "Docs touched" rule (chosen) | Docs grow with the code that changes them; EPIC-040 starts with a place to write |
| Write the full bots doc first (`041E` now) | Rejected for now: EPIC-040 is about to change the bots module, so the doc would be rewritten |
| Folders only, no rule | Rejected: nothing would make a task write the doc |

The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Navigation table and its guard: `CLAUDE.md` "Where to read what" and `tests/unit/test_rule_navigation_is_complete.py`.
- Superseded wording: `Docs/Diagrams/architecture.md` and `Docs/HLD/05_engine_app_split.md` already carry it.
- Template conventions: `.claude/templates/task.md` and `.claude/templates/epic.md`.
- Bots facts: the 2026-10-14 explanatory page, which cites `file:line` throughout. Each citation is re-verified before it is copied.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/README.md` | New map |
| every `Docs/**/*.md` | A `Status:` line |
| `Docs/ARCHITECTURE/README.md`, `Docs/MODULES/README.md`, `Docs/DECISIONS/README.md`, `Docs/METRICS/README.md` | New home READMEs |
| `Docs/MODULES/bots.md` | Seven-view skeleton |
| `.claude/templates/task.md`, `.github/PULL_REQUEST_TEMPLATE.md` | "Docs touched" section |
| `.claude/rules/task-execution-rule.md` | One tagged clause |
| `CLAUDE.md` | One navigation row |
| `Tasks/epics/EPIC-040_backtest_workbench/README.md` | One note |

## 5. Testing
Documentation-only (ONBOARDING §7): every changed path is `*.md` or the PR template.
- `python3 scripts/check_skill_prompt_references.py` passes.
- The document guards pass, including the rule-navigation, task-board and `.claude` wiring guards.
- The `-Full` run on the PR is green.
- A grep shows every `Docs/**/*.md` has a `Status:` line.
- Every `file:line` cited in `bots.md` exists at the PR's head.

## 6. Docs touched
`Docs/` (new map, homes, `MODULES/bots.md` skeleton, status lines); the task template, the PR template, `task-execution-rule.md`, `CLAUDE.md`.

## Implementation notes (written when done)
Verified at the branch head `claude/epic-041a-docs-skeleton`, built on `0d44850`. Documentation-only (ONBOARDING §7); the `-Full` run on the PR is the gate's authority and is not claimed here.

| Criterion | Evidence |
| :--- | :--- |
| Map | `Docs/README.md`: eight reader questions, the status vocabulary, and a table of what `HLD/`, `SDD/` and `Diagrams/` still uniquely hold |
| Status | All 51 existing files under `Docs/` and the five new ones start with a `Status:` line, except the generated `OPERATIONS/exit_codes.md` (`grep -L '^Status:' -r Docs --include=*.md` lists only it). A status line there broke `test_exit_code_table.py`, which compares the file with `scripts/render_exit_codes.py` byte for byte; `Docs/README.md` states the exemption: a generated document is current by construction. `Diagrams/architecture.md` and `ui_architecture.md` are `Superseded by` the links their own text names. `HLD/11_desktop_workbench.md` and the use-case, case-study, operations and vocabulary documents are `Current`. Everything nobody could vouch for (the other HLD files, all SDD files, the Vietnamese design notes, the intent and screen-registry documents) is `Historical`. The eight case studies stay at or under their 35-line cap: the blank line after the title gave way to the status line |
| Four homes, module template | `Docs/ARCHITECTURE/`, `MODULES/`, `DECISIONS/`, `METRICS/` each hold a `README.md` with belongs / does not belong, reader and question, layout, notation, and one worked D1 example; `MODULES/README.md` holds the seven-view template and the generated-from-code rule |
| `bots.md` skeleton | Seven headings, one paragraph each, a `Filled by:` line each. Every `file:line` was opened at this head before it was copied: 30 full-path citations resolve to existing files and lines |
| Docs touched | Section 6 in `.claude/templates/task.md`; a fourth heading in `.github/PULL_REQUEST_TEMPLATE.md`; one clause in `task-execution-rule.md` tagged `[review: K4; eye]` (K4 is the rubric's "structural changes update the design documents" check; no new check id was invented) |
| Navigation | One row in `CLAUDE.md`; `test_rule_navigation_is_complete.py` passes |
| EPIC-040 | Its README already carried the note, merged with the scaffold in #500; the link to this task now points at `completed/` |
| Nothing else changes | The only edit to an existing document under `Docs/` is the first line (plus, for the case studies, the removed blank) |

**Differences from the fact sheet** (it was a lead; these are what the tree says):
- `order_session_opening.py` has three callers by call site but two importing files: `grid_start_preconditions.py:76` (Resume from HALTED) and `:114` (Start), and `resume_recovering_for_host/handler.py:81`. The module's docstring names `BotRunner.resume` as the second caller, which reaches it through `open_session_for_resume`.
- `grid_facts.py` runs to `:232`, not `:231`; the alerting note spans `module.py:3-6`.
- The work queue is per bot, but the ticker is one shared object (`bots-ticker`) with a daemon thread per task, not per bot.
- `module.py:200` is where `dependencies` is declared; the fact sheet gave no line.

**Checks run:** `python3 scripts/check_skill_prompt_references.py` (7 checks, no problem; it resolves paths against tracked files, so the new files had to be staged first); `pytest` on `test_rule_navigation_is_complete.py`, `test_task_board_is_consistent.py`, `test_claude_tree_is_wired.py`, the SPEC and case-study index guards, `tests/unit/scripts/rule_integrity` and `test_no_runtime_artifact_is_tracked.py` (266 passed); `python3 scripts/render_board.py` runs. **Not run here:** the rest of `tests/unit/scripts` (this sandbox lacks `PySide6` and `pwsh`) and the `-Full` gate. The first push skipped `test_exit_code_table.py` along with that directory and went red on it; it and every test that reads `Docs/` were run before the fix.

**Left alone, found on the way:** two links already broken before this task, `Docs/Diagrams/event_correlation_id_design.md` (to `src/presentation/ui/common/base_feed.py`) and `Docs/VOCABULARY/README.md` (to `EPIC-038G` under `incomplete/`). Moving or rewriting documents is `041D`/`041I`; `041B` will check links.
