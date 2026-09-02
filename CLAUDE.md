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

**Do not copy rules in here.** This repository has caught the drifted-copy disease **twice**:
`AGENTS.md` was once a near-verbatim copy of `code-rule.md` and drifted independently (carrying
a real defect — a hard-coded, wrong `Co-Authored-By` trailer); `code-rule.md` had to be split
into 6 files because it merged 9 groups of rules at different abstraction levels. A third copy
will drift too. To add a rule, **edit the rule file itself**; here you add one line pointing at
it.

## Where to read what

| Task | File |
| :--- | :--- |
| **When to decide for yourself, when to ask** (doctrine: follow proven patterns, reference large projects, don't fear a redesign) | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) §7 |
| Starting, or picking up work in progress | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) — §12 is "picking up work in progress" |
| Architecture: layers, Port/ABC, explicit contracts (no implicit duck-typing), Shared Kernel, event placement, abstraction | [`.agents/rules/architecture-rule.md`](.agents/rules/architecture-rule.md) |
| Code quality: typing, magic numbers, cohesion, lazy imports | [`.agents/rules/code-quality-rule.md`](.agents/rules/code-quality-rule.md) |
| Before declaring anything "done" | [`.agents/rules/ci-rule.md`](.agents/rules/ci-rule.md) |
| Before every commit | [`.agents/rules/commit-rule.md`](.agents/rules/commit-rule.md) |
| The user reports a bug (**mandatory**) | [`.agents/rules/bug-fix-rule.md`](.agents/rules/bug-fix-rule.md) |
| Adding or changing logs | [`.agents/rules/logging-rule.md`](.agents/rules/logging-rule.md) |
| Writing tests | [`.agents/rules/testing-rule.md`](.agents/rules/testing-rule.md) |
| Where the system stands, which bugs are still open | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) · [`Tasks/bug_report/README.md`](Tasks/bug_report/README.md) · [`Tasks/epics/README.md`](Tasks/epics/README.md) |

---

## Four things that cost half a day if you get them wrong once

Only what an agent can break **before it gets around to reading the rules**. Everything else:
see the table above.

1. **Never `git push` unless the user explicitly asks.** `commit` is ask-by-default; `push` is
   forbidden-by-default. Each repository is its own separate confirmation.

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
Conversation with the user, task files, bug reports, `Tasks/` documents: **Vietnamese**.
User-visible UI strings: **Vietnamese**.
