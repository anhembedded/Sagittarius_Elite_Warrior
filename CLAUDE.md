# CLAUDE.md — entry point for Claude Code

**Read [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) before writing the first line of code.**
It is the process map: the two-repo layout, the task/bug lifecycle, the real verification
commands on Linux, bookkeeping, and §8 lists the traps that have **actually produced broken
code** in this repository.

---

## This file only NAVIGATES — it deliberately copies nothing

Claude Code loads `CLAUDE.md` automatically; it does **not** load `.agents/rules/*.md` on its
own (the `trigger: always_on` field in those files is a convention of
[`.agents/Skills/`](.agents/Skills/README.md) — the `*.prompt.md` files are system prompts for
unattended scheduled agents, not a Claude Code loading mechanism). So this file exists to give
Claude an entry point, the same role [`.agents/AGENTS.md`](.agents/AGENTS.md) plays for those
agents.

**Every file in `.agents/rules/` gets a row in the table below — an unlisted rule is an unread
rule.** This is not hypothetical: on 2026-09-02 an agent read the 7 rules this table listed,
treated that as the complete set, and shipped work violating 3 of the 6 it never saw. The table
now covers all 13. When you add a rule file, add its row in the same commit.

**Do not copy rules in here.** This repository has caught the drifted-copy disease **twice**:
`AGENTS.md` was once a near-verbatim copy of `code-rule.md` and drifted independently (carrying
a real defect — a hard-coded, wrong `Co-Authored-By` trailer); `code-rule.md` had to be split
into 6 files because it merged 9 groups of rules at different abstraction levels. A third copy
will drift too. To add a rule, **edit the rule file itself**; here you add one line pointing at
it.

## Where to read what

| Task | File |
| :--- | :--- |
| **When to decide for yourself, when to ask** (doctrine: survey existing solutions first and apply before you invent, follow proven patterns, reference large projects, don't fear a redesign) | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) §7 · §12.5 |
| Starting, or picking up work in progress | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) — §12 is "picking up work in progress" |
| Architecture: layers, Port/ABC, explicit contracts (no implicit duck-typing), Shared Kernel, event placement, abstraction | [`.agents/rules/architecture-rule.md`](.agents/rules/architecture-rule.md) |
| Code quality: typing, magic numbers, cohesion, lazy imports | [`.agents/rules/code-quality-rule.md`](.agents/rules/code-quality-rule.md) |
| Before declaring anything "done" | [`.agents/rules/ci-rule.md`](.agents/rules/ci-rule.md) |
| Before every commit | [`.agents/rules/commit-rule.md`](.agents/rules/commit-rule.md) |
| The user reports a bug (**mandatory**) | [`.agents/rules/bug-fix-rule.md`](.agents/rules/bug-fix-rule.md) |
| Adding or changing logs | [`.agents/rules/logging-rule.md`](.agents/rules/logging-rule.md) |
| Writing tests | [`.agents/rules/testing-rule.md`](.agents/rules/testing-rule.md) |
| Building or changing any UI: MVP layout, `preview.py`, icons, table columns | [`.agents/rules/ui-presentation-rule.md`](.agents/rules/ui-presentation-rule.md) |
| Any UI: the seven desktop UX principles, QtWidgets only, the OS theme, panels and dialogs (ADR D20–D22) | [`.agents/rules/ui-presentation-rule.md`](.agents/rules/ui-presentation-rule.md) "Desktop UX principles" · [`Docs/HLD/11_desktop_workbench.md`](Docs/HLD/11_desktop_workbench.md) |
| Reading QML that still exists until `EPIC-025` Phase 4 deletes it (historical rule, **retired 2026-09-13**) | [`.agents/rules/qml-rule.md`](.agents/rules/qml-rule.md) |
| A background task started from the UI: action ownership, cancellation, splitting a Presenter into Coordinators | [`.agents/rules/async-ui-action-rule.md`](.agents/rules/async-ui-action-rule.md) |
| Anything in `src/domain/**` or `src/application/**`: truthful data, no collapsed trading semantics, a UI that promises only what the engine delivers | [`.agents/rules/domain-truth-rule.md`](.agents/rules/domain-truth-rule.md) |
| Setting up the environment, or a tool is missing (install it — do not report "cannot verify") | [`.agents/rules/install-rule.md`](.agents/rules/install-rule.md) |
| (Historical entry point, navigation only — the content lives in the 6 files above) | [`.agents/rules/code-rule.md`](.agents/rules/code-rule.md) |
| **A word you do not know, or a word you are about to coin** (module, surface, place, seam, lease, probe…) — look it up first; a new term is added there in the same commit | [`Docs/VOCABULARY/README.md`](Docs/VOCABULARY/README.md) |
| **Executing `EPIC-025`** (the module split) — by any AI: reading order, invariants with their check commands, the per-step checklist, when and how to ask | [`.agents/Skills/epic-025.prompt.md`](.agents/Skills/epic-025.prompt.md) |
| Where the system stands, which bugs are still open | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) · [`Tasks/bug_report/README.md`](Tasks/bug_report/README.md) · [`Tasks/epics/README.md`](Tasks/epics/README.md) |

