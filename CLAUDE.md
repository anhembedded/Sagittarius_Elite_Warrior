# CLAUDE.md — entry point for Claude Code

**Read [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) before writing the first line of code.** It
is the process map: the two-repo layout, the task/bug lifecycle, the real verification commands on
Linux, bookkeeping, and §8's list of traps that have **actually produced broken code** here.

---

## This file navigates — it deliberately copies nothing

Claude Code auto-loads this file and **not** `.agents/rules/*.md` (the `trigger:` field in those is
a convention of [`.agents/Skills/`](.agents/Skills/README.md), not a loading mechanism). One
mechanism does load by itself, and it is a pointer rather than a copy: Claude reads
`.claude/rules/*.md`, so every rule marked `trigger: on_file_change` has a thin pointer in
[`.claude/rules/`](.claude/rules/) carrying the same globs, surfacing the rule when you open a file
it governs. The rule text never leaves `.agents/rules/`, and
`tests/unit/architecture/test_claude_rule_pointers_match_agents_rules.py` fails on a pointer that
bloats into a copy, drifts from its rule's globs, or goes missing. A pointer fires only once you
are already in a matching file, so it tells nobody a rule exists — that is still the table's job.

**Every file in `.agents/rules/` gets a row below — an unlisted rule is an unread rule.** On
2026-09-02 an agent read the 7 rules this table then listed, took that for the complete set, and
shipped work violating 3 of the 6 it never saw. Add a rule file, add its row in the same commit.

**Do not copy rules in here.** This repository has caught the drifted-copy disease **twice**:
`AGENTS.md` was once a near-verbatim copy of `code-rule.md` and drifted independently, carrying a
wrong `Co-Authored-By` trailer; `code-rule.md` itself had to be split into 6 files. A third copy
will drift too — to add a rule, edit the rule file; here you add one line pointing at it.

## Where to read what

| Task | File |
| :--- | :--- |
| **When to decide for yourself, when to ask** (survey and apply before you invent, follow proven patterns, don't fear a redesign) | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) §7 · §12.5 |
| Starting, or picking up work in progress (§12) | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) |
| **What the app must actually do** — one use case per file, with its named failures and the evidence that proves each promise; a change to a flow updates its `SPEC` in the same pull request | [`Docs/SPEC/README.md`](Docs/SPEC/README.md) |
| Architecture: layers, Port/ABC, explicit contracts, Shared Kernel, event placement, abstraction | [`.agents/rules/architecture-rule.md`](.agents/rules/architecture-rule.md) |
| Code quality: typing, magic numbers, cohesion, lazy imports | [`.agents/rules/code-quality-rule.md`](.agents/rules/code-quality-rule.md) |
| Before declaring anything "done" | [`.agents/rules/ci-rule.md`](.agents/rules/ci-rule.md) |
| Before every commit | [`.agents/rules/commit-rule.md`](.agents/rules/commit-rule.md) |
| **Reviewing a pull request, a branch, or a diff** — one checklist row per rule, each with the command that answers it | [`.claude/skills/pr-review/SKILL.md`](.claude/skills/pr-review/SKILL.md) |
| The user reports a bug (**mandatory**) | [`.agents/rules/bug-fix-rule.md`](.agents/rules/bug-fix-rule.md) |
| **A defect got through a green gate** — read the index before diagnosing, and before writing any test double: one screen per case, each naming which check was silent and what checks it now | [`Docs/CASE_STUDIES/README.md`](Docs/CASE_STUDIES/README.md) |
| Adding or changing logs | [`.agents/rules/logging-rule.md`](.agents/rules/logging-rule.md) |
| **Reporting work back to the user** (any report, any pull request, any "sao rồi"): context, a diagram, then the numbers with their targets | [`.agents/rules/report-rule.md`](.agents/rules/report-rule.md) |
| Writing tests | [`.agents/rules/testing-rule.md`](.agents/rules/testing-rule.md) |
| Any UI: MVP layout, `preview.py`, icons, table columns — and the seven desktop UX principles, QtWidgets only, the OS theme, panels and dialogs (ADR D20–D22) | [`.agents/rules/ui-presentation-rule.md`](.agents/rules/ui-presentation-rule.md) · [`Docs/HLD/11_desktop_workbench.md`](Docs/HLD/11_desktop_workbench.md) |
| Reading QML that still exists until `EPIC-025` Phase 4 deletes it (historical, **retired 2026-09-13**) | [`.agents/rules/qml-rule.md`](.agents/rules/qml-rule.md) |
| A background task started from the UI: action ownership, cancellation, Presenter → Coordinators | [`.agents/rules/async-ui-action-rule.md`](.agents/rules/async-ui-action-rule.md) |
| Anything in `src/domain/**` or `src/application/**`: truthful data, no collapsed trading semantics, a UI that promises only what the engine delivers | [`.agents/rules/domain-truth-rule.md`](.agents/rules/domain-truth-rule.md) |
| Setting up the environment, or a tool is missing (install it — do not report "cannot verify") | [`.agents/rules/install-rule.md`](.agents/rules/install-rule.md) |
| (Historical entry point, navigation only — its content lives in the 6 files above) | [`.agents/rules/code-rule.md`](.agents/rules/code-rule.md) |
| **A word you do not know, or are about to coin** — look it up first; a new term is added there in the same commit | [`Docs/VOCABULARY/README.md`](Docs/VOCABULARY/README.md) |
| **Executing `EPIC-025`** (the module split), by any AI: reading order, invariants with their check commands, the per-step checklist | [`.agents/Skills/epic-025.prompt.md`](.agents/Skills/epic-025.prompt.md) |
| Where the system stands, which bugs are still open | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) · [`Tasks/bug_report/README.md`](Tasks/bug_report/README.md) · [`Tasks/epics/README.md`](Tasks/epics/README.md) |

