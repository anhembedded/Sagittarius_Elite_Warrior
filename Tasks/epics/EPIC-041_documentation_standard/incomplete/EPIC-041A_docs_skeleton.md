# EPIC-041A — The documentation skeleton exists: a map, a status on every doc, four homes with their templates, a `bots` module doc ready for EPIC-040 to fill, and a rule that every task updates the docs it changes

**Status:** 🔵 Backlog
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
- [ ] **Map.** `Docs/README.md` lists the reader questions and the one file or folder that answers each:
  - what the app must do (`SPEC/`);
  - how the system is built (`ARCHITECTURE/`);
  - how one module works (`MODULES/`);
  - why a decision was taken (`DECISIONS/`);
  - how to run and operate the host (`OPERATIONS/`);
  - what a word means (`VOCABULARY/`);
  - what went wrong and why the gate missed it (`CASE_STUDIES/`);
  - what the process numbers say (`METRICS/`).

  Older trees (`HLD/`, `SDD/`, `Diagrams/`) are listed as *being replaced*, with what each still uniquely holds.
- [ ] **Status.** Every `.md` under `Docs/` starts with `Status: Current`, `Status: Superseded by <link>` or `Status: Historical`. Files whose own text says "superseded" take that status with the link they name. A file nobody can vouch for is marked `Historical`, not `Current`.
- [ ] **Four homes.** `Docs/ARCHITECTURE/`, `Docs/MODULES/`, `Docs/DECISIONS/` and `Docs/METRICS/` each hold a `README.md` that says:
  - what belongs there and what does not;
  - who reads it, and the question it answers;
  - the file layout and naming;
  - the diagram notation (PlantUML, sources under a `diagrams/` subfolder);
  - the doc ↔ rule ↔ guard linking convention of decision D1, with one worked example.
- [ ] **Module template.** `Docs/MODULES/README.md` gives the module-doc template:
  - seven views (context, components, state machines, sequences, data model, threading and deployment, timing);
  - per view, what it answers and where its facts come from;
  - the rule that state machines and timing tables are generated from code (D4), when the task that fills them adds the generator.
- [ ] **`Docs/MODULES/bots.md` skeleton.** It has:
  - the seven headings;
  - under each heading, a one-paragraph summary of what exists today, citing `file:line` and the existing design records (ADR 029 §3, design 038, design 039);
  - a `Filled by:` line naming the task that will complete that view: an `EPIC-040` child where the view is the one 040 changes, otherwise `EPIC-041E`.

  No diagram is drawn yet. The facts come from the coordinator's bots explanatory page of 2026-10-14, re-checked against the tree at the time of writing.
- [ ] **Docs touched, as a rule.**
  - `.claude/templates/task.md` gains a required section `## 6. Docs touched`: each doc the task changes, or "none, because …".
  - `.github/PULL_REQUEST_TEMPLATE.md` gains the same line.
  - `.claude/rules/task-execution-rule.md` gains one tagged clause: a task that changes a module's shape, a boundary, a lifecycle, a thread or a timing constant updates its module doc in the same PR.
- [ ] **Navigation.** `CLAUDE.md`'s "Where to read what" table gains a row pointing at `Docs/README.md`, and the rule-navigation guard passes.
- [ ] **EPIC-040 aimed at the skeleton.** EPIC-040's README gains one note: every child updates the `Docs/MODULES/bots.md` views it changes, through the "Docs touched" section.
- [ ] Nothing else in `Docs/` changes content. Moving, merging or rewriting old docs is `041D` and `041I`.

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
