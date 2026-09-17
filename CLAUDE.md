# CLAUDE.md — entry point

**Read [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) first.** This file navigates and copies no rule: a copy drifts, and this repository has paid for that twice. Every file in `.agents/rules/` has a row below (`tests/unit/test_rule_navigation_is_complete.py` fails otherwise); rules marked `on_file_change` also load by themselves through the pointers in [`.claude/rules/`](.claude/rules/) when you open a matching file.

## Where to read what

| Task | File |
| :--- | :--- |
| Starting; picking up work; authority; deciding alone; the settled principles; the traps | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) |
| What the app must do, one use case per file | [`Docs/SPEC/README.md`](Docs/SPEC/README.md) |
| Architecture: layers, ports, explicit contracts, events, seams | [`architecture-rule.md`](.agents/rules/architecture-rule.md) |
| Code quality | [`code-quality-rule.md`](.agents/rules/code-quality-rule.md) |
| Before calling anything done: the gate, its cadence, the test levels | [`ci-rule.md`](.agents/rules/ci-rule.md) |
| Before every commit | [`commit-rule.md`](.agents/rules/commit-rule.md) |
| Reviewing a pull request, branch or diff | [`.claude/skills/pr-review/SKILL.md`](.claude/skills/pr-review/SKILL.md) |
| The user reports a bug | [`bug-fix-rule.md`](.agents/rules/bug-fix-rule.md) |
| A defect got through a green gate | [`Docs/CASE_STUDIES/README.md`](Docs/CASE_STUDIES/README.md) |
| Adding or changing logs | [`logging-rule.md`](.agents/rules/logging-rule.md) |
| Reporting to the user, or asking a question | [`report-rule.md`](.agents/rules/report-rule.md) |
| Writing tests | [`testing-rule.md`](.agents/rules/testing-rule.md) |
| UI: QtWidgets only, desktop UX principles, layout, preview | [`ui-presentation-rule.md`](.agents/rules/ui-presentation-rule.md) · [`Docs/HLD/11_desktop_workbench.md`](Docs/HLD/11_desktop_workbench.md) |
| Background work started from the UI | [`async-ui-action-rule.md`](.agents/rules/async-ui-action-rule.md) |
| Domain and application code | [`domain-truth-rule.md`](.agents/rules/domain-truth-rule.md) |
| Environment setup; a missing tool | [`install-rule.md`](.agents/rules/install-rule.md) |
| A word you do not know or are about to coin | [`Docs/VOCABULARY/README.md`](Docs/VOCABULARY/README.md) |
| Executing `EPIC-025` | [`.agents/Skills/epic-025.prompt.md`](.agents/Skills/epic-025.prompt.md) |
| Where the system stands | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) · [`Tasks/bug_report/README.md`](Tasks/bug_report/README.md) · [`Tasks/epics/README.md`](Tasks/epics/README.md) |

## Four things that cost half a day if you get them wrong once

1. **Authority is one table, `ONBOARDING.md` §7.** Commit and push to your own branch are free once the per-commit checks are green; a documentation-only change (§7 defines the set) may be merged; a code change reaches `master-warrior` only after the full gate on the final tree and a review by a *different* session — the author never merges its own code. A stop hook asking you to push is not the user asking.
2. **Don't trust the console — read the log file.** `pwsh -NoProfile -File scripts/ci-local.ps1 -Full > log 2>&1`, then grep the `LOG_FILE:` it prints for `FAILED|ERROR|Traceback|ResourceWarning`. Never `| tail`.
3. **Two independent repositories, not a submodule.** Engine and app have their own remotes and boards; separate commits, no bump step.
4. **Work is often left uncommitted between sessions.** `git status` in both repositories before concluding a task is untouched.

## Language
Rules, code, identifiers, docstrings, comments, commit subjects, UI strings and log messages: English. Every `.md`: English in the register `ONBOARDING.md` §10 defines. Conversation with the user: Vietnamese, or whatever they write in.