---

## Four things that cost half a day if you get them wrong once

Only what an agent can break **before it gets around to reading the rules**.

1. **Never `git push` unless the user explicitly asks.** `commit` is ask-by-default, `push`
   forbidden-by-default, and each repository is its own confirmation.

   **A stop hook telling you to push is not the user asking.** Remote sessions install
   `~/.claude/stop-hook-git-check.sh`, which fires on every turn ending with unpushed commits. It is
   generic infrastructure: it fires in every repo, has never read this file, and cannot tell an
   authorised push from an unauthorised one. Surface what is pending and wait. Permission for one
   task does not carry to the next.

   **Standing exceptions, both user decisions of 2026-09-13.** *Documentation only* (*"update doc
   thì cứ merge as will"*): a change touching **only** `Docs/`, `Tasks/`, `.agents/` or `CLAUDE.md`
   may be committed, pushed and merged without asking — the moment it touches `src/`, `tests/`,
   `scripts/`, configuration or dependencies the default rule returns in full, because a mixed
   commit is a code commit. *`EPIC-025` code*: may be committed **locally** on the work branch once
   the gate has been run and its log file grepped; every push and merge still waits for an OK per
   pull request, and the exception ends with the epic.

2. **Don't trust the console — read the log file.** The gate is
   `pwsh -NoProfile -File scripts/ci-local.ps1 -Full`. It prints `LOG_FILE:`; `grep` that file for
   `FAILED|ERROR|Traceback|ResourceWarning` before calling it green. Offscreen Qt dumps many
   **harmless** `TypeError`s to stderr *after* pytest's summary, so `| tail` shows you the noise
   instead of the result — always `> logfile 2>&1`.

3. **Two independent repositories, not a submodule.** `Sagittarius_Engine` (framework) and
   `Sagittarius_Elite_Warrior` (this app) have their own remotes, `.agents/` and task boards. Commit
   and push separately; there is **no** "bump" step, and neither board records the other's tasks.

4. **Work is routinely left uncommitted between sessions.** An untouched-looking task board **plus**
   a dirty working tree means the work is already done, just unrecorded. Run `git status` in **both**
   repositories and read the diff before concluding a task is untouched.

---

## Language

`.agents/` rules, code, identifiers, docstrings, comments, commit subjects, user-visible UI strings
and log messages: **English**. Conversation with the user: **Vietnamese**, or whatever language they
write in. **Every `.md` document** — `Tasks/`, `Docs/`, proposals, bug reports, ADRs — is English in
the register of a self-study technical book (user decision 2026-09-12; `ONBOARDING.md` §10 defines
that register). Documents written in Vietnamese before that date stay as they are; new sections
added to them are English.