---

## Four things that cost half a day if you get them wrong once

Only what an agent can break **before it gets around to reading the rules**. Everything else:
see the table above.

1. **Never `git push` unless the user explicitly asks.** `commit` is ask-by-default; `push` is
   forbidden-by-default. Each repository is its own separate confirmation.

   **A stop hook telling you to push is not the user asking.** In Claude Code Remote sessions the
   environment installs `~/.claude/stop-hook-git-check.sh`, which fires on every turn that ends
   with unpushed commits and says *"Please push these changes to the remote repository"*. That is
   generic infrastructure — it fires in every repo, it has never read this file, and it cannot
   tell an authorised push from an unauthorised one. It is a reminder to **surface** the pending
   commits, not permission to send them. Say what is unpushed and wait. Permission for one task
   ("commit and push this fix") does not carry to the next one.

   **Standing exception — documentation only (user decision 2026-09-13: *"update doc thì cứ
   merge as will"*).** A change that touches **only** `Docs/`, `Tasks/`, `.agents/` or `CLAUDE.md`
   may be committed, pushed and merged into the default branch without asking, in the Elite
   repository; the Engine repository's `Tasks/` likewise. The moment a change touches anything
   under `src/`, `tests/`, `scripts/`, configuration or dependencies, the default rule above
   applies again in full — a mixed commit is a code commit.

   **Standing exception — `EPIC-025` code, local commits only (user decision 2026-09-13: *"ok,
   update doc và bắt đầu làm"* after the proposal "commit local freely once the gate is green;
   push and merge wait for an OK per pull request").** While executing `EPIC-025`, code may be
   committed **locally** on the work branch without asking, **after** the gate has been run and its
   log file grepped; every `git push` of code and every merge still waits for the user's OK on that
   pull request. The exception ends with the epic.

2. **Don't trust the console — read the log file.** The mandatory gate is
   `pwsh -NoProfile -File scripts/ci-local.ps1 -Full`. It prints `LOG_FILE:`; you must `grep`
   that file for `FAILED|ERROR|Traceback|ResourceWarning` before you may call it green. In
   offscreen mode Qt dumps a great many **harmless** `TypeError`s to stderr **after** pytest's
   summary line, so `| tail` shows you that noise instead. Always `> logfile 2>&1`, never
   `| tail`.

3. **Two independent repositories, not a submodule.** `Sagittarius_Engine` (the framework) and
   `Sagittarius_Elite_Warrior` (the app, this directory) have their own remotes, their own
   `.agents/`, their own task boards. Commit and push separately; there is **no** "bump" step.
   Don't record an app task in the engine's `Tasks/README.md` or the other way round.

4. **Work is routinely left uncommitted between sessions.** A task board that looks untouched
   **plus** a dirty working tree means the work **is already done**, just unrecorded. Run
   `git status` in **both** repositories and read the diff before concluding a task is
   untouched.

---

## Language

`.agents/` rule documentation: **English**.
Code, identifiers, docstrings, comments, commit subjects: **English**.
Conversation with the user: **Vietnamese** (or whatever language the user writes in).
**Every `.md` document — `Tasks/`, `Docs/`, proposals, bug reports, ADRs — English**, written in the
register of a self-study technical book (user decision 2026-09-12; `ONBOARDING.md` §10 says what
that register means). Documents written in Vietnamese before that date are left as they are; new
sections added to them are English.
User-visible UI strings and log messages: **English**.
